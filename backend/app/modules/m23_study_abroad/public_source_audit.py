"""Public-source metadata registry and robots audit, not an essay corpus.

No page bodies, cookies, signups or licensed-content claims. The prior M23
source-only reading boundary is preserved. DNS preflight is not a rebinding
security guarantee; this tool accepts only the fixed reviewed registry.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.robotparser import RobotFileParser

USER_AGENT='AtlasCaseResearch/1.0'
MAX_ROBOTS_BYTES=500000
REGISTRY=Path(__file__).with_name('public_source_registry_v1.json')
FIELDS=('id','publisher','url','evidence_type','outcome_basis','example_school')

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def _url(value):
 if type(value)is not str:raise ValueError('URL must be text')
 p=urlparse(value)
 if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None,443):raise ValueError('HTTPS public URL required')
 if '.' not in p.hostname:raise ValueError('public hostname required')
 try:ipaddress.ip_address(p.hostname)
 except ValueError:pass
 else:raise ValueError('IP literals not allowed')
 return p

def normalize_sources(rows,required_count=None):
 if type(rows)is not list or not 1<=len(rows)<=20:raise ValueError('one through twenty sources required')
 if required_count is not None and len(rows)!=required_count:raise ValueError('required source count mismatch')
 ids=set();hosts=set();out=[]
 for row in rows:
  if type(row)is not dict:raise ValueError('source must be dict')
  for f in FIELDS:
   if f=='example_school' and row.get(f) is None:continue
   if type(row.get(f))is not str or not row[f].strip() or len(row[f])>2000 or any(ord(c)<32 for c in row[f]):raise ValueError('invalid field: '+f)
  if not re.fullmatch(r'[a-z0-9_-]{1,80}',row['id']):raise ValueError('invalid source id')
  host=_url(row['url']).hostname.lower().removeprefix('www.')
  if row['id'] in ids or host in hosts:raise ValueError('duplicate source identity or host')
  ids.add(row['id']);hosts.add(host)
  out.append({**{f:row[f] for f in FIELDS},'schema_version':'1','reading_mode':'publisher_page',
   'outcome_status':'source_reported_not_independently_verified','license_status':'not_granted',
   'terms_status':'unreviewed','body_collection_allowed':False,'training_rights_granted':False})
 return out

def robots_decision(text,url):
 if type(text)is not str or not text.strip() or '<html' in text.lower() or not re.search(r'^\s*user-agent\s*:',text,re.I|re.M):return {'status':'robots_unverified','pace_seconds':2}
 parser=RobotFileParser();parser.parse(text.splitlines())
 delay=parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or 2
 return {'status':'robots_allowed' if parser.can_fetch(USER_AGENT,url) else 'robots_denied','pace_seconds':max(2,delay)}

def summarize(records):
 return {'schema_version':'1','checked_source_count':len(records),'status_counts':dict(Counter(r['robots_status'] for r in records)),
  'collected_case_count':0,'essay_bodies_collected':0,'scope':'robots_audited_derived_registry_only',
  'limitation':'Robots permission is not a license or terms clearance. No publisher cleared for product-side body collection.'}

def audit_registry(rows):
 sources=normalize_sources(rows,required_count=20);records=[];opener=build_opener(NoRedirect())
 for source in sources:
  p=_url(source['url']);robots_url='https://'+p.netloc+'/robots.txt'
  r={**source,'checked_at':datetime.now(timezone.utc).isoformat(),'robots_url':robots_url,'robots_status':'robots_unverified','page_body_fetched':False}
  try:
   addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
   if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('non-public DNS')
   request=Request(robots_url,headers={'User-Agent':USER_AGENT,'Accept':'text/plain'})
   with opener.open(request,timeout=10) as response:
    r['http_status']=response.status
    if response.status==200:
     data=response.read(MAX_ROBOTS_BYTES+1)
     if len(data)>MAX_ROBOTS_BYTES:r['failure']='robots_size_cap'
     else:
      text=data.decode('utf-8',errors='strict');decision=robots_decision(text,source['url'])
      r['robots_status']=decision['status'];r['pace_seconds']=decision['pace_seconds']
      # Hash is audit integrity, not permission. No content retained.
      import hashlib
      r['robots_sha256']=hashlib.sha256(data).hexdigest()
  except HTTPError as exc:r.update(http_status=exc.code,failure='http_refusal_or_redirect')
  except (URLError,TimeoutError,ValueError,UnicodeError,OSError):r['failure']='network_or_validation_failure'
  records.append(r)
  time.sleep(2) # distinct hosts, only one robots request per site; no retries
 return {'summary':summarize(records),'records':records}

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
 rows=json.loads(REGISTRY.read_text(encoding='utf-8'))
 result=audit_registry(rows);Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps(result['summary']))
if __name__=='__main__':main()
