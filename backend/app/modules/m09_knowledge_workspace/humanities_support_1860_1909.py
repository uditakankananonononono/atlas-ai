"""Evidence-grounded humanities workbench for owner rows 1860-1909."""
from __future__ import annotations
from collections import Counter,defaultdict
from math import log
from typing import Any
NAMES=["Narrative Theory","Reader Response","Deconstruction","Psychoanalytic Criticism","Marxist Criticism","Feminist Criticism","Postcolonial Criticism","Ecocriticism","Linguistics","Phonetics","Phonology","Morphology","Syntax","Semantics","Pragmatics","Sociolinguistics","Psycholinguistics","Neurolinguistics","Historical Linguistics","Comparative Linguistics","Computational Linguistics","Corpus Linguistics","Translation Studies","Interpretation Studies","Religion","Theology","Comparative Religion","History of Religion","Sociology of Religion","Psychology of Religion","Anthropology of Religion","Mythology","Folklore","Ritual Studies","Art History","Visual Culture","Architecture","Musicology","Ethnomusicology","Film Studies","Media Studies","Performance Studies","Dance Studies","Theater Studies","Cultural Studies","Popular Culture","Subculture Studies","Museum Studies","Heritage Studies","Digital Humanities"]
FEATURES={1860+i:n for i,n in enumerate(NAMES)}
CRIT=set(range(1860,1868));LING=set(range(1868,1884));REL=set(range(1884,1894));ART=set(range(1894,1909));DH={1909}
DISCLAIMER="Interpretive and research support only. Claims are bounded to supplied evidence; qualified researchers and represented communities must review framing, context, rights and conclusions."
def _base(fid:int,d:dict)->dict:
 if fid not in FEATURES:raise ValueError('feature_id must be 1860-1909')
 corpus=d.get('sources',[])
 if not corpus:raise ValueError('sources are required')
 for s in corpus:
  if not all(s.get(k) for k in ('id','title','source_url','provenance')):raise ValueError('each source needs id, title, source_url and provenance')
 return {'feature_id':fid,'concept':FEATURES[fid],'sources':corpus,'research_question':d.get('research_question'),'assumptions':d.get('assumptions',[]),'unknowns':d.get('unknowns',[]),'review_required':True,'disclaimer':DISCLAIMER}
def _crit(fid:int,d:dict)->dict:
 o=_base(fid,d);passages=d.get('passages',[]);lens=d.get('lens',{})
 if not passages or not lens.get('principles'):raise ValueError('passages and lens principles are required')
 readings=[]
 for p in passages:
  sid=p.get('source_id');readings.append({'passage_id':p.get('id'),'source_id':sid,'quotation':p.get('quotation'),'location':p.get('location'),'observations':p.get('observations',[]),'interpretations':p.get('interpretations',[]),'counter_readings':p.get('counter_readings',[]),'source_resolved':any(s['id']==sid for s in o['sources'])})
 o.update({'lens':lens,'close_readings':readings,'reader_positions':d.get('reader_positions',[]),'boundary':'Interpretive analysis, not a single authoritative meaning. Quote locations and counter-readings remain visible; do not diagnose authors/characters or erase historical, material, gendered, colonial or ecological context.'});return o
def _ling(fid:int,d:dict)->dict:
 o=_base(fid,d);tokens=d.get('tokens',[]);annotations=d.get('annotations',[])
 if not tokens:raise ValueError('tokens are required')
 counts=Counter(str(x) for x in tokens);total=sum(counts.values());types=len(counts);entropy=-sum((n/total)*log(n/total,2) for n in counts.values()) if total else 0
 invalid=[a for a in annotations if a.get('start',-1)<0 or a.get('end',0)>len(tokens) or a.get('start',0)>=a.get('end',0)]
 o.update({'corpus_summary':{'tokens':total,'types':types,'type_token_ratio':types/total if total else None,'entropy_bits':entropy},'frequencies':dict(counts.most_common()),'annotations':annotations,'invalid_spans':invalid,'languages_or_varieties':d.get('languages_or_varieties',[]),'elicitation_or_model':d.get('elicitation_or_model',{}),'boundary':'Descriptive analysis of supplied language data. Do not infer competence, cognition, pathology, identity or social worth. Experts and speakers validate transcription, annotation, dialect, translation, model performance and cultural context.'});return o
def _religion(fid:int,d:dict)->dict:
 o=_base(fid,d);traditions=d.get('traditions',[]);claims=d.get('claims',[])
 if not traditions or not claims:raise ValueError('traditions and claims are required')
 matrix=[]
 for c in claims:
  supports=[s for s in o['sources'] if s['id'] in c.get('source_ids',[])];matrix.append({'claim':c.get('claim'),'claim_type':c.get('claim_type','descriptive'),'tradition_or_community':c.get('tradition_or_community'),'source_ids':[s['id'] for s in supports],'insider_views':c.get('insider_views',[]),'scholarly_views':c.get('scholarly_views',[]),'contested':bool(c.get('contested',False)),'evidence_status':'supported' if supports else 'unsupported'})
 o.update({'traditions':traditions,'claim_matrix':matrix,'community_review':d.get('community_review',[]),'sacred_or_restricted_material':d.get('sacred_or_restricted_material',[]),'boundary':'Comparative/descriptive scholarship, not adjudication of religious truth. Distinguish insider, theological and academic claims; avoid homogenizing traditions and honor community authority, sacred restrictions, consent and living practice.'});return o
def _arts(fid:int,d:dict)->dict:
 o=_base(fid,d);works=d.get('works',[]);contexts=d.get('contexts',[])
 if not works:raise ValueError('works are required')
 catalog=[]
 for w in works:
  evidence=[s for s in o['sources'] if s['id'] in w.get('source_ids',[])];catalog.append({'work_id':w.get('id'),'title':w.get('title'),'creator_or_community':w.get('creator_or_community'),'date_or_period':w.get('date_or_period'),'medium_or_form':w.get('medium_or_form'),'location_or_context':w.get('location_or_context'),'formal_features':w.get('formal_features',[]),'source_ids':[s['id'] for s in evidence],'attribution_status':w.get('attribution_status','unverified'),'rights':w.get('rights',{}),'interpretations':w.get('interpretations',[])})
 o.update({'catalog':catalog,'contexts':contexts,'reception_or_audiences':d.get('reception_or_audiences',[]),'community_attributions':d.get('community_attributions',[]),'boundary':'Cataloging and contextual interpretation only. Do not authenticate, appraise, claim ownership, flatten cultural specificity, expose restricted heritage, or replace creator/community attribution and rights review.'});return o
def _digital(fid:int,d:dict)->dict:
 o=_base(fid,d);records=d.get('records',[]);schema=d.get('schema',[])
 if not records or not schema:raise ValueError('records and schema are required')
 required=[f['name'] for f in schema if f.get('required')];clean=[];missing=defaultdict(list)
 for i,r in enumerate(records):
  for field in required:
   if r.get(field) in (None,''):missing[field].append(i)
  clean.append({field.get('name'):r.get(field.get('name')) for field in schema})
 edges=d.get('edges',[]);degree=Counter();
 for e in edges:degree.update([e.get('source'),e.get('target')])
 o.update({'schema':schema,'normalized_records':clean,'missing_required':dict(missing),'network_summary':{'nodes':len({x for e in edges for x in (e.get('source'),e.get('target')) if x is not None}),'edges':len(edges),'degree':dict(degree)},'transform_log':d.get('transform_log',[]),'reproducibility':d.get('reproducibility',{}),'boundary':'Reproducible analysis of supplied data only. Digitization and counts are not neutral: document selection, OCR, schemas and missingness shape results. Preserve originals, provenance, rights, community restrictions and uncertainty.'});return o
def humanities_support_1860_1909(fid:int,data:dict[str,Any])->dict[str,Any]:
 if fid in CRIT:return _crit(fid,data)
 if fid in LING:return _ling(fid,data)
 if fid in REL:return _religion(fid,data)
 if fid in ART:return _arts(fid,data)
 if fid in DH:return _digital(fid,data)
 raise ValueError('feature_id must be 1860-1909')
