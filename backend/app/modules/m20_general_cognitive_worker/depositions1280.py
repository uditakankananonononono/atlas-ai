"""Supplied-reference bookkeeping only. No legal conclusions or effects."""
from datetime import date
import re
import unicodedata

BOUNDARY='Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.'
TOP={'row','as_of','entries'}
ENTRY={'element','status','source_ref','entry_date'}
TABLES=(('SEND',{'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'}),('SPEND',{'pay','purchase','spend','buy','checkout','card_number'}),('EFFECT',{'file','serve','send','contact','submit','execute','advise','settle'}),('NOCREDS',{'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'}))
class Legal1280Refusal(ValueError):pass

def run(request):
 row,prefix,vocabulary,limits=ROW,PREFIX,VOCAB,LIMITS
 def fail(reason,field):raise Legal1280Refusal(prefix+' '+reason+':'+field)
 def raw(v,field,limit):
  if type(v) is str and len(v)>limit:fail('OVERSIZE',field)
 def text(v,field,limit):
  if type(v) is not str:fail('BAD_TYPE',field)
  raw(v,field,limit)
  if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in v):fail('CONTROL_CHARS',field)
  return v
 def day(v,field):
  v=text(v,field,10)
  if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',v):fail('BAD_TYPE',field)
  try:return date.fromisoformat(v)
  except ValueError:fail('BAD_TYPE',field)
 if type(request) is not dict:fail('BAD_TYPE','request')
 if len(request)>32:fail('OVERSIZE','request')
 entries=request.get('entries')
 if type(entries) is list:
  if len(entries)>200:fail('OVERSIZE','entries')
  for entry in entries:
   if type(entry) is dict:
    if len(entry)>32:fail('OVERSIZE','request')
    for field,cap in (('element',200),('status',200),('source_ref',200),('entry_date',10)):raw(entry.get(field),field,cap)
 raw(request.get('as_of'),'as_of',10)
 stack=[(request,0,False,32)];active=set();nodes=0;hits=[];bad_key=False
 while stack:
  node,depth,leaving,cap=stack.pop()
  if leaving:active.remove(id(node));continue
  if type(node) in (dict,list,tuple):nodes+=1
  if nodes>10000 or depth>32:fail('OVERSIZE','request')
  if type(node) not in (dict,list,tuple):continue
  if len(node)>cap:fail('OVERSIZE','request')
  if id(node) in active:fail('BAD_TYPE','request')
  active.add(id(node));stack.append((node,depth,True,cap))
  if type(node) is dict:
   for key,value in reversed(list(node.items())):
    if type(key) is not str:bad_key=True
    else:
     text(key,'key',200);norm=key.casefold().replace('-','_')
     for rank,(reason,table)in enumerate(TABLES):
      if norm in table:hits.append((rank,norm,reason))
    child_cap=200 if depth==0 and key=='entries' and type(value) is list else (32 if type(value) is dict else 64)
    stack.append((value,depth+1,False,child_cap))
  else:stack.extend((value,depth+1,False,32 if type(value) is dict else 64)for value in reversed(node))
 if hits:
  _,key,reason=min(hits);fail(reason,key)
 if bad_key:fail('BAD_TYPE','key')
 if set(request)-TOP:fail('UNKNOWN','request')
 if type(entries) is list:
  for entry in entries:
   if type(entry) is dict and set(entry)-ENTRY:fail('UNKNOWN','entries')
 supplied_row=request.get('row')
 if type(supplied_row) is not int:fail('BAD_TYPE','row')
 if supplied_row!=row:fail('UNKNOWN','row')
 as_of=day(request.get('as_of'),'as_of')
 if type(entries) is not list:fail('BAD_TYPE','entries')
 if not entries:fail('EMPTY','entries')
 seen=set();records=[]
 for entry in entries:
  if type(entry) is not dict:fail('BAD_TYPE','entries')
  element=text(entry.get('element'),'element',200)
  status=text(entry.get('status'),'status',200)
  if element not in vocabulary:fail('UNKNOWN','element')
  if status not in ('supplied','missing','disputed'):fail('UNKNOWN','status')
  ref=entry.get('source_ref')
  if status=='missing':
   if ref is not None:fail('BAD_TYPE','source_ref')
  else:
   ref=text(ref,'source_ref',200)
   if not ref.strip():fail('BAD_TYPE','source_ref')
  stamp=None
  if 'entry_date' in entry:
   stamp=day(entry['entry_date'],'entry_date')
   if stamp>as_of:fail('BAD_TYPE','entry_date')
  duplicate=(element,status,ref)
  if duplicate in seen:fail('BAD_TYPE','entries')
  seen.add(duplicate);records.append((element,status,stamp))
 elements=[];coverage={'elements_total':len(vocabulary),'referenced':0,'disputed':0,'declared_missing':0,'unaddressed':0}
 for element in vocabulary:
  chosen=[r for r in records if r[0]==element];statuses={r[1]for r in chosen}
  state='disputed' if 'disputed' in statuses else 'referenced' if 'supplied' in statuses else 'declared_missing' if 'missing' in statuses else 'unaddressed'
  latest=max((r[2]for r in chosen if r[2] is not None),default=None)
  coverage[state]+=1
  elements.append({'element':element,'status':state,'also_declared_missing':'missing' in statuses,'latest_entry_date':latest.isoformat() if latest else None,'days_since_latest':(as_of-latest).days if latest else None})
 scope={'implemented':['declared element supplied-reference bookkeeping'],'not_implemented':list(limits)+['legal conclusions','reference verification','external effects'],'data_source':'caller supplied entries only','as_of':request['as_of']}
 scope['jurisdiction']='jurisdiction not supplied or validated'
 return {'row':row,'elements':elements,'coverage':coverage,'counsel_review_required':True,'legal_conclusion':False,'references_verified':False,'boundary':BOUNDARY,'scope':scope}

ROW=1280
PREFIX='DEPOSI1280:'
VOCAB=('witness_topics', 'exhibits', 'record_support', 'privilege_flags', 'noncoaching_boundaries')
LIMITS=('no testimony coaching or privilege determination',)
