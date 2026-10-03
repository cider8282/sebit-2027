import copy
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

if os.environ.get('FIRESTORE_EMULATOR_HOST') != '127.0.0.1:8085':
    raise RuntimeError('Tests require the local Firestore emulator on port 8085.')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
from flask import Flask, request
from google.cloud import firestore
import core
import main
from store import Store, Context, CHUNK_BYTES
import requests


class FirebaseHTTPTests(unittest.TestCase):
    def setUp(self):
        self.db = Store(firestore.Client(project='demo-sebit-test'), 'http-' + core.uid())
        self.origin = 'https://sebit-test.github.io'
        os.environ['SEBIT_ALLOWED_ORIGINS'] = self.origin
        self.secret = 'test-only-setup-key-more-than-24-characters'
        app = Flask(__name__)
        app.add_url_rule('/<path:path>', 'api', lambda path: main.handle(request, self.db, self.secret), methods=['GET', 'POST', 'OPTIONS'])
        self.http = app.test_client()

    def call(self, path, body=None, token=None, origin=None):
        headers = {'Origin': origin or self.origin}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        return self.http.open('/'+path, method='GET' if body is None else 'POST', json=body, headers=headers)

    def setup_class(self):
        self.assertEqual(self.call('setup', {'setupKey':self.secret,'className':'테스트','password':'Teacher123!'}).status_code, 200)
        return self.call('login', {'id':'teacher','password':'Teacher123!'}).json['token']

    def test_setup_needs_private_code_and_cannot_be_reclaimed(self):
        self.assertFalse(self.call('status').json['configured'])
        self.assertEqual(self.call('setup', {'className':'탈취','password':'Teacher123!','setupKey':'wrong'}).status_code,400)
        self.assertFalse(self.db.status()['configured'])
        self.setup_class()
        self.assertEqual(self.call('setup', {'setupKey':self.secret,'className':'탈취','password':'Teacher123!'}).status_code,400)
        self.assertEqual(self.db.status()['className'],'테스트')

    def test_cors_and_methods(self):
        self.assertEqual(self.call('status',origin='https://other.github.io').status_code,403)
        r=self.http.open('/status',method='OPTIONS',headers={'Origin':self.origin})
        self.assertEqual(r.status_code,204)
        self.assertEqual(r.headers['Access-Control-Allow-Origin'],self.origin)
        self.assertEqual(self.http.get('/status').status_code,403)
        self.assertEqual(self.http.delete('/status',headers={'Origin':self.origin}).status_code,405)

    def test_anonymous_private_data_blocked(self):
        self.setup_class()
        self.assertEqual(self.call('state').status_code,400)
        self.assertEqual(self.call('backup').status_code,400)
        self.assertEqual(self.call('command',{'command':'points','data':{},'requestId':'12345678'}).status_code,400)

    def test_backup_restore_atomic_and_revokes_sessions(self):
        teacher=self.setup_class()
        backup=self.call('backup',token=teacher).json
        self.call('command',{'command':'settings','data':{'className':'변경'},'requestId':core.uid()},teacher)
        broken=copy.deepcopy(backup);broken['state']['className']='위조'
        self.assertEqual(self.call('restore',{'backup':broken,'confirm':'위조'},teacher).status_code,400)
        self.assertEqual(self.db.status()['className'],'변경')
        self.assertEqual(self.call('restore',{'backup':backup,'confirm':'테스트'},teacher).status_code,200)
        self.assertEqual(self.db.status()['className'],'테스트')
        self.assertEqual(self.call('state',token=teacher).status_code,400)
        self.assertEqual(self.call('login',{'id':'teacher','password':'Teacher123!'}).status_code,200)

    def test_no_raw_credentials_in_response_or_firestore_session(self):
        token=self.setup_class()
        state=self.call('state',token=token).json
        self.assertNotIn('teacher',state)
        session=list(self.db.root.collection('sessions').stream())[0]
        self.assertNotEqual(session.id,token)
        self.assertNotIn(token,json.dumps(session.to_dict(),default=str))

    def test_login_limit_survives_new_store_instance_and_ip_change(self):
        self.setup_class()
        for i in range(5):
            with self.assertRaises(ValueError): self.db.login('teacher','bad','source'+str(i))
        other=Store(self.db.client,self.db.root.id)
        with self.assertRaisesRegex(ValueError,'5분'): other.login('teacher','Teacher123!','new-ip')

    def test_snapshot_larger_than_firestore_document_and_atomic_shrink(self):
        self.setup_class()
        # Incompressible payload forces several real Firestore documents.
        import secrets
        payload=secrets.token_hex(CHUNK_BYTES*3)
        self.db.transaction(lambda s,c:s['schedule'].update({'2026-10-04':{'events':payload,'meal':''}}))
        manifest=self.db.root.get().to_dict()
        self.assertGreater(len(manifest['chunks']),1)
        self.assertEqual(self.db.transaction(lambda s,c:s['schedule']['2026-10-04']['events']),payload)
        self.db.transaction(lambda s,c:s['schedule'].clear())
        self.assertEqual(len(list(self.db.root.collection('chunks').stream())),1)

    def test_readonly_status_does_not_create_classroom(self):
        self.call('status')
        self.assertFalse(self.db.root.get().exists)

    def test_firestore_rules_block_direct_anonymous_read_and_write(self):
        self.setup_class()
        url='http://127.0.0.1:8085/v1/projects/demo-sebit-test/databases/(default)/documents/'+self.db.root.path
        self.assertEqual(requests.get(url,timeout=10).status_code,403)
        self.assertEqual(requests.patch(url,json={'fields':{'configured':{'booleanValue':True}}},timeout=10).status_code,403)


if __name__ == '__main__': unittest.main()
