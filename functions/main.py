"""Firebase HTTP API and scheduled settlement. Never deployed by the browser."""
import hmac
import json
import logging
import os
from functools import lru_cache

from firebase_admin import initialize_app, firestore
from firebase_functions import https_fn, scheduler_fn, options
from firebase_functions.params import SecretParam

import core
from store import Store

initialize_app()
SETUP_KEY = SecretParam('SEBIT_SETUP_KEY')
REGION = 'asia-northeast3'


@lru_cache(maxsize=1)
def database():
    return Store(firestore.client())


def response(data, status=200, origin=None):
    headers = {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
               'X-Content-Type-Options': 'nosniff', 'Vary': 'Origin'}
    if origin:
        headers.update({'Access-Control-Allow-Origin': origin,
                        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                        'Access-Control-Max-Age': '3600'})
    return https_fn.Response(json.dumps(data, ensure_ascii=False), status=status, headers=headers)


def handle(req, db=None, setup_key=None):
    allowed = set(filter(None, (s.strip() for s in os.environ.get('SEBIT_ALLOWED_ORIGINS', '').split(','))))
    origin = req.headers.get('Origin')
    if origin not in allowed:
        return response({'error': '허용된 SEBIT 주소에서 접속해 주세요.'}, 403)
    if req.method == 'OPTIONS':
        return response({}, 204, origin)
    try:
        db = db or database()
        path = req.path.rstrip('/').split('/')[-1]
        token = req.headers.get('Authorization', '').removeprefix('Bearer ')
        core.require(len(token) <= 200)
        if req.method == 'GET':
            if path == 'status':
                return response(db.status(), origin=origin)
            if path == 'state':
                return response(db.view(token), origin=origin)
            if path == 'backup':
                return response(db.backup(token), origin=origin)
            return response({'error': '찾을 수 없는 경로예요.'}, 404, origin)
        if req.method != 'POST':
            return response({'error': '허용되지 않은 요청 방식이에요.'}, 405, origin)
        raw = req.get_data(cache=True)
        core.require(0 < len(raw) <= 26_000_000, '요청 크기를 확인해 주세요.')
        body = json.loads(raw)
        core.require(isinstance(body, dict))
        if path == 'setup':
            secret = setup_key if setup_key is not None else SETUP_KEY.value
            supplied = body.get('setupKey', '')
            core.require(isinstance(supplied, str) and isinstance(secret, str) and len(secret) >= 24
                         and hmac.compare_digest(supplied, secret), '학급 개설 코드를 확인해 주세요.')
            result = db.setup(body)
        elif path == 'login':
            result = db.login(body['id'], body['password'], req.remote_addr or 'unknown')
        elif path == 'logout':
            db.logout(token)
            result = {'ok': True}
        elif path == 'touch':
            db.touch(token)
            result = {'ok': True}
        elif path == 'restore':
            result = db.restore(token, body)
        elif path == 'command':
            result = db.command(token, body['command'], body.get('data', {}), body['requestId'])
        else:
            return response({'error': '찾을 수 없는 경로예요.'}, 404, origin)
        return response(result, origin=origin)
    except ValueError as exc:
        return response({'error': str(exc)}, 400, origin)
    except (KeyError, TypeError, OverflowError, IndexError):
        return response({'error': '입력 자료를 확인해 주세요.'}, 400, origin)
    except Exception:
        logging.exception('SEBIT request failed')
        return response({'error': '서버 처리에 실패했어요. 새로고침 후 상태를 확인해 주세요.'}, 503, origin)


@https_fn.on_request(region=REGION, secrets=[SETUP_KEY], memory=options.MemoryOption.MB_512,
                     timeout_sec=120, concurrency=8, max_instances=3, invoker='public')
def sebit_api(req: https_fn.Request) -> https_fn.Response:
    return handle(req)


@scheduler_fn.on_schedule(schedule='every 1 minutes', timezone='Asia/Seoul', region=REGION,
                         memory=options.MemoryOption.MB_512, timeout_sec=120, max_instances=1)
def sebit_settle(event: scheduler_fn.ScheduledEvent) -> None:
    database().settle()
