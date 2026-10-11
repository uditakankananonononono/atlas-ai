"""S5.7 supplied-page labelled concept graph. No external effects."""
from datetime import date
from app.modules.c30 import policy
PREFIX='VENT'
TABLES=[('SEND',{'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'}),('SPEND',{'pay','purchase','spend','buy','checkout','card_number'}),('EFFECT',{'fetch','crawl','scrape','download'}),('NOCREDS',{'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'})]
def fail(reason):raise ValueError(PREFIX+'_REFUSED_'+reason)
def walk(value):
 if isinstance(value,dict):
  for key,child in value.items():
   yield key
   yield from walk(child)
 elif isinstance(value,list):
  for child in value:yield from walk(child)
def cap(value,limit,field):
 if len(value)>limit:fail('OVERSIZE:'+field)
def clean(value,field,limit):return policy.clean_text(value,PREFIX,field,limit)
def key(value):return ' '.join(value.casefold().split())
def run(request):
 if not isinstance(request,dict):fail('BAD_TYPE:request')
 keys=list(walk(request));normalized={k.casefold().replace('-','_') for k in keys if isinstance(k,str)}
 for reason,table in TABLES:
  hit=sorted(normalized & table)
  if hit:fail(reason+':'+hit[0])
 if any(not isinstance(k,str) for k in keys):fail('BAD_TYPE:key')
 if set(request)-{'as_of','pages'}:fail('UNKNOWN:request')
 pages=request.get('pages')
 if isinstance(pages,list):
  for row in pages:
   if isinstance(row,dict):
    if set(row)-{'id','title','categories','links'}:fail('UNKNOWN:pages')
    for field,value in row.items():
     if any(True for _ in walk(value)):fail('UNKNOWN:'+field)
 as_of=request.get('as_of')
 if not isinstance(as_of,str):fail('BAD_TYPE:as_of')
 if not isinstance(pages,list):fail('BAD_TYPE:pages')
 if not pages:fail('EMPTY')
 cap(pages,20000,'pages');cap(as_of,10,'as_of')
 for row in pages:
  if not isinstance(row,dict):fail('BAD_TYPE:pages')
  for field,limit in [('id',128),('title',200)]:
   if not isinstance(row.get(field),str):fail('BAD_TYPE:'+field)
   cap(row[field],limit,field)
  for field,limit in [('categories',50),('links',200)]:
   if not isinstance(row.get(field),list):fail('BAD_TYPE:'+field)
   cap(row[field],limit,field)
   for value in row[field]:
    if not isinstance(value,str):fail('BAD_TYPE:'+field)
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
