"""Atomic Firestore storage for one classroom. No client database access."""
import copy
import hashlib
import json
import secrets
import zlib
from datetime import datetime, timezone, timedelta

from google.cloud import firestore
import core

CHUNK_BYTES = 300_000
MAX_STATE_BYTES = 24_000_000
# Budget for both replaced/deleted chunks and new chunks within Firestore's
# transaction request limit; old blobs also count when they are deleted.
MAX_COMPRESSED_BYTES = 3_000_000


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Context:
    """Buffer writes so every Firestore read precedes every write."""
    def __init__(self, store, tx, meta):
        self.store, self.tx, self.meta = store, tx, meta
        self.pending, self.reads = {}, {}

    def ref(self, collection, key):
        return self.store.root.collection(collection).document(key)

    def get(self, collection, key):
        ref = self.ref(collection, key)
        if ref.path in self.pending:
            return copy.deepcopy(self.pending[ref.path][1])
        if ref.path not in self.reads:
            self.reads[ref.path] = ref.get(transaction=self.tx).to_dict()
        return copy.deepcopy(self.reads[ref.path])

    def put(self, collection, key, data):
        ref = self.ref(collection, key)
        self.pending[ref.path] = (ref, data)

    def revoke_all(self):
        self.meta['generation'] = secrets.token_hex(16)

    def revoke_students(self):
        self.meta['studentGeneration'] = secrets.token_hex(16)

    def revoke_actor(self, actor):
        self.meta.setdefault('actors', {})[actor] = secrets.token_hex(16)

    def flush(self):
        for ref, data in self.pending.values():
            if data is None:
                self.tx.delete(ref)
            else:
                self.tx.set(ref, data)


class Store:
    def __init__(self, client, classroom='main'):
        core.require(isinstance(classroom, str) and classroom and '/' not in classroom)
        self.client = client
        self.root = client.collection('sebitV4').document(classroom)

    def transaction(self, fn):
        @firestore.transactional
        def run(tx):
            manifest = self.root.get(transaction=tx).to_dict()
            old = manifest or {}
            meta = copy.deepcopy(old.get('auth', {'generation': '', 'studentGeneration': '', 'actors': {}}))
            chunk_ids = old.get('chunks', [])
            if chunk_ids:
                chunks = [self.root.collection('chunks').document(i).get(transaction=tx).to_dict()['body'] for i in chunk_ids]
                raw = zlib.decompress(b''.join(chunks))
                state = json.loads(raw)
            else:
                state = core.initial()
                raw = b''
            ctx = Context(self, tx, meta)
            result = fn(state, ctx)
            updated = json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()
            core.require(len(updated) <= MAX_STATE_BYTES, '학급 기록이 저장 한도에 도달했어요. 백업 후 관리자에게 문의해 주세요.')
            ids = chunk_ids
            if updated != raw:
                compressed = zlib.compress(updated)
                core.require(len(compressed) <= MAX_COMPRESSED_BYTES, '학급 기록이 저장 한도에 도달했어요. 백업 후 관리자에게 문의해 주세요.')
                ids = []
                for offset in range(0, len(compressed), CHUNK_BYTES):
                    body = compressed[offset:offset + CHUNK_BYTES]
                    key = hashlib.sha256(body).hexdigest()
                    ids.append(key)
                    if key not in chunk_ids:
                        ctx.put('chunks', key, {'body': body})
                for key in set(chunk_ids) - set(ids):
                    ctx.put('chunks', key, None)
            next_manifest = {'chunks': ids, 'auth': meta, 'configured': bool(state['teacher']),
                             'className': state['className'], 'opened': state['opened']}
            if next_manifest != old:
                tx.set(self.root, next_manifest)
            ctx.flush()
            return result
        return run(self.client.transaction(max_attempts=10))

    def actor(self, ctx, state, token, touch=False):
        core.require(isinstance(token, str) and 20 <= len(token) <= 200, '로그인이 필요해요.')
        session = ctx.get('sessions', digest(token))
        core.require(session, '로그인이 필요해요.')
        actor = session['actor']
        core.require(session['epoch'] == state['epoch'] and session['generation'] == ctx.meta['generation']
                     and session['actorVersion'] == ctx.meta.get('actors', {}).get(actor, ''), '다시 로그인해 주세요.')
        core.require(session['expiresAt'].timestamp() * 1000 > core.now(), '다시 로그인해 주세요.')
        if actor != 'teacher':
            person = core.student(state, actor)
            core.require(state['opened'] and person['active'] and session['studentGeneration'] == ctx.meta['studentGeneration'], '학생 접속이 닫혀 있어요.')
            core.require(core.now() - session['seen'] < 180000, '3분이 지나 로그아웃되었어요.')
        if touch:
            session['seen'] = core.now()
            session['expiresAt'] = datetime.now(timezone.utc) + timedelta(days=30 if actor == 'teacher' else 1)
            ctx.put('sessions', digest(token), session)
        return actor

    def login(self, login_id, password, ip='local'):
        login_id, password = core.txt(login_id, 40), core.txt(password, 200)
        def run(state, ctx):
            core.require(state['teacher'], '학급 설정을 먼저 진행해 주세요.')
            # Both account and source are limited; an IP change cannot bypass the account limit.
            keys = [digest('account:' + login_id), digest('source:' + ip)]
            attempts = [ctx.get('attempts', key) or {} for key in keys]
            for row, limit in zip(attempts, [5, 40]):
                if row.get('n', 0) >= limit and row.get('until', 0) > core.now():
                    return {'error': '여러 번 실패했어요. 5분 뒤 다시 시도해 주세요.'}
            person = next((p for p in state['students'] if p['login'] == login_id), None)
            hashed = state['teacher'] if login_id == 'teacher' else person['pin'] if person else ''
            if not core.pw_ok(password, hashed):
                for key, row in zip(keys, attempts):
                    ctx.put('attempts', key, {'n': (row.get('n', 0) if row.get('until', 0) > core.now() else 0) + 1,
                                             'until': core.now() + 300000,
                                             'expiresAt': datetime.now(timezone.utc) + timedelta(days=1)})
                return {'error': '아이디 또는 비밀번호를 확인해 주세요.'}
            if login_id != 'teacher':
                core.require(person and state['opened'] and person['active'], '학생 접속이 닫혀 있어요.')
            actor = 'teacher' if login_id == 'teacher' else person['id']
            ctx.put('attempts', keys[0], None)
            token = secrets.token_urlsafe(32)
            ctx.put('sessions', digest(token), {'actor': actor, 'seen': core.now(), 'epoch': state['epoch'],
                    'generation': ctx.meta['generation'], 'studentGeneration': ctx.meta['studentGeneration'],
                    'actorVersion': ctx.meta.get('actors', {}).get(actor, ''),
                    'expiresAt': datetime.now(timezone.utc) + timedelta(days=30 if actor == 'teacher' else 1)})
            return {'token': token, 'actor': actor}
        result = self.transaction(run)
        if 'error' in result:
            core.fail(result['error'])
        return result

    def view(self, token):
        def run(state, ctx):
            actor = self.actor(ctx, state, token)
            core.tick(state)
            return core.project_view(state, actor)
        return self.transaction(run)

    def command(self, token, command, body, key):
        core.require(isinstance(key, str) and 8 <= len(key) <= 100, '요청 번호가 필요해요.')
        core.require(isinstance(body, dict) and isinstance(command, str))
        def run(state, ctx):
            actor = self.actor(ctx, state, token, True)
            if actor != 'teacher' and core.student(state, actor)['mustChange']:
                core.require(command == 'pin', '먼저 개인 PIN을 변경해 주세요.')
            core.tick(state)
            request_key = digest(json.dumps([state['epoch'], actor, key]))
            signature = digest(json.dumps([command, body], sort_keys=True))
            previous = ctx.get('requests', request_key)
            if previous:
                core.require(previous['digest'] == signature, '같은 요청 번호에 다른 내용이 들어왔어요.')
                return json.loads(previous['result'])
            result = core.dispatch(state, ctx, actor, command, body) or {'ok': True}
            # Retained for the whole classroom epoch, with no short TTL replay window.
            ctx.put('requests', request_key, {'digest': signature, 'result': json.dumps(result), 'epoch': state['epoch']})
            return result
        return self.transaction(run)

    def backup(self, token):
        def run(state, ctx):
            core.require(self.actor(ctx, state, token) == 'teacher', '교사만 사용할 수 있어요.')
            core.tick(state)
            snapshot = copy.deepcopy(state)
            for person in snapshot['students']:
                person['tempPin'] = None
            return {'format': 'SEBIT-1', 'savedAt': core.now(), 'className': state['className'], 'state': snapshot,
                    'checksum': digest(json.dumps(snapshot, sort_keys=True, ensure_ascii=False))}
        return self.transaction(run)

    def restore(self, token, body):
        restored = core.validate_backup(body['backup'])
        def run(state, ctx):
            core.require(self.actor(ctx, state, token) == 'teacher', '교사만 사용할 수 있어요.')
            core.require(body['confirm'] == restored['className'], '학급 이름을 확인해 주세요.')
            password = state['teacher']
            state.clear()
            state.update(copy.deepcopy(restored))
            state.update(teacher=password, epoch=core.uid(), opened=False)
            ctx.revoke_all()
            core.tick(state)
            return {'ok': True, 'logout': True}
        return self.transaction(run)

    def status(self):
        manifest = self.root.get().to_dict() or {}
        return {key: manifest.get(key, default) for key, default in [('configured', False), ('className', ''), ('opened', False)]}

    def setup(self, body):
        # HTTP endpoint separately verifies a deployment-only setup secret.
        def run(state, ctx):
            core.require(not state['teacher'], '이미 설정된 학급이에요.')
            password = core.txt(body['password'], 200)
            core.require(len(password) >= 8, '비밀번호는 8자 이상이에요.')
            state.update(teacher=core.pw_hash(password), className=core.txt(body['className'], 50))
            ctx.revoke_all()
            return {'ok': True}
        return self.transaction(run)

    def logout(self, token):
        core.require(isinstance(token, str) and len(token) <= 200)
        return self.transaction(lambda s, c: c.put('sessions', digest(token), None))

    def touch(self, token):
        self.transaction(lambda s, c: self.actor(c, s, token, True))

    def settle(self):
        self.transaction(lambda s, c: core.tick(s))
