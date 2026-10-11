"""S5.7 supplied-page labelled concept graph. No external effects."""
from datetime import date
import unicodedata
from app.modules.c30 import policy
PREFIX='VENT'
TABLES=[('SEND',{'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'}),('SPEND',{'pay','purchase','spend','buy','checkout','card_number'}),('EFFECT',{'fetch','crawl','scrape','download'}),('NOCREDS',{'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'})]
def fail(reason):raise ValueError(PREFIX+'_REFUSED_'+reason)
def walk(value):
 if type(value) is dict:
  for key,child in value.items():
   yield key
   yield from walk(child)
 elif type(value) in (list,tuple):
  for child in value:yield from walk(child)
def cap(value,limit,field):
 if len(value)>limit:fail('OVERSIZE:'+field)
def clean(value,field,limit):
 if type(value) is not str:fail('BAD_TYPE:'+field)
 cap(value,limit,field)
 if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in value):fail('CONTROL_CHARS:'+field)
 return policy.clean_text(value,PREFIX,field,limit)
def preflight(request):
 if len(request)>32:fail('OVERSIZE:request')
 pages=request.get('pages')
 if type(pages) is list:
  cap(pages,20000,'pages')
  for row in pages:
   if type(row) is dict:
    if len(row)>32:fail('OVERSIZE:request')
    for field,limit in [('id',128),('title',200)]:
     value=row.get(field)
     if type(value) is str:cap(value,limit,field)
    for field,limit in [('categories',50),('links',200)]:
     value=row.get(field)
     if type(value) is list:
      cap(value,limit,field)
      for item in value:
       if type(item) is str:cap(item,200,field)
 value=request.get('as_of')
 if type(value) is str:cap(value,10,'as_of')
 stack=[(request,0,False,32,'root')];active=set();nodes=0;normalized=set();bad_key=False
 while stack:
  node,depth,leaving,limit,context=stack.pop()
  if leaving:active.remove(id(node));continue
  if type(node) in (dict,list,tuple):nodes+=1
  if nodes>100000 or depth>32:fail('OVERSIZE:request')
  if type(node) not in (dict,list,tuple):continue
  if len(node)>limit:fail('OVERSIZE:request')
  if id(node) in active:fail('BAD_TYPE:request')
  active.add(id(node));stack.append((node,depth,True,limit,context))
  if type(node) is dict:
   for k,v in reversed(list(node.items())):
    if type(k) is not str:bad_key=True
    else:
     cap(k,200,'key')
     if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in k):fail('CONTROL_CHARS:key')
     normalized.add(k.casefold().replace('-','_'))
    child_context='generic';child_limit=32 if type(v) is dict else 64
    if context=='root' and k=='pages' and type(v) is list:child_limit=20000;child_context='pages'
    if context=='page' and k in ('categories','links') and type(v) is list:child_limit=50 if k=='categories' else 200
    stack.append((v,depth+1,False,child_limit,child_context))
  else:
   stack.extend((v,depth+1,False,32 if type(v) is dict else 64,'page' if context=='pages' else 'generic') for v in reversed(node))
 for reason,table in TABLES:
  hit=sorted(normalized & table)
  if hit:fail(reason+':'+hit[0])
 if bad_key:fail('BAD_TYPE:key')
def key(value):return ' '.join(value.casefold().split())
def run(request):
 if type(request) is not dict:fail('BAD_TYPE:request')
 preflight(request)
 if set(request)-{'as_of','pages'}:fail('UNKNOWN:request')
 pages=request.get('pages')
 if type(pages) is list:
  for row in pages:
   if type(row) is dict:
    if set(row)-{'id','title','categories','links'}:fail('UNKNOWN:pages')
    for field,value in row.items():
     if any(True for _ in walk(value)):fail('UNKNOWN:'+field)
 as_of=request.get('as_of')
 if type(as_of) is not str:fail('BAD_TYPE:as_of')
 if type(pages) is not list:fail('BAD_TYPE:pages')
 if not pages:fail('EMPTY')
 cap(pages,20000,'pages');cap(as_of,10,'as_of')
 for row in pages:
  if type(row) is not dict:fail('BAD_TYPE:pages')
  for field,limit in [('id',128),('title',200)]:
   if type(row.get(field)) is not str:fail('BAD_TYPE:'+field)
   cap(row[field],limit,field)
  for field,limit in [('categories',50),('links',200)]:
   if type(row.get(field)) is not list:fail('BAD_TYPE:'+field)
   cap(row[field],limit,field)
   for value in row[field]:
    if type(value) is not str:fail('BAD_TYPE:'+field)
    cap(value,200,field)
 clean(as_of,'as_of',10)
 try:d=date.fromisoformat(as_of)
 except ValueError:fail('BAD_TYPE:as_of')
 if d.isoformat()!=as_of:fail('BAD_TYPE:as_of')
 ids=set()
 for row in pages:
  clean(row['id'],'id',128);clean(row['title'],'title',200)
  for field in ('categories','links'):
   for value in row[field]:clean(value,field,200)
  if row['id'] in ids:fail('BAD_TYPE:pages')
  ids.add(row['id'])
 nodes={}
 for row in pages:
  k=key(row['title'])
  nodes.setdefault(k,{'key':k,'title':row['title'],'stub':False,'degree':0})
 edges=set()
 for row in pages:
  source=key(row['title'])
  for field,kind in [('categories','category'),('links','link')]:
   for value in row[field]:
    target=key(value);nodes.setdefault(target,{'key':target,'title':value,'stub':True,'degree':0});edges.add((source,target,kind))
 neighbors={k:set() for k in nodes}
 for source,target,kind in edges:
  nodes[source]['degree']+=1;nodes[target]['degree']+=1
  neighbors[source].add(target);neighbors[target].add(source)
 clusters=[];unseen=set(nodes)
 while unseen:
  start=min(unseen);todo=[start];component=set()
  while todo:
   current=todo.pop()
   if current in component:continue
   component.add(current);todo.extend(neighbors[current]-component)
  unseen-=component;clusters.append({'id':min(component),'nodes':sorted(component)})
 return {'nodes':[nodes[k] for k in sorted(nodes)],'edges':[{'source':a,'target':b,'kind':c} for a,b,c in sorted(edges)],'clusters':sorted(clusters,key=lambda x:x['id']),'top_concepts':sorted(nodes,key=lambda k:(-nodes[k]['degree'],k))[:50],'coverage':{'pages_supplied':len(pages),'nodes':len(nodes),'stubs':sum(n['stub'] for n in nodes.values()),'edges':len(edges)},'scope':policy.scope(['supplied page graph, labelled edges, degree, ranking and undirected clusters'],['semantic knowledge','live fetch','model training','universal coverage','external actions','routes'], 'supplied-page-exports',as_of)}
