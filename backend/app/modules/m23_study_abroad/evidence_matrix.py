"""Trace application requirements and essay claims to owner and official evidence."""
from __future__ import annotations
from typing import Any

def build_evidence_matrix(requirements:list[dict[str,Any]],claims:list[dict[str,Any]],owner_records:list[dict[str,Any]],official_sources:list[dict[str,Any]])->dict[str,Any]:
 owner={str(x.get('id','')):x for x in owner_records};official={str(x.get('id','')):x for x in official_sources};rows=[]
 def row(kind,item):
  oid=[str(x) for x in item.get('owner_record_ids',[])];sid=[str(x) for x in item.get('official_source_ids',[])]
  missing_owner=[x for x in oid if x not in owner];missing_official=[x for x in sid if x not in official]
  unsupported=not oid and not sid
  return {'kind':kind,'id':str(item.get('id','')),'text':str(item.get('text') or item.get('claim') or item.get('requirement') or ''),'owner_record_ids':oid,'official_source_ids':sid,'missing_owner_record_ids':missing_owner,'missing_official_source_ids':missing_official,'status':'missing_input' if unsupported or missing_owner or missing_official else 'grounded'}
 for x in requirements:rows.append(row('requirement',x))
 for x in claims:rows.append(row('essay_claim',x))
 if any(not r['id'] or not r['text'] for r in rows):raise ValueError('every requirement and claim needs an id and text')
 ids=[(r['kind'],r['id']) for r in rows]
 if len(ids)!=len(set(ids)):raise ValueError('ids must be unique within requirement/claim kind')
 missing=[{'kind':r['kind'],'id':r['id'],'needed':'owner record or official source'} for r in rows if r['status']=='missing_input']
 return {'ready':not missing,'rows':rows,'missing_inputs':missing,'coverage':round(sum(r['status']=='grounded' for r in rows)/len(rows),4) if rows else 1.0,'boundary':'Links show supplied provenance only. They do not prove admission eligibility or essay truth; reviewers must inspect source contents.'}
