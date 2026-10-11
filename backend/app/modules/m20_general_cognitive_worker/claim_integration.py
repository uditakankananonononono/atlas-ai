"""Explicit finite claim conflicts and supplied-premise/frame resolution checks."""
from .calibration_predictor import text
from .anchored_assessment import rows,keys

def check(mode,p):
 schema=p.get('reasoning_schema')
 if not isinstance(schema,dict)or not 1<=len(schema)<=32:raise ValueError('reasoning_schema requires1..32 features')
 domains={}
 for key,values in schema.items():
  text(key,'schema feature');domains[key]=keys(values,'schema values',minimum=1,maximum=16)
 frames={}
 for row in rows(p.get('reasoning_frames'),'reasoning_frames',minimum=1,maximum=16):
  key=text(row.get('id'),'frame id');source=text(row.get('source'),'frame source');constraints=[]
  if key in frames:raise ValueError('unique frame IDs required')
  for c in rows(row.get('constraints'),'frame constraints',maximum=32):
   feature=text(c.get('feature'),'constraint feature');allowed=keys(c.get('allowed_values'),'constraint values',minimum=1,maximum=16);provenance=text(c.get('source'),'constraint source')
   if feature not in domains or not allowed<=domains[feature]:raise ValueError('known constraint feature and schema values required')
   constraints.append({'feature':feature,'allowed_values':allowed,'source':provenance})
  frames[key]={'constraints':constraints,'source':source}
 claims={};assumptions={};all_ids=set()
 for label,bank in [('reasoning_claims',claims),('reasoning_assumptions',assumptions)]:
  for row in rows(p.get(label),label,minimum=1 if label=='reasoning_claims' else 0,maximum=128):
   key=text(row.get('id'),label+' id');feature=text(row.get('feature'),label+' feature');value=text(row.get('value'),label+' value');source=text(row.get('source'),label+' source')
   if key in all_ids or feature not in domains or value not in domains[feature]:raise ValueError('globally unique evidence IDs with schema feature/value required')
   frame=None
   if label=='reasoning_claims':
    frame=text(row.get('frame_id'),'claim frame')
    if frame not in frames:raise ValueError('known claim frame required')
   all_ids.add(key);bank[key]={'id':key,'feature':feature,'value':value,'source':source,'frame_id':frame}
 conflicts=[]
 for feature in sorted(domains):
  ids=sorted(k for k,r in claims.items()if r['feature']==feature);values=sorted({claims[k]['value']for k in ids})
  if len(values)>1:conflicts.append({'feature':feature,'values':values,'claim_ids':ids})
 reports=[];seen=set();evidence={**claims,**assumptions};resolved=set()
 for row in rows(p.get('reasoning_resolutions'),'reasoning_resolutions',maximum=128):
  key=text(row.get('id'),'resolution id');feature=text(row.get('feature'),'resolution feature');value=text(row.get('value'),'resolution value');source=text(row.get('source'),'resolution source');premises=keys(row.get('premise_ids'),'premise_ids',minimum=1,maximum=64);covers=keys(row.get('resolves_claim_ids'),'resolves_claim_ids',minimum=1,maximum=128)
  if key in seen or feature not in domains or value not in domains[feature]or not premises<=set(evidence)or not covers<=set(claims):raise ValueError('unique resolutions with known schema and evidence references required')
  seen.add(key);wrong_feature=sorted(k for k in covers if claims[k]['feature']!=feature);required=set(next((c['claim_ids']for c in conflicts if c['feature']==feature),[]));uncovered=sorted(required-covers)
  supporting=sorted(k for k in premises if evidence[k]['feature']==feature and evidence[k]['value']==value);contradicting=sorted(k for k in premises if evidence[k]['feature']==feature and evidence[k]['value']!=value)
  violated=sorted(k for k,f in frames.items()if any(c['feature']==feature and value not in c['allowed_values']for c in f['constraints']))if mode=='integrative_thinking'else []
  supported=bool(required)and bool(supporting)and not(contradicting or wrong_feature or uncovered or violated)
  if supported:resolved.add(feature)
  reports.append({'id':key,'feature':feature,'value':value,'premise_ids':sorted(premises),'premise_sources':sorted(evidence[k]['source']for k in premises),'resolves_claim_ids':sorted(covers),'supporting_premise_ids':supporting,'contradicting_premise_ids':contradicting,'uncovered_claim_ids':uncovered,'wrong_feature_claim_ids':wrong_feature,'violated_frames':violated,'supported':supported,'source':source})
 # Multiple incompatible supported resolutions cannot silently select a winner.
 competing=sorted(feature for feature in resolved if len({r['value']for r in reports if r['feature']==feature and r['supported']})>1)
 unresolved=sorted({c['feature']for c in conflicts}-resolved|set(competing))
 return {'status':'no_conflicts'if not conflicts else 'no_supported_resolution'if unresolved else 'supported_resolution','contradictions':conflicts,'resolution_reports':sorted(reports,key=lambda r:r['id']),'unresolved_features':unresolved,'competing_resolution_features':competing,'claims':[claims[k]for k in sorted(claims)],'assumptions':[assumptions[k]for k in sorted(assumptions)],'frames':[{'id':k,'source':frames[k]['source'],'constraints':[{'feature':c['feature'],'allowed_values':sorted(c['allowed_values']),'source':c['source']}for c in frames[k]['constraints']]}for k in sorted(frames)],'source_truth_verified':False,'invented_synthesis':None,'boundary':'Finite sourced schema feature/value contradictions and caller-supplied resolutions only. A resolution must cite agreeing premises without same-feature contrary premises, cover all conflicting claims and, for integration, satisfy every supplied frame constraint. Competing supported values stay unresolved. No independent truth, novel synthesis or real-world conflict resolution.'}
