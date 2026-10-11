"""Declaration inventory, not simulated moral-hazard prevention."""
import importlib.util
from pathlib import Path
import unittest
import copy
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/moral_hazard87.py'
s=importlib.util.spec_from_file_location('moral87',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def request():
    return {'source_ref':'deal-1','actions':[{'id':'maintain','observable':False,'incentive':'misaligned'},{'id':'report','observable':True,'incentive':'unknown'}],
            'controls':[{'action_id':'maintain','class':'bonding','source_ref':'clause-2'}]}
class Tests(unittest.TestCase):
    def test_exact_gaps_and_classes(self):
        r=m.inventory(request())
        self.assertEqual(r['action_gaps'],[{'action_id':'maintain','missing_classes':['monitoring','deductible']},{'action_id':'report','missing_classes':['monitoring','bonding','deductible']}])
        self.assertEqual(r['unobservable_action_ids'],['maintain'])
        self.assertEqual(r['misaligned_action_ids'],['maintain'])
        self.assertEqual(r['unknown_incentive_action_ids'],['report'])
        self.assertEqual(r['declared_class_counts'],{'monitoring':0,'bonding':1,'deductible':0})
        self.assertFalse(r['controls_effective_verified'])
    def test_complete_presence_is_not_effectiveness(self):
        d=request();d['controls']=[{'action_id':a['id'],'class':c,'source_ref':'clause'} for a in d['actions'] for c in ['monitoring','bonding','deductible']]
        r=m.inventory(d);self.assertTrue(r['all_declared_classes_present']);self.assertFalse(r['controls_effective_verified'])
    def test_deterministic_no_alias(self):
        d=request();snap=copy.deepcopy(d);r=m.inventory(d)
        d['actions'].reverse();d['controls'].reverse();self.assertEqual(r,m.inventory(d))
        self.assertEqual(snap['controls'],d['controls'])
        r['controls'][0]['source_ref']='changed';self.assertEqual(d['controls'][0]['source_ref'],'clause-2')
    def refuse(self,d):
        with self.assertRaisesRegex(ValueError,'^MORAL87:'):m.inventory(d)
    def test_types_unknown_fields_and_observability(self):
        for bad in [None,[],{},dict(request(),extra=True)]:self.refuse(bad)
        for value in ['yes',1,None]:
            d=request();d['actions'][0]['observable']=value;self.refuse(d)
        for value in ['',None,3,'bad\nref']:
            d=request();d['source_ref']=value;self.refuse(d)
        d=request();d['actions'][0]['extra']=1;self.refuse(d)
    def test_duplicate_or_unknown_references(self):
        d=request();d['actions'].append(copy.deepcopy(d['actions'][0]));self.refuse(d)
        d=request();d['controls'][0]['action_id']='unknown';self.refuse(d)
        d=request();d['controls'].append(copy.deepcopy(d['controls'][0]));self.refuse(d)
    def test_exact_classes_and_incentives(self):
        for c in ['insurance','Monitoring','',None]:
            d=request();d['controls'][0]['class']=c;self.refuse(d)
        for c in ['yes','',1,None]:
            d=request();d['actions'][0]['incentive']=c;self.refuse(d)
    def test_empty_and_bounds(self):
        d=request();d['actions']=[];self.refuse(d)
        d=request();d['controls']=[];self.assertEqual(m.inventory(d)['declared_class_counts'],{'monitoring':0,'bonding':0,'deductible':0})
        d=request();d['actions']=[{'id':str(i),'observable':True,'incentive':'aligned'} for i in range(100)];d['controls']=[]
        self.assertEqual(len(m.inventory(d)['actions']),100)
        d['actions'].append({'id':'extra','observable':True,'incentive':'aligned'});self.refuse(d)
if __name__=='__main__':unittest.main(verbosity=2)
