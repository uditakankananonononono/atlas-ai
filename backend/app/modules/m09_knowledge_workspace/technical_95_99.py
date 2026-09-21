from __future__ import annotations
from typing import Any
NODE_TYPES={'Project','Research','Competition','Application','Email','Contact','File','Deadline','Task','Note'}
EDGE_TYPES={'child_of','references','supports','blocks'}
ROWS={95:'typed_graph_nodes',96:'typed_graph_edges',97:'postgres_adjacency_list',98:'embedding_suggested_links',99:'ner_entity_linking'}
def need(d,*ks):
 m=[k for k in ks if k not in d or d[k] in ('',None)];
 if m:raise ValueError('missing required fields: '+', '.join(m))
def run(row:int,d:dict[str,Any]):
 if row not in ROWS:raise ValueError('unsupported row')
 if row==95:
  need(d,'nodes');bad=[x for x in d['nodes'] if x.get('type') not in NODE_TYPES];r={'nodes':d['nodes'],'allowed_types':sorted(NODE_TYPES),'invalid_ids':[x.get('id') for x in bad],'valid':not bad}
 elif row==96:
  need(d,'edges','node_ids');ids=set(d['node_ids']);bad=[x for x in d['edges'] if x.get('type') not in EDGE_TYPES or x.get('from_id') not in ids or x.get('to_id') not in ids or x.get('from_id')==x.get('to_id')];r={'edges':d['edges'],'allowed_types':sorted(EDGE_TYPES),'invalid_edge_ids':[x.get('id') for x in bad],'valid':not bad}
 elif row==97:
  need(d,'tenant_id','nodes','edges');r={'schema':{'nodes':['id','tenant_id','type','payload','created_at','updated_at'],'edges':['id','tenant_id','from_id','to_id','type','payload','created_at']},'tenant_id':d['tenant_id'],'node_rows':d['nodes'],'edge_rows':d['edges'],'foreign_keys_required':True,'tenant_predicate_required':True,'persisted':False}
 elif row==98:
  need(d,'entity_id','entity_vector','candidates','threshold');
  def cos(a,b):
   import math
   if len(a)!=len(b):raise ValueError('embedding dimension mismatch')
   den=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/den if den else 0
  scored=[{'candidate_id':x['id'],'score':cos(d['entity_vector'],x['vector']),'suggested_type':x.get('suggested_type','references')} for x in d['candidates']];r={'entity_id':d['entity_id'],'suggestions':[x for x in sorted(scored,key=lambda x:x['score'],reverse=True) if x['score']>=float(d['threshold'])],'auto_created':False}
 else:
  need(d,'text','mentions','entities');idx={(x.get('type'),x.get('normalized_name')):x for x in d['entities']};links=[]
  for m in d['mentions']:
   x=idx.get((m.get('type'),m.get('normalized_name')));links.append({'mention':m,'entity_id':x.get('id') if x else None,'status':'linked' if x else 'unresolved'})
  r={'text':d['text'],'links':links,'unresolved_count':sum(x['status']=='unresolved' for x in links),'deadline_normalization_requires_timezone':True,'auto_created':False}
 return {'row':row,'requirement':ROWS[row],'result':r}
