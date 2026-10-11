"""Predeclared finite two-group mean-effect hypothesis checks on supplied data."""
from .calibration_predictor import text
from .anchored_assessment import rows,keys
from .arithmetic_work import rational

def check(p):
 protocol=p.get('scientific_protocol')
 if not isinstance(protocol,dict):raise ValueError('scientific_protocol object required')
 ident=text(protocol.get('id'),'protocol id');hypothesis=text(protocol.get('hypothesis'),'hypothesis');source=text(protocol.get('source'),'protocol source')
 if protocol.get('predeclared')is not True:raise ValueError('explicit predeclared protocol required')
 variables={}
 for name in ['independent_variable','outcome_variable']:
  row=protocol.get(name)
  if not isinstance(row,dict):raise ValueError(name+' object required')
  variables[name]={'id':text(row.get('id'),name+' id'),'operational_definition':text(row.get('operational_definition'),name+' operational_definition'),'source':text(row.get('source'),name+' source')}
 if variables['independent_variable']['id']==variables['outcome_variable']['id']:raise ValueError('distinct operational variable IDs required')
 unit=text(protocol['outcome_variable'].get('unit'),'outcome unit');prediction=protocol.get('prediction')
 if not isinstance(prediction,dict):raise ValueError('prediction object required')
 confirm=rational(prediction.get('minimum_effect'),'minimum_effect');falsify=rational(prediction.get('falsify_at_or_below'),'falsify_at_or_below');minimum=prediction.get('minimum_per_group')
 if confirm<=falsify or type(minimum)is not int or not 1<=minimum<=128:raise ValueError('ordered disjoint effect thresholds and integer minimum_per_group[1,128] required')
 procedure=keys(protocol.get('procedure'),'procedure',minimum=1,maximum=32);controls={}
 for row in rows(protocol.get('controls'),'controls',minimum=1,maximum=32):
  key=text(row.get('id'),'control id');description=text(row.get('description'),'control description');provenance=text(row.get('source'),'control source')
  if key in controls:raise ValueError('unique control IDs required')
  controls[key]={'id':key,'description':description,'source':provenance}
 confounds={}
 for row in rows(protocol.get('confounds'),'confounds',maximum=32):
  key=text(row.get('id'),'confound id');description=text(row.get('description'),'confound description');controlled=row.get('controlled');provenance=text(row.get('source'),'confound source')
  if key in confounds or type(controlled)is not bool:raise ValueError('unique confounds with boolean controlled required')
  confounds[key]={'id':key,'description':description,'controlled':controlled,'source':provenance}
 artifacts=[];seen=set();kinds=set()
 for row in rows(protocol.get('replication_artifacts'),'replication_artifacts',maximum=16):
  kind=row.get('kind');ref=text(row.get('artifact_ref'),'artifact_ref');provenance=text(row.get('source'),'artifact source')
  if kind not in ('protocol','data','analysis')or ref in seen:raise ValueError('supported artifact kind and unique artifact_ref required')
  seen.add(ref);kinds.add(kind);artifacts.append({'kind':kind,'artifact_ref':ref,'source':provenance})
 values={'control':[],'treatment':[]};observations=[];seen=set()
 for row in rows(p.get('scientific_observations'),'scientific_observations',maximum=256):
  key=text(row.get('id'),'observation id');group=row.get('group');value=rational(row.get('value'),'observation value');provenance=text(row.get('source'),'observation source');bound=text(row.get('protocol_id'),'observation protocol_id')
  if key in seen or group not in values or bound!=ident:raise ValueError('unique observations bound to known group and exact protocol required')
  seen.add(key);values[group].append(value);observations.append({'id':key,'group':group,'value':str(value),'protocol_id':bound,'source':provenance})
 means={k:sum(v)/len(v)if v else None for k,v in values.items()};effect=means['treatment']-means['control']if all(v is not None for v in means.values())else None
 if any(v is not None and(abs(v.numerator)>10**12 or v.denominator>10**12)for v in [*means.values(),effect]):raise ValueError('computed effect/mean rational components exceed10**12')
 uncontrolled=sorted(k for k,v in confounds.items()if not v['controlled']);status='inconclusive_insufficient_data'if any(len(v)<minimum for v in values.values())else'inconclusive_uncontrolled_confounds'if uncontrolled else'confirming_supplied_data'if effect>=confirm else'disconfirming_supplied_data'if effect<=falsify else'inconclusive_supplied_data';missing=sorted({'protocol','data','analysis'}-kinds)
 return {'status':status,'protocol_id':ident,'hypothesis':hypothesis,'protocol_source':source,'variables':variables,'unit':unit,'group_counts':{k:len(v)for k,v in values.items()},'group_means':{k:str(v)if v is not None else None for k,v in means.items()},'effect':str(effect)if effect is not None else None,'prediction':{'minimum_effect':str(confirm),'falsify_at_or_below':str(falsify),'minimum_per_group':minimum},'procedure':list(protocol['procedure']),'controls':[controls[k]for k in sorted(controls)],'confounds':[confounds[k]for k in sorted(confounds)],'uncontrolled_confound_ids':uncontrolled,'observations':sorted(observations,key=lambda r:r['id']),'replication_artifacts':sorted(artifacts,key=lambda r:(r['kind'],r['artifact_ref'])),'replication_missing_kinds':missing,'replication_artifacts_complete':not missing,'replication_performed':False,'hypothesis_truth_verified':False,'predeclaration_verified':False,'source_truth_verified':False,'statistical_significance':None,'boundary':'Caller-declared preplanned two-group mean-effect thresholds on supplied exact rational data. Confirmation/disconfirmation describes these data only, not causal truth or statistical significance. Controls/confound handling/predeclaration/artifact references are declarations, not verified procedures, accessible files or completed replication.'}
