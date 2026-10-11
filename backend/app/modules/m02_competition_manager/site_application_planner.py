"""Offline application snapshot map and grounded draft, never browser execution."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlsplit

SECRET_SUBSTRINGS=('creditcard','cardnumber','socialsecurity','ssn','password','passcode','token','secret','apikey','privatekey',
                   'routing','accountnumber','cookie','securitycode')
SECRET_EXACT={'cvv','cvv2','cvc','pin','otp','mfa','iban'}
BLOCKS={'captcha','phone','id','payment','credentials'}

def _fail(message):raise ValueError('APPPLAN: '+message)

def _text(value,name):
 if not isinstance(value,str) or not value.strip():_fail(name+' must be nonempty text')
 return value

def _url(value):
 _text(value,'URL')
 try:
  u=urlsplit(value);port=u.port
 except ValueError:_fail('malformed URL')
 if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or any(c.isspace() or ord(c)<32 for c in value):_fail('URL must be credential-free HTTPS')
 return value

class FormMap(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.fields={};self.select=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='option' and self.select:
   self.fields[self.select]['choices'].append(a.get('value',''));return
  if tag not in ('input','textarea','select'):return
  kind=a.get('type','text') if tag=='input' else tag
  if kind in ('hidden','submit','button','reset','image'):return
  identifier=a.get('id') or a.get('name')
  if not identifier:_fail('fillable control has no id or name')
  if identifier in self.fields:_fail('duplicate field identifier')
  self.fields[identifier]={'id':identifier,'tag':tag,'type':kind,'required':'required' in a,
                           'disabled':'disabled' in a,'choices':[]}
  if tag=='select':self.select=identifier
 def handle_endtag(self,tag):
  if tag=='select':self.select=None

def plan_application(*,site_url,html,facts,bindings,sources,challenges=None):
 """Build a draft from explicit bindings and source-labelled supplied answers.

 HTML blocker detection is a conservative heuristic, not complete site detection.
 Explicit observed challenges are also accepted and always stop draft filling.
 """
 site_url=_url(site_url)
 if not isinstance(html,str) or len(html)>1000000:_fail('HTML must be text at most 1000000 characters')
 if type(facts) is not dict or type(bindings) is not dict:_fail('facts and bindings must be objects')
 for key in facts:
  if not isinstance(key,str):_fail('fact keys must be strings')
  norm=re.sub('[^a-z0-9]','',key.lower())
  if norm in SECRET_EXACT or any(t in norm for t in SECRET_SUBSTRINGS):_fail('credential facts forbidden')
 if not isinstance(sources,list):_fail('sources must be a list')
 source_ids=set()
 for source in sources:
  if type(source) is not dict:_fail('source must be an object')
  identifier=_text(source.get('id'),'source id');_url(source.get('url'));_text(source.get('excerpt'),'source excerpt')
  if identifier in source_ids:_fail('duplicate source id')
  source_ids.add(identifier)
 if challenges is None:challenges=[]
 if not isinstance(challenges,list) or any(not isinstance(x,str) or x not in BLOCKS for x in challenges):_fail('unknown challenge')
 lower=html.lower();blockers=set(challenges)
 for block,pattern in [('captcha',r'recaptcha|hcaptcha|turnstile|verify you are human'),
                       ('phone',r'type\s*=\s*[\x22\x27]tel|phone verification|verify.*phone'),
                       ('id',r'passport|government.?id|identity verification'),
                       ('payment',r'payment|credit.?card|checkout|application fee'),
                       ('credentials',r'type\s*=\s*[\x22\x27]password')]:
  if re.search(pattern,lower):blockers.add(block)
 parser=FormMap();parser.feed(html);parser.close()
 draft={};missing=[]
 if not blockers:
  for field,key in bindings.items():
   if type(key) is not str:_fail('binding must name a fact key')
   if field not in parser.fields or key not in facts:_fail('binding references unknown field or fact')
   descriptor=parser.fields[field]
   if descriptor['disabled']:_fail('binding references disabled field')
   if descriptor['type'] in ('file','checkbox','radio','password','tel'):_fail('field type needs separate owner handling')
   fact=facts[key]
   if type(fact) is not dict:_fail('fact must be an object')
   value=_text(fact.get('value'),'fact value')
   if any(unicodedata.category(c) in ('Cc','Cf','Zl','Zp') for c in value):_fail('fact value contains control characters')
   refs=fact.get('source_ids')
   if not isinstance(refs,list) or not refs or any(x not in source_ids for x in refs):_fail('fact requires known source ids')
   if descriptor['choices'] and value not in descriptor['choices']:_fail('value not in declared choices')
   draft[field]=value
  missing=sorted(k for k,v in parser.fields.items() if v['required'] and not v['disabled'] and k not in draft)
 snapshot=hashlib.sha256(html.encode()).hexdigest()
 digest=hashlib.sha256(json.dumps(draft,sort_keys=True).encode()).hexdigest()
 return {'site_url':site_url,'form_map':copy.deepcopy(parser.fields),'sources':copy.deepcopy(sources),
         'draft_values':draft,'missing_required':missing,'blockers':sorted(blockers),
         'snapshot_sha256':snapshot,'draft_sha256':digest,
         'status':'blocked' if blockers else 'needs_input' if missing else 'draft_ready_for_review',
         'submission_enabled':False,'browser_action_performed':False,'source_facts_verified':False,
         'handoff':{'approval_module':'m00','mode':'proposal_only','requires_exact_review':True,
                    'site_url':site_url,'snapshot_sha256':snapshot,'draft_sha256':digest},
         'boundary':'Supplied snapshot and explicit answer bindings only; no live form fill or submit. Blocker text detection is heuristic.'}
