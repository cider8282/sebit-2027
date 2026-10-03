import unittest,tempfile,sys,copy,json,hashlib,concurrent.futures
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import os
if os.environ.get('FIRESTORE_EMULATOR_HOST') != '127.0.0.1:8085':
    raise RuntimeError('Tests require the local Firestore emulator on port 8085.')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'functions'))
import core as app
from store import Store, digest
from google.cloud import firestore


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Store(firestore.Client(project='demo-sebit-test'), 'test-'+app.uid())
        def setup(s,c): s.update(teacher=app.pw_hash('Teacher123!'),className='시험 학급')
        self.db.transaction(setup); self.teacher=self.db.login('teacher','Teacher123!')['token']
        self.cmd('roster',{'rows':[{'number':1,'name':'민서'},{'number':2,'name':'지호'}]});self.cmd('open',{'value':True})
        ss=self.view()['students'];self.sid=ss[0]['id'];self.sid2=ss[1]['id'];self.student=self.db.login(ss[0]['login'],ss[0]['tempPin'])['token'];self.student2=self.db.login(ss[1]['login'],ss[1]['tempPin'])['token']
        self.cmd('pin',{'pin':'876543'},self.student);self.cmd('pin',{'pin':'876542'},self.student2)
        self.cmd('points',{'students':[self.sid,self.sid2],'lumen':3000,'xp':200})
        self.cmd('product',{'name':'지우개','price':100,'stock':20,'image':0});self.product=next(p['id'] for p in self.view()['products'] if p['name']=='지우개')
    def tearDown(self):self.tmp.cleanup()
    def cmd(self,name,data={},token=None,key=None):return self.db.command(token or self.teacher,name,data,key or app.uid())
    def view(self,token=None):return self.db.view(token or self.teacher)
    def buy(self,token=None,key=None):
        s=self.view(); p=app.get(s['products'],self.product);return self.cmd('buy',{'id':self.product,'price':app.pricing(s,p)},token or self.student,key)
    def test_idempotent_purchase(self):
        k=app.uid();self.buy(key=k);self.buy(key=k);s=self.view();self.assertEqual(len(s['items']),1);self.assertEqual(app.get(s['products'],self.product)['stock'],19)
        with self.assertRaises(ValueError):self.cmd('buy',{'id':self.product,'price':99},self.student,k)
    def test_capacity_failure_changes_nothing(self):
        for i in range(6):self.buy()
        before=self.view()
        with self.assertRaises(ValueError):self.buy()
        after=self.view();self.assertEqual(before['students'][0]['lumen'],after['students'][0]['lumen']);self.assertEqual(before['products'],after['products']);self.assertEqual(before['ledger'],after['ledger'])
    def test_concurrent_last_stock(self):
        self.cmd('product',{'id':self.product,'name':'지우개','price':100,'stock':1,'image':0})
        def attempt(t):
            try:self.buy(t);return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as e:r=list(e.map(attempt,[self.student,self.student2]))
        self.assertEqual(sum(r),1);self.assertEqual(app.get(self.view()['products'],self.product)['stock'],0)
    def test_concurrent_last_slot(self):
        for i in range(5):self.buy()
        def attempt(_):
            try:self.buy();return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:r=list(e.map(attempt,range(4)))
        self.assertEqual(sum(r),1);self.assertEqual(len(self.view()['items']),6)
    def test_expiry_and_delivery(self):
        self.buy();item=self.view()['items'][0]['id'];self.cmd('request',{'id':item},self.student)
        self.db.transaction(lambda s,c:app.get(s['items'],item).update(until=app.now()-1))
        with self.assertRaises(ValueError):self.cmd('deliver',{'id':item})
        self.assertEqual(self.view()['items'][0]['status'],'pocket');self.cmd('request',{'id':item},self.student);self.cmd('deliver',{'id':item})
        with self.assertRaises(ValueError):self.cmd('deliver',{'id':item})
        self.assertEqual(app.get(self.view()['products'],self.product)['stock'],19)
    def test_bank_maturity_wins_withdraw(self):
        self.cmd('deposit',{'amount':100},self.student);d=self.view()['deposits'][0]['id'];self.db.transaction(lambda s,c:app.get(s['deposits'],d).update(due=app.now()-1));self.view()
        with self.assertRaises(ValueError):self.cmd('withdraw',{'id':d},self.student)
        self.assertEqual(app.student(self.view(),self.sid)['lumen'],3003)
        self.view();self.assertEqual(app.student(self.view(),self.sid)['lumen'],3003)
    def test_early_withdraw_no_interest(self):
        self.cmd('deposit',{'amount':100},self.student);d=self.view()['deposits'][0]['id'];self.cmd('withdraw',{'id':d},self.student)
        self.assertEqual(app.student(self.view(),self.sid)['lumen'],3000)
    def test_reverse_exact_penalty_and_preserve_later(self):
        self.cmd('points',{'students':[self.sid],'lumen':0,'xp':-197});self.cmd('violate',{'rule':'r2','students':[self.sid]});v=self.view()['violations'][0];self.assertEqual(v['xp'],3)
        self.cmd('points',{'students':[self.sid],'lumen':7,'xp':10});self.cmd('reverse',{'id':v['ledger']});p=app.student(self.view(),self.sid);self.assertEqual((p['lumen'],p['xp']),(3007,13));self.assertTrue(self.view()['violations'][0]['cancelled'])
        with self.assertRaises(ValueError):self.cmd('reverse',{'id':v['ledger']})
    def test_donation_target_and_daily_limit_persist(self):
        self.db.transaction(lambda s,c:s['thermo'].update(total=9970))
        with self.assertRaises(ValueError):self.cmd('donate',{'amount':100},self.student)
        self.cmd('donate',{'amount':30},self.student);self.assertEqual(self.view()['thermo']['total'],10000);self.cmd('thermo',{'reset':True})
        with self.assertRaises(ValueError):self.cmd('donate',{'amount':100},self.student)
        self.cmd('donate',{'amount':70},self.student)
    def test_activity_close_once_late_add_and_repay(self):
        self.cmd('activity',{'kind':'morning'},self.student);data={'kind':'morning','date':app.day(),'students':[self.sid]};self.cmd('closeActivity',data);self.cmd('closeActivity',data)
        self.assertEqual(app.student(self.view(),self.sid)['lumen'],3010)
        with self.assertRaises(ValueError):self.cmd('activity',{'kind':'morning'},self.student)
        self.cmd('closeActivity',dict(data,students=[self.sid,self.sid2]));self.assertEqual(app.student(self.view(),self.sid2)['lumen'],3010)
        r=next(r for r in self.view()['ledger'] if r['kind']=='reward' and r['student']==self.sid);self.cmd('reverse',{'id':r['id']});self.cmd('repay',{'id':r['id']});self.cmd('repay',{'id':r['id']});self.assertEqual(app.student(self.view(),self.sid)['lumen'],3010)
    def test_citizen_cancel_recompute_reset(self):
        self.cmd('citizen',{'action':'start','reward':[30,10]});self.cmd('violate',{'rule':'r1','students':[self.sid]});self.cmd('citizen',{'action':'end'});c=self.view()['citizens'][0];self.assertNotIn(self.sid,c['eligible']);self.cmd('citizen',{'action':'pay'});v=self.view()['violations'][0];self.cmd('reverse',{'id':v['ledger']});self.cmd('citizen',{'action':'pay'});self.cmd('citizen',{'action':'pay'});self.assertEqual(app.student(self.view(),self.sid)['lumen'],3030)
        self.cmd('citizen',{'action':'reset'});self.assertEqual(self.view(self.student)['violations'],[]);self.assertEqual(len(self.view()['violations']),1)
    def test_roles_and_private_messages(self):
        self.cmd('message',{'title':'비밀','body':'개인적인 이야기'},self.student);s=self.view(self.student2);self.assertEqual(s['threads'],[])
        tid=self.view()['threads'][0]['id']
        with self.assertRaises(ValueError):self.cmd('message',{'id':tid,'body':'침입'},self.student2)
        with self.assertRaises(ValueError):self.cmd('points',{'students':[self.sid],'lumen':1000,'xp':0},self.student)
        with self.assertRaises(ValueError):self.cmd('violate',{'rule':'r1','students':[self.sid2]},self.student)
        self.assertTrue(all('pin' not in p and 'tempPin' not in p for p in self.view(self.student)['students']))
    def test_job_snapshot_and_days(self):
        self.cmd('jobStart',{'assignments':{self.sid:'helper'}});p=self.view()['jobPeriods'][0]
        self.cmd('job',{'id':'helper','name':'바뀐 이름','checklist':['바뀐 항목'],'reward':[999,999]});self.cmd('jobComplete',{'checks':[0],'memo':'끝'},self.student);self.cmd('jobEnd',{'id':p['id']});self.cmd('jobPay',{'id':p['id']});self.assertEqual(app.student(self.view(),self.sid)['lumen'],3020)
    def test_quest_once_and_reward_locked(self):
        self.cmd('quest',{'name':'미션','start':app.day(),'end':app.day(),'reward':[20,5]});q=self.view()['quests'][0]
        self.cmd('applyQuest',{'id':q['id']},self.student);a=self.view()['applications'][0];self.cmd('reviewQuest',{'id':a['id'],'approve':True})
        with self.assertRaises(ValueError):self.cmd('reviewQuest',{'id':a['id'],'approve':True})
        with self.assertRaises(ValueError):self.cmd('quest',{'id':q['id'],'name':'변경','start':app.day(),'end':app.day(),'reward':[999,999]})
    def test_new_year(self):
        self.cmd('newYear',{'confirm':'시험 학급'});s=self.db.transaction(lambda s,c:copy.deepcopy(s));self.assertEqual(s['students'],[]);self.assertFalse(s['opened']);self.assertEqual(app.get(s['products'],self.product)['stock'],0);self.assertEqual(len(s['jobs']),3)
    def test_backup_corruption_rejected(self):
        s=self.db.transaction(lambda s,c:copy.deepcopy(s));data=dict(format='SEBIT-1',state=s,checksum=hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False).encode()).hexdigest());app.validate_backup(data);s['students'][0]['lumen']=99999
        with self.assertRaises(ValueError):app.validate_backup(data)
    def test_close_and_deactivation_invalidate(self):
        self.cmd('student',{'id':self.sid,'active':False})
        with self.assertRaises(ValueError):self.view(self.student)
        self.cmd('open',{'value':False})
        with self.assertRaises(ValueError):self.view(self.student2)
    def test_idle_expiry(self):
        self.db.transaction(lambda s,c:c.put('sessions',digest(self.student),dict(c.get('sessions',digest(self.student)),seen=app.now()-180001)))
        with self.assertRaises(ValueError):self.view(self.student)
    def test_login_rate_limit_persists(self):
        for _ in range(5):
            with self.assertRaises(ValueError):self.db.login('teacher','wrong','test')
        with self.assertRaisesRegex(ValueError,'5분'):self.db.login('teacher','Teacher123!','test')

    def test_new_class_has_five_unlisted_snack_types(self):
        fresh=app.initial()
        self.assertEqual(len(fresh['products']),5)
        self.assertEqual({p['image'] for p in fresh['products']},{8,9,10,11,12})
        self.assertTrue(all(p['stock']==0 and p['price']==0 and not p['active'] for p in fresh['products']))
        self.assertEqual(fresh['students'],[])
    def test_new_snack_image_survives_purchase_request_and_delivery(self):
        self.cmd('product',{'id':self.product,'name':'곰젤리','price':100,'stock':2,'image':10,'category':'간식','active':True})
        self.buy();item=self.view(self.student)['items'][0]
        self.assertEqual(item['image'],10)
        self.cmd('request',{'id':item['id']},self.student)
        self.cmd('jobStart',{'assignments':{self.sid2:'merchant'}})
        pending=self.view(self.student2)['items'];self.assertEqual(pending[0]['image'],10)
        self.cmd('deliver',{'id':item['id']},self.student2)
        self.assertEqual(app.get(self.view()['items'],item['id'])['status'],'delivered')
    def test_unknown_product_image_rejected_without_mutation(self):
        before=self.view()['products']
        with self.assertRaises(ValueError):self.cmd('product',{'id':self.product,'name':'변경','price':1,'stock':9,'image':99})
        self.assertEqual(self.view()['products'],before)
    def test_other_students_job_corrections_are_private(self):
        self.cmd('jobStart',{'assignments':{self.sid:'helper',self.sid2:'helper'}})
        period=self.view()['jobPeriods'][0]
        self.cmd('jobAssignment',{'id':period['id'],'student':self.sid2,'job':'merchant','reason':'다른 학생의 사적인 정정 사유'})
        self.cmd('jobEnd',{'id':period['id']})
        self.cmd('jobAdjust',{'id':period['id'],'student':self.sid2,'dates':[],'reason':'다른 학생의 개인 사정'})
        student_view=self.view(self.student)['jobPeriods'][0]
        self.assertNotIn('assignmentCorrections',student_view)
        self.assertNotIn('reasons',student_view)
        self.assertEqual(set(student_view['assignments']),{self.sid})
        self.assertNotIn(self.sid2,json.dumps(student_view))
        self.assertEqual(len(self.view()['jobPeriods'][0]['assignmentCorrections']),1)
    def test_resigned_malformed_backup_rejected(self):
        def signed(state):return dict(format='SEBIT-1',state=state,checksum=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
        base=self.db.transaction(lambda s,c:copy.deepcopy(s))
        for mutation in [lambda s:s['products'][0].pop('name'),lambda s:s['products'][0].update(image=999),lambda s:s['threads'].append(dict(id='invalid',student=self.sid,title='비어 있음',closed=False,messages=[],lastBy=self.sid))]:
            with self.subTest(mutation=mutation):
                broken=copy.deepcopy(base);mutation(broken)
                with self.assertRaises((ValueError,KeyError,TypeError)):app.validate_backup(signed(broken))
        app.validate_backup(signed(base))
    def test_published_quest_text_edit_keeps_reward(self):
        self.cmd('quest',{'name':'미션','start':app.day(),'end':app.day(),'reward':[20,5]})
        quest=self.view()['quests'][0]
        self.cmd('quest',{'id':quest['id'],'name':'제목 수정','description':'설명 수정','start':app.day(),'end':app.day(),'reward':[20,5]})
        changed=self.view()['quests'][0];self.assertEqual(changed['name'],'제목 수정');self.assertEqual(changed['reward'],[20,5])

if __name__=='__main__':unittest.main(verbosity=2)
