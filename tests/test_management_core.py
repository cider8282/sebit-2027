import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'functions'))
import core
class ManagementTests(unittest.TestCase):
 def setUp(self):
  self.s=core.initial();self.s['students']=[dict(id='p1',number=1,login='S01',name='예시',pin='salt:hash',mustChange=False,active=True,joined=core.now(),lumen=200,xp=0,character='default')]
  core.dispatch(self.s,{},'teacher','quest',dict(name='보존 테스트',description='내용',start=core.day(),end=core.day(),reward=[20,10]))
  self.q=self.s['quests'][0]['id']
 def call(self,actor,cmd,b):return core.dispatch(self.s,{},actor,cmd,b)
 def backup(self):
  state=copy.deepcopy(self.s);return core.validate_backup(dict(format='SEBIT-1',state=state,checksum=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False).encode()).hexdigest()))
 def test_legacy_backup_and_removal_preserve_rewards_records(self):
  self.backup();self.call('p1','applyQuest',{'id':self.q});aid=self.s['applications'][0]['id']
  self.call('teacher','reviewQuest',{'id':aid,'approve':True});self.call('teacher','quest',{'id':self.q,'action':'ended'})
  before=copy.deepcopy(self.s);self.call('teacher','quest',{'id':self.q,'action':'remove'})
  for k in before:
   if k!='quests':self.assertEqual(self.s[k],before[k],k)
  self.assertEqual(len(self.s['quests']),1);self.assertTrue(self.s['quests'][0]['listRemoved']);self.assertEqual(len(core.project_view(self.s,'p1')['quests']),0)
  self.assertTrue(self.backup()['quests'][0]['listRemoved'])
  self.call('teacher','quest',{'id':self.q,'action':'copy'});self.assertNotIn('listRemoved',self.s['quests'][-1])
 def test_pending_active_and_student_removal_blocked(self):
  with self.assertRaises(ValueError):self.call('teacher','quest',{'id':self.q,'action':'remove'})
  self.call('p1','applyQuest',{'id':self.q});self.call('teacher','quest',{'id':self.q,'action':'ended'})
  for actor in ['teacher','p1']:
   with self.assertRaises(ValueError):self.call(actor,'quest',{'id':self.q,'action':'remove'})
  self.assertNotIn('listRemoved',self.s['quests'][0])
 def test_thread_delete_only_closed_teacher_and_preserves_other_data(self):
  self.call('p1','message',{'title':'질문','body':'학생 내용'});t=self.s['threads'][0]['id']
  with self.assertRaises(ValueError):self.call('teacher','threadDelete',{'id':t})
  self.call('teacher','message',{'id':t,'body':'교사 답장'});self.call('teacher','thread',{'id':t,'closed':True})
  with self.assertRaises(ValueError):self.call('p1','threadDelete',{'id':t})
  before=copy.deepcopy(self.s);self.call('teacher','threadDelete',{'id':t})
  self.assertEqual(self.s['threads'],[])
  for k in before:
   if k!='threads':self.assertEqual(self.s[k],before[k],k)
  self.assertEqual(self.backup()['threads'],[])
if __name__=='__main__':unittest.main()
