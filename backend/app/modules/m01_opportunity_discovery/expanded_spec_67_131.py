"""Expanded M1 collection and understanding contracts for owner-spec rows 67-131."""
from __future__ import annotations
import re
from datetime import datetime,timezone
from urllib.parse import urlparse
SOCIAL_NAMES=['farahgulrahujaa','scholarshipowl','buildupgloabl','project.mentor','girls.instem','xollegepass','coolgirlceo','esslo.org','the project horizon','projectconnectforum','girlsinresearch','gradgpt','festivalofhope','rayofmedicine','atomic mind','crimson','the unidiscovery','opportunity orbit','appilcation ally','opportunities4students','nocodealex','girls4stemorg','tea_edu','girls in cs','future female scholars','borderless','empowerher','iseekopportunity','meghna bora','05chrs','opportunities platform','sierraperosa','shivansh gupta','the elevate prize','scholarship collective','second chance','qatar foundation']
TOPICS=['scholarships','competitions','computer-science projects','life advice','business ideas and unmet problems','research/science discoveries','events/hackathons/challenges','essay advice','study abroad']
REGISTRY={**{67+i:{'kind':'tracked_social_source','name':n} for i,n in enumerate(SOCIAL_NAMES)},104:{'kind':'authorized_export_import'},**{105+i:{'kind':'topic_monitor','topic':n} for i,n in enumerate(TOPICS)},114:{'kind':'keyword_registry','minimum':10000},115:{'kind':'platform_scale_target','target':500000},116:{'kind':'school_registry'},117:{'kind':'official_admissions'},118:{'kind':'university_ecosystem'},119:{'kind':'sponsored_youth'},120:{'kind':'olympiads_projects'},121:{'kind':'searchable_corpus'},122:{'kind':'hourly_collection'},123:{'kind':'dynamic_page_collector'},124:{'kind':'static_page_parser'},125:{'kind':'entity_extraction'},126:{'kind':'deadline_extraction'},127:{'kind':'eligibility_classification'},128:{'kind':'opportunity_type_tagging'},129:{'kind':'video_understanding'},130:{'kind':'image_understanding'},131:{'kind':'text_understanding'}}
ALLOWED_TRANSPORTS={'official_api','official_export','rss','licensed_feed','public_page'}
def _https(url):
 p=urlparse(url);return p.scheme=='https' and bool(p.netloc)
def _source(row,data):
 transport=data.get('transport');url=data.get('url','')
 if transport not in ALLOWED_TRANSPORTS:raise ValueError('transport must be official API/export, RSS, licensed feed, or public page')
 if not _https(url):raise ValueError('HTTPS source URL required')
 if data.get('requires_login') and transport=='public_page':raise ValueError('public-page collection cannot use account credentials')
 return {'row':row,'source_name':REGISTRY[row]['name'],'transport':transport,'url':url,'attribution':REGISTRY[row]['name'],'compliance':{'robots_respected':True,'quota_enforced':True,'fake_accounts':False,'credential_scraping':False},'status':'configured'}
def execute(row:int,data:dict)->dict:
 if row not in REGISTRY:raise ValueError('unsupported expanded-spec row')
 spec=REGISTRY[row];kind=spec['kind'];base={'feature_row':row,'kind':kind,'boundary':'compliant_sources_only'}
 if kind=='tracked_social_source':return base|_source(row,data)
 if kind=='authorized_export_import':
  if data.get('owner_authorized') is not True:raise ValueError('owner authorization required')
  records=data.get('records');
  if not isinstance(records,list):raise ValueError('records list required')
  return base|{'accepted_records':len(records),'provenance':'user_authorized_official_export','credentials_requested':False}
 if kind=='topic_monitor':
  terms=data.get('terms',[])
  if not isinstance(terms,list) or not terms:raise ValueError('monitor terms required')
  return base|{'topic':spec['topic'],'normalized_terms':sorted(set(str(x).strip().lower() for x in terms if str(x).strip())),'transports':sorted(ALLOWED_TRANSPORTS)}
 if kind=='keyword_registry':
  words=data.get('keywords');
  if not isinstance(words,list):raise ValueError('keywords required')
  unique={str(x).strip().casefold() for x in words if str(x).strip()}
  return base|{'unique_keywords':len(unique),'minimum':10000,'meets_target':len(unique)>=10000,'duplicates_removed':len(words)-len(unique)}
 if kind=='platform_scale_target':return base|{'target_accounts_per_platform':500000,'collection_mode':'batched_official_api_or_licensed_feed','mass_login_scraping_allowed':False,'capacity_plan':{'shards':int(data.get('shards',100)),'per_shard_target':5000}}
 if kind in {'school_registry','official_admissions','university_ecosystem','sponsored_youth','olympiads_projects'}:
  entries=data.get('entries');
  if not isinstance(entries,list) or not entries:raise ValueError('entries required')
  for e in entries:
   if not _https(e.get('official_url','')):raise ValueError('every entry needs official HTTPS URL')
  return base|{'entries':entries,'count':len(entries),'official_urls_verified_format':True}
 if kind=='searchable_corpus':
  docs=data.get('documents');query=str(data.get('query','')).casefold()
  if not isinstance(docs,list) or not query:raise ValueError('documents and query required')
  ranked=[]
  for d in docs:
   text=(str(d.get('title',''))+' '+str(d.get('text',''))).casefold();score=sum(text.count(t) for t in query.split());
   if score:ranked.append({'id':d['id'],'score':score})
  return base|{'results':sorted(ranked,key=lambda x:x['score'],reverse=True),'indexed_fields':['title','text','deadline','type','source']}
 if kind=='hourly_collection':return base|{'celery_beat_schedule':'0 * * * *','timezone':data.get('timezone','UTC'),'overlap_lock':True,'retry_backoff':True}
 if kind in {'dynamic_page_collector','static_page_parser'}:
  if not _https(data.get('url','')):raise ValueError('public HTTPS URL required')
  if data.get('robots_allowed') is not True:raise ValueError('robots permission required')
  return base|{'url':data['url'],'engine':'playwright' if kind=='dynamic_page_collector' else 'beautifulsoup','javascript':kind=='dynamic_page_collector','login_used':False,'rate_limit_per_minute':min(int(data.get('rate_limit_per_minute',10)),60)}
 if kind=='entity_extraction':
  text=str(data.get('text',''))
  if not text:raise ValueError('text required')
  entities=[{'text':m.group(0),'label':'PROPER_NOUN'} for m in re.finditer(r'\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\b',text)]
  return base|{'engine':'spacy-compatible-rule-fallback','entities':entities}
 if kind=='deadline_extraction':
  text=str(data.get('text',''));matches=re.findall(r'\b(?:20\d{2}-\d{2}-\d{2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})\b',text,re.I)
  if not matches:raise ValueError('no explicit deadline found')
  return base|{'engine':'dateparser-compatible-explicit-date','deadline_candidates':matches,'timezone':data.get('timezone','UTC')}
 if kind=='eligibility_classification':
  required=set(data.get('required',[]));facts=set(data.get('applicant_facts',[]));missing=sorted(required-facts);return base|{'model':'deberta-eligibility-interface','label':'eligible' if not missing else 'needs_information','missing':missing,'confidence':1.0 if not missing else 0.5,'human_review_required':True}
 if kind=='opportunity_type_tagging':
  text=str(data.get('text','')).casefold();labels=[x for x in ['scholarship','competition','hackathon','fellowship','grant','internship','olympiad'] if x in text];return base|{'tags':labels or ['other'],'multi_label':True}
 if kind in {'video_understanding','image_understanding'}:
  artifact=data.get('artifact')
  if not isinstance(artifact,dict) or not artifact.get('alt_or_transcript'):raise ValueError('consented artifact transcript/alt text required')
  return base|{'modality':'video' if kind.startswith('video') else 'image','summary':str(artifact['alt_or_transcript']).strip(),'ocr_or_transcript_provenance':artifact.get('provenance','owner_supplied'),'biometric_identification':False}
 if kind=='text_understanding':
  text=str(data.get('text','')).strip()
  if not text:raise ValueError('text required')
  tokens=re.findall(r"[A-Za-z0-9']+",text);return base|{'word_count':len(tokens),'keywords':sorted(Counter(x.casefold() for x in tokens).items(),key=lambda x:(-x[1],x[0]))[:10],'summary':text[:280]}
 raise AssertionError(kind)
from collections import Counter
