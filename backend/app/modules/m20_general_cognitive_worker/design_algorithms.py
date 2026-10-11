"""Declared numeric prototype constraints and bounded scalar typed DAGs."""
from .calibration_predictor import text
from .anchored_assessment import rows,keys
from .arithmetic_work import rational

def numeric_features(value,label):
 if not isinstance(value,dict)or not 1<=len(value)<=32:raise ValueError(label+' requires1..32 numeric features')
 return {text(k,label+' key'):rational(v,label+' value')for k,v in value.items()}

def design(p):
 brief=p.get('design_brief')
 if not isinstance(brief,dict):raise ValueError('design_brief object required')
 audience=text(brief.get('audience'),'brief audience');constraints={}
 for row in rows(brief.get('constraints'),'brief constraints',minimum=1,maximum=32):
  key=text(row.get('id'),'constraint id');feature=text(row.get('feature'),'constraint feature');low=rational(row.get('minimum'),'minimum');high=rational(row.get('maximum'),'maximum');source=text(row.get('source'),'constraint source')
  if key in constraints or low>high:raise ValueError('unique constraints with minimum<=maximum required')
  constraints[key]={'feature':feature,'low':low,'high':high,'source':source}
 def violations(features):return sorted(k for k,c in constraints.items()if c['feature']not in features or not c['low']<=features[c['feature']]<=c['high'])
 prototypes={};reports=[]
 for row in rows(p.get('design_prototypes'),'design_prototypes',minimum=1,maximum=64):
  key=text(row.get('id'),'prototype id');features=numeric_features(row.get('features'),'prototype features');source=text(row.get('source'),'prototype source')
  if key in prototypes:raise ValueError('unique prototype IDs required')
  prototypes[key]={'features':features,'source':source};bad=violations(features);reports.append({'id':key,'violated_constraints':bad,'feasible':not bad,'source':source})
 feedback={}
 for row in rows(p.get('design_feedback'),'design_feedback',maximum=128):
  key=text(row.get('id'),'feedback id');base=text(row.get('prototype_id'),'feedback prototype');feature=text(row.get('feature'),'feedback feature');value=rational(row.get('suggested_value'),'suggested_value');source=text(row.get('source'),'feedback source')
  if key in feedback or base not in prototypes or feature not in prototypes[base]['features']:raise ValueError('unique feedback bound to known prototype feature required')
  feedback[key]={'prototype_id':base,'feature':feature,'value':value,'source':source}
 revisions=[];seen=set()
 for row in rows(p.get('design_revisions'),'design_revisions',maximum=64):
  key=text(row.get('id'),'revision id');base=text(row.get('base_prototype_id'),'revision base');refs=keys(row.get('feedback_ids'),'feedback_ids',minimum=1,maximum=64);changes=numeric_features(row.get('changes'),'changes');source=text(row.get('source'),'revision source')
  if key in seen or base not in prototypes or not refs<=set(feedback)or not set(changes)<=set(prototypes[base]['features']):raise ValueError('unique revisions with known base, feedback and changed features required')
  seen.add(key);wrong=sorted(k for k in refs if feedback[k]['prototype_id']!=base);unbacked=sorted(feature for feature,value in changes.items()if not any(feedback[k]['prototype_id']==base and feedback[k]['feature']==feature and feedback[k]['value']==value for k in refs));result={**prototypes[base]['features'],**changes};bad=violations(result)
  revisions.append({'id':key,'base_prototype_id':base,'feedback_ids':sorted(refs),'feedback_sources':sorted(feedback[k]['source']for k in refs),'features':{k:str(result[k])for k in sorted(result)},'wrong_prototype_feedback_ids':wrong,'unbacked_features':unbacked,'violated_constraints':bad,'supported':not(wrong or unbacked or bad),'source':source})
 return {'status':'checked','audience':audience,'prototype_reports':sorted(reports,key=lambda r:r['id']),'revision_reports':sorted(revisions,key=lambda r:r['id']),'constraint_sources':{k:constraints[k]['source']for k in sorted(constraints)},'source_truth_verified':False,'participant_validation_performed':False,'invented_prototype':None,'boundary':'Caller-supplied numeric prototypes checked against sourced interval constraints; supplied changes require same-prototype exact-value feedback and renewed constraint checks. No participant contact, empathy inference, invented design or real-world usability validation.'}

OPS={'add':('number','number'),'subtract':('number','number'),'multiply':('number','number'),'divide':('number','number'),'less_than':('number','boolean'),'equal':('same','boolean'),'and':('boolean','boolean'),'or':('boolean','boolean'),'not':('boolean','boolean'),'select':('select','branch')}

def typed(value,kind,label):
 if kind=='number':return rational(value,label)
 if type(value)is not bool:raise ValueError(label+' boolean required')
 return value

def algorithm(p):
 inputs={};types={}
 for row in rows(p.get('algorithm_inputs'),'algorithm_inputs',minimum=1,maximum=32):
  key=text(row.get('id'),'input id');kind=row.get('type')
  if key in inputs or kind not in ('number','boolean'):raise ValueError('unique typed number/boolean inputs required')
  inputs[key]=typed(row.get('value'),kind,'input value');types[key]=kind
 nodes={}
 for row in rows(p.get('algorithm_nodes'),'algorithm_nodes',maximum=64):
  key=text(row.get('id'),'node id');op=row.get('op');args=row.get('args');source=text(row.get('source'),'node source')
  count=1 if op=='not' else 3 if op=='select' else 2
  if key in types or key in nodes or op not in OPS or not isinstance(args,list)or len(args)!=count:raise ValueError('unique supported typed nodes with exact arity required')
  for arg in args:text(arg,'argument reference')
  nodes[key]={'op':op,'args':args,'source':source}
 outputs=keys(p.get('algorithm_outputs'),'algorithm_outputs',minimum=1,maximum=32)
 if not outputs<=set(inputs)|set(nodes)or any(not set(r['args'])<=set(inputs)|set(nodes)for r in nodes.values()):raise ValueError('known argument/output references required')
 order=[];pending=set(nodes)
 while pending:
  ready=sorted(k for k in pending if set(nodes[k]['args'])<=set(types))
  if not ready:raise ValueError('algorithm must be acyclic')
  for key in ready:
   row=nodes[key];kinds=[types[a]for a in row['args']];op=row['op'];required,out=OPS[op]
   if required=='select':valid=kinds[0]=='boolean'and kinds[1]==kinds[2];out=kinds[1]
   elif required=='same':valid=kinds[0]==kinds[1]
   else:valid=all(k==required for k in kinds)
   if not valid:raise ValueError('node argument type mismatch')
   types[key]=out;order.append(key);pending.remove(key)
 def evaluate(values):
  values=dict(values)
  for key in order:
   row=nodes[key];args=[values[a]for a in row['args']];op=row['op']
   if op=='add':value=args[0]+args[1]
   elif op=='subtract':value=args[0]-args[1]
   elif op=='multiply':value=args[0]*args[1]
   elif op=='divide':
    if args[1]==0:raise ValueError('algorithm division by zero')
    value=args[0]/args[1]
   elif op=='less_than':value=args[0]<args[1]
   elif op=='equal':value=args[0]==args[1]
   elif op=='and':value=args[0]and args[1]
   elif op=='or':value=args[0]or args[1]
   elif op=='not':value=not args[0]
   else:value=args[1]if args[0]else args[2]
   if types[key]=='number'and(abs(value.numerator)>10**12 or value.denominator>10**12):raise ValueError('algorithm result rational components exceed10**12')
   values[key]=value
  return {k:values[k]for k in sorted(outputs)}
 def export(values):return {k:str(v)if types[k]=='number'else v for k,v in values.items()}
 actual=evaluate(inputs);tests=[];seen=set()
 for row in rows(p.get('algorithm_tests'),'algorithm_tests',maximum=64):
  key=text(row.get('id'),'test id');source=text(row.get('source'),'test source');values=row.get('inputs');expected=row.get('expected_outputs')
  if key in seen or not isinstance(values,dict)or set(values)!=set(inputs)or not isinstance(expected,dict)or set(expected)!=outputs:raise ValueError('unique tests with exact input/output schema required')
  seen.add(key);values={k:typed(v,types[k],'test input')for k,v in values.items()};expected={k:typed(v,types[k],'expected output')for k,v in expected.items()};got=evaluate(values);tests.append({'id':key,'actual_outputs':export(got),'expected_outputs':export({k:expected[k]for k in sorted(expected)}),'passed':got==expected,'source':source})
 return {'status':'executed','outputs':export(actual),'execution_order':order,'node_sources':{k:nodes[k]['source']for k in order},'test_reports':sorted(tests,key=lambda r:r['id']),'complexity':{'model':'unit-cost arithmetic on bounded rational/boolean scalars','input_count':len(inputs),'node_count':len(nodes),'edge_count':sum(len(r['args'])for r in nodes.values()),'per_execution_steps':len(nodes),'test_execution_steps':len(nodes)*len(tests),'time_bound':'O(I + V + E) per execution; O((T+1)*(I+V+E)) including tests','space_bound':'O(I+V+E+T*O) including reports'},'source_truth_verified':False,'general_computational_thinking':None,'boundary':'Finite typed scalar number/boolean DAG execution with supplied tests. Exact bounded rationals, no loops, arbitrary code, semantic pattern discovery or proof beyond supplied cases. Complexity is unit-cost execution/reporting only, excluding validation/topological setup and rational bit costs.'}
