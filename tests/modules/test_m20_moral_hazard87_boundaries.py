"""Absolute boundary pins for unchanged MORAL87 declaration inventory."""
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/moral_hazard87.py'
s=importlib.util.spec_from_file_location('moral87_bounds',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def action(i):return {'id':str(i),'observable':True,'incentive':'aligned'}
def data(n=1):return {'source_ref':'deal','actions':[action(i) for i in range(n)],'controls':[]}
def controlled(n):
    d=data(100)
    d['controls']=[{'action_id':str(i),'class':c,'source_ref':'clause'} for i in range(100) for c in ['monitoring','bonding','deductible']][:n]
    if n==301:d['controls'].append({'action_id':'0','class':'monitoring','source_ref':'extra'})
    return d
class Boundaries(unittest.TestCase):
    def refuse(self,d,message):
        with self.assertRaises(ValueError) as e:m.inventory(d)
        self.assertEqual(str(e.exception),message)
    def test_actions_absolute(self):
        self.refuse(data(0),'MORAL87: actions must be a list of 1-100 records')
        for n in [1,100]:self.assertEqual(len(m.inventory(data(n))['actions']),n)
        self.refuse(data(101),'MORAL87: actions must be a list of 1-100 records')
    def test_controls_absolute(self):
        for n in [299,300]:self.assertEqual(len(m.inventory(controlled(n))['controls']),n)
        self.refuse(controlled(301),'MORAL87: controls must be a list of at most 300 records')
    def test_controls_type_specific(self):
        for controls in ['not a list',42]:
            d=data();d['controls']=controls
            self.refuse(d,'MORAL87: controls must be a list of at most 300 records')
    def test_all_text_fields_length(self):
        for field in ['source_ref','action_id','control_source_ref']:
            for n in [199,200,201]:
                d=data();value='a'*n
                if field=='source_ref':d['source_ref']=value;label='source_ref'
                elif field=='action_id':d['actions'][0]['id']=value;label='action id'
                else:d['controls']=[{'action_id':'0','class':'monitoring','source_ref':value}];label='control source_ref'
                if n<=200:m.inventory(d)
                else:self.refuse(d,'MORAL87: '+label+' must be nonblank control-free text up to 200 characters')
    def test_control_char_and_space(self):
        for field in ['source_ref','action_id','control_source_ref']:
            for character in ['\x1f',' ']:
                d=data();value='a'+character+'b'
                if field=='source_ref':d['source_ref']=value;label='source_ref'
                elif field=='action_id':d['actions'][0]['id']=value;label='action id'
                else:d['controls']=[{'action_id':'0','class':'monitoring','source_ref':value}];label='control source_ref'
                if character==' ':m.inventory(d)
                else:self.refuse(d,'MORAL87: '+label+' must be nonblank control-free text up to 200 characters')
if __name__=='__main__':unittest.main(verbosity=2)
