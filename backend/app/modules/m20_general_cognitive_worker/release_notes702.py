"""Row 702: strict supplied-change release-draft bookkeeping, no execution."""
import copy
import hashlib
import json
import unicodedata

def fail(reason):raise ValueError('RELEAS702: '+reason)
def text(value):
 if type(value) is not str or len(value)>1000 or not value.strip() or any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in value):fail('text must be 1..1000 characters without controls')
 return value
def sequence(value):
 if type(value) is not list:fail('list required')
 if len(value)>10000:fail('list exceeds 10000')
 return value
def plan_release(request):
 """No source truth, completeness, quality or release authority is verified."""
 if type(request) is not dict:fail('request must be object')
 if len(request)!=5:fail('request fields invalid')
 if any(type(key) is not str for key in request):fail('unknown field')
 if set(request)!={'version','audience','changes','upgrade_steps','known_issues'}:fail('request fields invalid')
 version=text(request['version']);audience=text(request['audience']);changes=sequence(request['changes'])
 upgrades=[text(x) for x in sequence(request['upgrade_steps'])];issues=[text(x) for x in sequence(request['known_issues'])]
 rows=[];ids=set()
 for row in changes:
  if type(row) is not dict or len(row)!=4:fail('change fields invalid')
  if any(type(key) is not str for key in row):fail('unknown field')
  if set(row)!={'id','description','user_visible','breaking'}:fail('change fields invalid')
  ident=text(row['id']);description=text(row['description'])
  if type(row['user_visible']) is not bool or type(row['breaking']) is not bool:fail('flag must be bool')
  if ident in ids:fail('duplicate change id')
  ids.add(ident);rows.append({'id':ident,'description':description,'user_visible':row['user_visible'],'breaking':row['breaking']})
 highlights=[{'id':r['id'],'description':r['description']} for r in rows if r['user_visible']]
 breaking=[{'id':r['id'],'description':r['description']} for r in rows if r['breaking']]
 digest=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 return {'version':version,'audience':audience,'highlights':highlights,'breaking_changes':breaking,'upgrade_steps':upgrades,'known_issues':issues,'generated_from_change_ids':[r['id'] for r in rows],'snapshot_sha256':digest,'status':'draft_only','published':False,'repository_verified':False,'release_authorized':False,'scope':'Supplied change list only; no completeness, quality, impact or release-authority claim.'}
