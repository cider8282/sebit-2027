"""Backward compatibility and multi-student job placement for the redesign."""
import copy,sys,unittest,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'functions'))
import core

class DesignCoreTests(unittest.TestCase):
    def setUp(self):
        self.s=core.initial()
        self.s['students']=[dict(id=f'p{i}',number=i,login=f'S{i:02}',name=f'학생{i}',pin='salt:hash',mustChange=False,active=True,joined=core.now(),lumen=200,xp=0,character='default') for i in (1,2)]
    def test_donation_timestamp_and_legacy_backup(self):
        core.dispatch(self.s,{},'p1','donate',{'amount':50})
        donation=self.s['donations'][0]
        self.assertIsInstance(donation['time'],int)
        self.assertEqual(self.s['students'][0]['lumen'],150)
        self.assertEqual(self.s['thermo']['total'],50)
        self.assertEqual(core.validate_backup(dict(format='SEBIT-1',state=copy.deepcopy(self.s),checksum=hashlib.sha256(json.dumps(self.s,sort_keys=True,ensure_ascii=False).encode()).hexdigest()))['donations'][0]['time'],donation['time'])
        del donation['time']
        self.assertEqual(core.validate_backup(dict(format='SEBIT-1',state=copy.deepcopy(self.s),checksum=hashlib.sha256(json.dumps(self.s,sort_keys=True,ensure_ascii=False).encode()).hexdigest()))['donations'][0]['amount'],50)
    def test_many_students_one_job_and_individual_settlement(self):
        core.dispatch(self.s,{},'teacher','jobStart',{'assignments':{'p1':'merchant','p2':'merchant'}})
        period=self.s['jobPeriods'][0]
        for sid in ('p1','p2'):
            core.dispatch(self.s,{},sid,'jobComplete',{'checks':[0,1],'memo':''})
        core.dispatch(self.s,{},'teacher','jobEnd',{'id':period['id']})
        core.dispatch(self.s,{},'teacher','jobPay',{'id':period['id']})
        self.assertEqual([p['lumen'] for p in self.s['students']],[220,220])
        self.assertEqual([p['xp'] for p in self.s['students']],[10,10])
        self.assertEqual(len([r for r in self.s['ledger'] if r['kind']=='reward']),2)

if __name__=='__main__':unittest.main()
