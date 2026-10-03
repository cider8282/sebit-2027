"""Administrator-only utility. Run with project IAM credentials in Cloud Shell."""
import getpass
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
from google.cloud import firestore
import core
from store import Store

if len(sys.argv) != 2 or not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', sys.argv[1]):
    raise SystemExit('사용법: python scripts/reset_teacher.py 프로젝트ID')
db = Store(firestore.Client(project=sys.argv[1]))
if not db.status()['configured']:
    raise SystemExit('이 프로젝트에 설정된 SEBIT 학급이 없습니다. 변경하지 않았습니다.')
print('프로젝트:', sys.argv[1], '/ 학급:', db.status()['className'])
password = getpass.getpass('새 교사 비밀번호 (8~200자): ')
if not 8 <= len(password) <= 200 or password != getpass.getpass('새 비밀번호 다시 입력: '):
    raise SystemExit('길이 또는 입력 일치를 확인해 주세요. 변경하지 않았습니다.')

def reset(state, context):
    core.require(state['teacher'], '설정된 학급이 없습니다.')
    state['teacher'] = core.pw_hash(password)
    context.revoke_actor('teacher')

db.transaction(reset)
print('교사 비밀번호를 변경하고 기존 교사 세션을 종료했습니다.')
