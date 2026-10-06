import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'functions'))
import core
class TeacherMessageTests(unittest.TestCase):
 def setUp(self):
  self.s=core.initial()
  self.s['students']=[dict(id=f'p{i}',number=i,login=f'S{i:02}',name=f'예시{i}',pin='salt:hash',mustChange=False,active=i<4,joined=core.now(),lumen=200,xp=10,character='default') for i in range(1,5)]
  core.dispatch(self.s,{},'p1','message',dict(title='기존 질문',body='보존할 내용'))
 def call(self,a,cmd,b):return core.dispatch(self.s,{},a,cmd,b)
 def test_group_delivery_private_replies_and_preservation(self):
  before=copy.deepcopy(self.s)
  self.call('teacher','teacherMessage',dict(students=['p1','p2','p3'],title='학급 안내',body='내일 준비물'))
  for k in before:
   if k not in ['threads','notifications']:self.assertEqual(before[k],self.s[k],k)
  self.assertEqual(before['threads'][0],self.s['threads'][0])
  threads=self.s['threads'][1:];self.assertEqual(len({t['id'] for t in threads}),3)
  for t in threads:
   view=core.project_view(self.s,t['student'])
   self.assertIn(t,view['threads']);self.assertTrue(all(x['student']==t['student'] for x in view['threads']))
   self.assertTrue(any(n['menu']=='messages' and not n['read'] for n in view['notifications']))
  t=threads[0];other=copy.deepcopy(threads[1])
  with self.assertRaises(ValueError):self.call('p2','message',dict(id=t['id'],body='다른 학생 접근'))
  self.call('p1','message',dict(id=t['id'],body='알겠습니다'));self.assertEqual(t['lastBy'],'p1');self.assertEqual(threads[1],other)
  self.call('teacher','message',dict(id=t['id'],body='좋아요'));self.assertEqual(t['lastBy'],'teacher')
  snapshot=copy.deepcopy(self.s)
  backup=dict(format='SEBIT-1',state=snapshot,checksum=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
  self.assertEqual(core.validate_backup(backup)['threads'],snapshot['threads'])
 def test_invalid_and_unauthorized_requests_leave_data_unchanged(self):
  for actor,data in [('p1',dict(students=['p2'],title='제목',body='내용')),('teacher',dict(students=[],title='제목',body='내용')),('teacher',dict(students=['p1','p1'],title='제목',body='내용')),('teacher',dict(students=['p1','p4'],title='제목',body='내용')),('teacher',dict(students=['p1','unknown'],title='제목',body='내용')),('teacher',dict(students=['p1'],title=' ',body='내용')),('teacher',dict(students=['p1'],title='제목',body=' '))]:
   before=copy.deepcopy(self.s)
   with self.assertRaises(ValueError):self.call(actor,'teacherMessage',data)
   self.assertEqual(self.s,before)
 def test_single_recipient(self):
  self.call('teacher','teacherMessage',dict(students=['p2'],title='개별 안내',body='내용'))
  self.assertEqual(len(self.s['threads']),2);self.assertEqual(self.s['threads'][-1]['student'],'p2')
if __name__=='__main__':unittest.main()
