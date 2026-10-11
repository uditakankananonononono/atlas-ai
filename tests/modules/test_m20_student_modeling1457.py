"""Row1457 supplied-only conditional arithmetic, no learner efficacy claims."""
import copy
import importlib.util
import json
import pathlib
import unittest
P=pathlib.Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/student_modeling1457.py'
s=importlib.util.spec_from_file_location('student1457',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def request():
    return {'parameters':{'prior_mastery':.2,'learn_rate':.1,'slip':.1,'guess':.2},'events':[
        {'event_id':'e1','learner_id':'p1','skill':'s1','correct':True},
        {'event_id':'e2','learner_id':'p1','skill':'s1','correct':False}]}

class Student(unittest.TestCase):
    def refuse(self,d,code):
        with self.assertRaises(ValueError) as cm:m.run(d)
        self.assertEqual(str(cm.exception),'STUDEN1457:'+code)
    def test_exact_step_oracle(self):
        out=m.run(request());p=.2;tr=[]
        for correct in (True,False):
            num=p*(.9 if correct else .1);den=num+(1-p)*(.2 if correct else .8);post=num/den;after=post+(1-post)*.1
            tr.append((round(p,6),round(den,6),round(post,6),round(after,6)));p=after
        self.assertEqual([(r['prior'],r['likelihood'],r['posterior'],r['post_learning']) for r in out['traces']],tr)
        self.assertEqual([r['step'] for r in out['traces']],[1,2]);self.assertEqual(out['states'][0]['modeled_probability'],round(p,6))
        self.assertEqual(out['states'][0]['event_ids'],['e1','e2']);self.assertEqual(out['states'][0]['attempts'],2)
    def test_order_and_group_independence(self):
        d=request();a=m.run(d);d['events'].reverse();b=m.run(d)
        self.assertNotEqual(a['states'][0]['modeled_probability'],b['states'][0]['modeled_probability'])
        d=request();d['events'].insert(1,{'event_id':'e3','learner_id':'p2','skill':'s1','correct':False})
        o=m.run(d);self.assertEqual(o['states'][0],a['states'][0]);self.assertEqual([r['step'] for r in o['traces']],[1,1,2])
        d['events'].append({'event_id':'e4','learner_id':'p1','skill':'s2','correct':True});o=m.run(d)
        self.assertEqual(o['states'][1]['modeled_probability'],a['traces'][0]['post_learning'])
    def test_parameters_no_defaults_and_unknown(self):
        d=request();del d['parameters']['guess'];self.refuse(d,'MISSING:parameters.guess')
        d=request();d['parameters']['extra']=1;self.refuse(d,'UNKNOWN:parameters.extra')
        for k in ('parameters','events'):
            d=request();del d[k];self.refuse(d,'MISSING:request.'+k)
        d=request();d['extra']=1;self.refuse(d,'UNKNOWN:request.extra')
        d=request();d['events'][0]['extra']=1;self.refuse(d,'UNKNOWN:events[0].extra')
    def test_types_bounds_and_boolean(self):
        self.refuse(None,'BAD_TYPE:request')
        for value in (True,float('nan'),float('inf'),-.1,1.1,10**400,'0.2'):
            for key in request()['parameters']:
                d=request();d['parameters'][key]=value;self.refuse(d,'BAD_TYPE:parameters.'+key)
        for v in (None,1,0,'true',[]):
            d=request();d['events'][0]['correct']=v;self.refuse(d,'BAD_TYPE:events[0].correct')
        d=request();d['events']={};self.refuse(d,'BAD_TYPE:events')
        d=request();d['events']=[None];self.refuse(d,'BAD_TYPE:events[0]')
        d=request();d['parameters']=[];self.refuse(d,'BAD_TYPE:parameters')
    def test_identity_type_control_and_duplicate(self):
        for field in ('event_id','learner_id','skill'):
            for val in (' ','x\x00',True,None):
                d=request();d['events'][0][field]=val;self.refuse(d,'BAD_TYPE:'+field)
        d=request();d['events'][1]['event_id']='e1';self.refuse(d,'DUPLICATE:event_id')
    def test_impossible_and_probability_edges(self):
        for prior,correct in ((0,True),(1,False)):
            d=request();d['parameters'].update(prior_mastery=prior,slip=0,guess=0);d['events']=d['events'][:1];d['events'][0]['correct']=correct
            self.refuse(d,'IMPOSSIBLE:e1')
        d=request();d['parameters']['learn_rate']=1;o=m.run(d);self.assertEqual(o['states'][0]['modeled_probability'],1)
        d=request();d['parameters']['learn_rate']=0;o=m.run(d);self.assertEqual(o['traces'][0]['posterior'],o['traces'][0]['post_learning'])
        d=request();d['parameters'].update(prior_mastery=1,slip=0,guess=1);d['events']=d['events'][:1];self.assertEqual(m.run(d)['states'][0]['modeled_probability'],1)
    def test_event_n_nplus1(self):
        d=request();d['events']=[{'event_id':str(i),'learner_id':'p','skill':'s','correct':True} for i in range(1024)]
        self.assertEqual(m.run(d)['states'][0]['attempts'],1024)
        d['events'].append({'event_id':'1024','learner_id':'p','skill':'s','correct':True});self.refuse(d,'OVERSIZE:events')
    def test_pair_n_nplus1(self):
        d=request();d['events']=[{'event_id':str(i),'learner_id':'p','skill':str(i),'correct':True} for i in range(128)]
        self.assertEqual(len(m.run(d)['states']),128)
        d['events'].append({'event_id':'128','learner_id':'p','skill':'128','correct':True});self.refuse(d,'OVERSIZE:pairs')
    def test_identifier_n_nplus1(self):
        for field in ('event_id','learner_id','skill'):
            d=request();d['events'][0][field]='x'*120;m.run(d)
            d['events'][0][field]='x'*121;self.refuse(d,'OVERSIZE:'+field)
    def test_empty_deterministic_scope_and_no_mutation(self):
        d=request();before=copy.deepcopy(d);o=m.run(d);self.assertEqual(d,before);self.assertEqual(o,m.run(d));self.assertEqual(list(o),sorted(o));json.dumps(o,allow_nan=False)
        self.assertEqual(o['row_id'],1457);self.assertFalse(o['fitted_to_data']);self.assertFalse(o['learner_mastery_verified']);self.assertTrue(o['educator_review_required'])
        self.assertEqual(o['status'],'conditional_unfitted_model_calculation');self.assertEqual(o['parameter_source'],'caller');self.assertEqual(o['parameters'],d['parameters'])
        self.assertEqual([k for k,v in vars(m).items() if callable(v) and not k.startswith('_')],['run'])
        d['events']=[];self.assertEqual(m.run(d)['states'],[]);self.assertEqual(m.run(d)['traces'],[])
        self.assertIn('no educational advice or high-stakes decisions',o['scope']['limits'])

if __name__=='__main__':unittest.main(verbosity=2)
