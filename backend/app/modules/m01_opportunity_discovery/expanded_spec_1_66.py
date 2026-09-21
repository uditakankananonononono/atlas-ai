"""Compliant source registry and normalization for expanded owner-spec M1 rows 1-66."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from urllib.parse import urlparse
import re
from typing import Any
class SourceRegistryError(ValueError):pass
SOURCE_NAMES={1:'Kaggle RSS',2:'Devpost API',3:'Unstop',4:'Opportunity Desk',5:'Opportunities for Youth',6:'Snowday',7:'Hack Club',8:'GitHub Topics',9:'LinkedIn jobs',10:'Instagram hashtags',11:'Twitter/X lists',12:'Reddit r/competitions',13:'Reddit r/scholarships',14:'Discord channels',15:'Custom webhooks',16:'Girls on Campus',17:'Institute of Competition Sciences',18:'Bold.org',19:'Unigo',20:'Fastweb',21:'JoinSucceed.com',22:'Top-college and company hackathon channels',23:'Tata Imagination Challenge',24:'Samsung Solve for Tomorrow',25:'Google opportunities',26:'Scholarships360',27:'Scholarships.com',28:'Exactly 200 scholarship sites'}
SOCIAL=['mila yilin','covacut','code with dino','jamesdyson award','buildwbrendan','design4me','imangadzhi','kennethchiba','college with_hari','students$_success','nadsbennani','careergirlglobal','ashleyprado29','bridgeupfutures','eduall.official','scholarshipcollegemama','posse foundation','the college navigator','youth scholarships','tutor.inc',"fatimah's guide",'open doors for students org','esther funds foundation','science olympiad','ultimate ivy league guide','connect me tutoring','think global scholarship','coke scholars','kolllgeio.ai','study for you bestie','questbridge','scholarship.junkie','for finance hub','adroiteducation','the university network','opportunities_corners','ivy brothers','essayswithavigail']
ROWS={**SOURCE_NAMES,**{29+i:n for i,n in enumerate(SOCIAL)}}
def slug(s):return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
MODES={1:'rss',2:'official_api',8:'official_api',9:'official_api_or_user_export',10:'official_api_or_public_page',11:'official_api_or_public_list',12:'official_api',13:'official_api',14:'user_authorized_export_or_webhook',15:'signed_webhook'}
PUBLIC_DEFAULT={i:'public_page' for i in range(3,29)}
MODE={**PUBLIC_DEFAULT,**MODES,**{i:'official_api_export_or_public_page' for i in range(29,67)}}
# Registry entries are intentionally declarative: callers provide fetched records from a permitted transport.
def capabilities():return [{'row_id':i,'key':slug(n),'name':n,'kind':('source_adapter' if i<=28 else 'tracked_social_source'),'access_mode':MODE[i]} for i,n in ROWS.items()]
def get_source(row_id:int):
 if row_id not in ROWS:raise SourceRegistryError(f'unknown row_id: {row_id}')
 return next(x for x in capabilities() if x['row_id']==row_id)
def validate_transport(row_id:int,transport:str,authorized:bool=False):
 allowed={MODE[row_id]}
 expansions={'official_api_or_user_export':{'official_api','user_export'},'official_api_or_public_page':{'official_api','public_page'},'official_api_or_public_list':{'official_api','public_list'},'user_authorized_export_or_webhook':{'user_export','webhook'},'official_api_export_or_public_page':{'official_api','user_export','public_page'}}
 allowed=expansions.get(MODE[row_id],allowed)
 if transport not in allowed:raise SourceRegistryError(f'transport {transport} is not permitted for {ROWS[row_id]}')
 if transport in {'user_export','webhook'} and not authorized:raise SourceRegistryError(f'{transport} requires user authorization')
 return {'permitted':True,'transport':transport,'robots_and_terms_review_required':transport in {'public_page','public_list'},'no_login_mass_scraping':True,'no_evasion':True}
def normalize(row_id:int,record:dict[str,Any],*,transport:str,authorized:bool=False):
 if not isinstance(record,dict):raise SourceRegistryError('record must be an object')
 policy=validate_transport(row_id,transport,authorized)
 title=str(record.get('title','')).strip();url=str(record.get('url','')).strip()
 if not title:raise SourceRegistryError('record.title is required')
 parsed=urlparse(url)
 if parsed.scheme not in {'http','https'} or not parsed.netloc:raise SourceRegistryError('record.url must be http(s)')
 observed_at=record.get('observed_at') or datetime.now(timezone.utc).isoformat()
 identity=sha256(f"{row_id}|{url.lower()}|{title.lower()}".encode()).hexdigest()[:24]
 deadline=record.get('deadline')
 return {'id':identity,'source_row_id':row_id,'source_name':ROWS[row_id],'source_key':slug(ROWS[row_id]),'title':title,'url':url,'summary':str(record.get('summary','')).strip(),'deadline':deadline,'location':record.get('location'),'eligibility':record.get('eligibility',[]),'tags':record.get('tags',[]),'observed_at':observed_at,'transport':transport,'provenance':{'canonical_url':url,'publisher':record.get('publisher') or parsed.netloc,'retrieved_via':transport},'policy':policy,'raw_reference':record.get('raw_reference')}
def normalize_batch(row_id:int,records:list[dict[str,Any]],*,transport:str,authorized:bool=False):
 if not isinstance(records,list):raise SourceRegistryError('records must be a list')
 validate_transport(row_id,transport,authorized)
 seen={};errors=[]
 for index,r in enumerate(records):
  try:
   item=normalize(row_id,r,transport=transport,authorized=authorized);seen[item['id']]=item
  except SourceRegistryError as exc:errors.append({'index':index,'error':str(exc)})
 return {'source':get_source(row_id),'items':list(seen.values()),'errors':errors,'received':len(records),'accepted':len(seen),'deduplicated':len(records)-len(errors)-len(seen)}
def validate_scholarship_registry(sites:list[dict[str,Any]]):
 if not isinstance(sites,list):raise SourceRegistryError('sites must be a list')
 domains=[];problems=[]
 for i,s in enumerate(sites):
  url=s.get('url','') if isinstance(s,dict) else '';d=urlparse(url).netloc.lower().removeprefix('www.')
  if not d:problems.append({'index':i,'error':'valid url required'})
  elif d in domains:problems.append({'index':i,'error':'duplicate domain'})
  else:domains.append(d)
 return {'required_count':200,'valid_unique_count':len(domains),'complete':len(domains)==200 and not problems,'problems':problems,'domains':domains,'boundary':'Only verified, permitted scholarship sources count; placeholders never count toward 200.'}
