import importlib.util
from pathlib import Path
import sys
import pytest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/c36/blueprint.py'
spec=importlib.util.spec_from_file_location('s51_delta',P);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
def niche(**kw):return {'id':'n','name':'Tool','audience':'students','problem':'planning','price_points':[19],'currency':'USD','regulated_flags':[],'channels':['email'],'worker_roles':['writer','critic'],**kw}
def req(**kw):return {'as_of':'2026-10-11','niches':[niche()],**kw}
def refuse(code,r):
 with pytest.raises(ValueError)as e:m.run(r)
 assert str(e.value)==code


def test_count_before_forbidden_scan():
 refuse('VENT_REFUSED_OVERSIZE:niches',req(niches=[{'token':'x'}]*2001))


@pytest.mark.parametrize('field,limit',[('price_points',20),('channels',20),('worker_roles',12),('regulated_flags',10)])
def test_nested_count_before_scan(field,limit):
 refuse('VENT_REFUSED_OVERSIZE:'+field,req(niches=[niche(**{field:[{'token':'x'}]*(limit+1)})]))


@pytest.mark.parametrize('char',['\x00','\x81','\u200b','\u2028','\u2029'])
@pytest.mark.parametrize('field',['id','name','audience','problem','currency'])
def test_full_unicode_refusal(field,char):
 refuse('VENT_REFUSED_CONTROL_CHARS:'+field,req(niches=[niche(**{field:'X'+char})]))


@pytest.mark.parametrize('field',['channels','worker_roles','regulated_flags'])
def test_list_text_cf_refusal(field):
 refuse('VENT_REFUSED_CONTROL_CHARS:'+field,req(niches=[niche(**{field:['x\u200b']})]))


def test_zs_preserved_and_no_funnel():
 out=m.run(req(niches=[niche(name='\u00a0Tool\u00a0')]))
 assert out['blueprints'][0]['offer'].startswith('\u00a0Tool\u00a0:')
 assert 'funnel' not in out['blueprints'][0]


class DictSub(dict):pass
class ListSub(list):pass
class StrSub(str):pass
class IntSub(int):pass
class FloatSub(float):pass


@pytest.mark.parametrize('field,value,reason',[
 ('id',StrSub('n'),'id'),('currency',StrSub('USD'),'currency'),
 ('channels',ListSub(['email']),'channels'),('worker_roles',[StrSub('writer')],'worker_roles'),
 ('price_points',[IntSub(19)],'price_points'),('price_points',[FloatSub(19)],'price_points')])
def test_exact_leaf_types(field,value,reason):refuse('VENT_REFUSED_BAD_TYPE:'+reason,req(niches=[niche(**{field:value})]))


def test_exact_container_boundaries():
 refuse('VENT_REFUSED_BAD_TYPE:request',DictSub(req()))
 refuse('VENT_REFUSED_BAD_TYPE:niches',req(niches=ListSub([niche()])))
 refuse('VENT_REFUSED_BAD_TYPE:niches',req(niches=[DictSub(niche())]))
 refuse('VENT_REFUSED_BAD_TYPE:as_of',req(as_of=StrSub('2026-10-11')))


def test_raw_list_leaf_caps_before_policy():
 for field in ('channels','worker_roles'):
  refuse('VENT_REFUSED_OVERSIZE:'+field,req(niches=[niche(**{field:['x'*201+'\x00']})]))


def test_large_int_is_bad_type_not_overflow():
 refuse('VENT_REFUSED_BAD_TYPE:price_points',req(niches=[niche(price_points=[10**400])]))


def test_container_node_budget_n_and_n_plus_one():
 def tree(nodes):
  if nodes==1:return []
  children=min(64,nodes-1);q,rem=divmod(nodes-1,children)
  return [tree(q+(i<rem))for i in range(children)]
 refuse('VENT_REFUSED_UNKNOWN:request',{'extra':tree(9999)})
 refuse('VENT_REFUSED_OVERSIZE:request',{'extra':tree(10000)})


def test_depth32_and33():
 def nested(depth):
  node='leaf'
  for _ in range(depth):node={'x':node}
  return node
 refuse('VENT_REFUSED_UNKNOWN:request',nested(32))
 refuse('VENT_REFUSED_OVERSIZE:request',nested(33))


def test_cycle_clean_refusal():
 r={};r['loop']=r
 refuse('VENT_REFUSED_BAD_TYPE:request',r)


def test_key_raw_cap_and_controls_before_membership():
 refuse('VENT_REFUSED_UNKNOWN:request',req(**{'x'*200:1}))
 refuse('VENT_REFUSED_OVERSIZE:key',req(**{'x'*201:1}))
 refuse('VENT_REFUSED_CONTROL_CHARS:key',req(**{'token\u200b':1}))


def test_currency_raw_caps_even_without_prices():
 for prices in ([],[1]):
  refuse('VENT_REFUSED_OVERSIZE:currency',req(niches=[niche(price_points=prices,currency='USDD')]))
  assert m.run(req(niches=[niche(price_points=prices,currency='USD')]))['blueprints']


def test_asof_raw_9_10_11():
 refuse('VENT_REFUSED_BAD_TYPE:as_of',req(as_of='2026-1-11'))
 assert m.run(req())['scope']['as_of']=='2026-10-11'
 refuse('VENT_REFUSED_OVERSIZE:as_of',req(as_of='2026-10-11\n'))


@pytest.mark.parametrize('field',['id','name','audience','problem','currency'])
def test_raw_caps_beat_table_scan(field):
 cap=3 if field=='currency' else 200
 n=niche(**{field:'x'*(cap+1)});n['token']='x'
 refuse('VENT_REFUSED_OVERSIZE:'+field,req(niches=[n]))


def test_real_floor_imports():
 from app.auth import context
 from app.core import providers,database,approvals
 for module in (context,providers,database,approvals):assert '/backend/app/' in module.__file__


def test_asof_raw_cap_precedes_forbidden_scan():
 refuse('VENT_REFUSED_OVERSIZE:as_of',req(as_of='2026-10-11x',token='x'))


def test_exact_key_and_flag_types():
 r=req();r[StrSub('extra')]=1
 refuse('VENT_REFUSED_BAD_TYPE:key',r)
 refuse('VENT_REFUSED_BAD_TYPE:regulated_flags',req(niches=[niche(regulated_flags=[StrSub('review')])]))


def test_shared_reference_is_not_a_cycle():
 shared=[]
 refuse('VENT_REFUSED_UNKNOWN:request',{'a':shared,'b':shared})


def test_role_edges_only_with_both_endpoints():
 out=m.run(req(niches=[niche(worker_roles=['researcher','analyst','writer','critic','auditor','builder','Writer',' writer'])]))
 graph=out['blueprints'][0]['worker_graph']
 assert graph['edges']==[{'from':'analyst','to':'writer'},{'from':'builder','to':'critic'},{'from':'critic','to':'auditor'},{'from':'researcher','to':'analyst'},{'from':'writer','to':'critic'}]
 assert graph['isolated']==[' writer','Writer']


@pytest.mark.parametrize('field,limit',[('price_points',20),('channels',20),('worker_roles',12),('regulated_flags',10)])
@pytest.mark.parametrize('key_place',['niche','top','nested'])
@pytest.mark.parametrize('bad_key',['x'*201,'bad\u200b'])
def test_preflight_list_counts_beat_raw_bad_keys(field,limit,key_place,bad_key):
 n=niche(**{field:['x']*(limit+1)});r=req(niches=[n])
 if key_place=='niche':n[bad_key]=1
 elif key_place=='top':r[bad_key]=1
 else:r['extra']={bad_key:1}
 refuse('VENT_REFUSED_OVERSIZE:'+field,r)


@pytest.mark.parametrize('field',['channels','worker_roles'])
def test_leaf_exact_200_and201_cap_before_earlier_control(field):
 assert m.run(req(niches=[niche(**{field:['x'*200]})]))['blueprints']
 refuse('VENT_REFUSED_OVERSIZE:'+field,req(niches=[niche(name='bad\x00',**{field:['x'*201]})]))


def test_flag50_and51_before_earlier_name_control():
 assert m.run(req(niches=[niche(),niche(id='r',regulated_flags=['x'*50])]))['regulated_review']==[{'id':'r','status':'regulated_review_needed'}]
 refuse('VENT_REFUSED_OVERSIZE:regulated_flags',req(niches=[niche(name='bad\x00',regulated_flags=['x'*51])]))


@pytest.mark.parametrize('shape',['list_in_dict','leaf'])
def test_depth_boundary_mixed_and_leaf(shape):
 def value(depth):
  node=[] if shape=='list_in_dict' else 'leaf'
  for _ in range(depth):node={'x':node}
  return node
 # Pure preflight boundary, independently from unknown-schema refusal.
 m._preflight(value(32))
 with pytest.raises(ValueError)as e:m._preflight(value(33))
 assert str(e.value)=='VENT_REFUSED_OVERSIZE:request'


@pytest.mark.parametrize('prices',[5,None,True,{}])
def test_nonlist_prices_safe_reason(prices):
 refuse('VENT_REFUSED_BAD_TYPE:price_points',req(niches=[niche(price_points=prices)]))


@pytest.mark.parametrize('container',[list,tuple])
def test_sequence_branch_depth32_and33_direct(container):
 def nest(edges):
  node='leaf'
  for _ in range(edges):node=container([node])
  return node
 m._preflight({"extra":nest(31)})
 with pytest.raises(ValueError)as e:m._preflight({"extra":nest(32)})
 assert str(e.value)=='VENT_REFUSED_OVERSIZE:request'


@pytest.mark.parametrize('container',[list,tuple])
def test_sequence_branch_depth_real_worker_roles(container):
 def roles(edges):
  # request0/niches1/niche2/worker_roles3, then edges into sequences/scalar
  node='leaf'
  for _ in range(edges-1):node=container([node])
  return [node]
 refuse('VENT_REFUSED_BAD_TYPE:worker_roles',req(niches=[niche(worker_roles=roles(29))]))
 refuse('VENT_REFUSED_OVERSIZE:request',req(niches=[niche(worker_roles=roles(30))]))


@pytest.mark.parametrize('kind,limit',[(dict,32),(list,64),(tuple,64)])
def test_generic_cardinality_boundaries(kind,limit):
 def node(n):return {str(i):0 for i in range(n)} if kind is dict else kind(range(n))
 refuse('VENT_REFUSED_UNKNOWN:request',{'extra':node(limit)})
 refuse('VENT_REFUSED_OVERSIZE:request',{'extra':node(limit+1)})


def test_root_cardinality_boundary():
 refuse('VENT_REFUSED_UNKNOWN:request',{str(i):0 for i in range(32)})
 refuse('VENT_REFUSED_OVERSIZE:request',{str(i):0 for i in range(33)})


@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_cardinality_before_materialization(monkeypatch,kind):
 import builtins
 hostile={str(i):0 for i in range(100000)} if kind is dict else kind(range(100000))
 request=hostile if kind is dict else {'extra':hostile}
 visited=[]
 def spy(value):
  assert len(value)<=64,'oversized node reached materialization/traversal'
  visited.append(len(value));return builtins.reversed(value)
 monkeypatch.setattr(m,'reversed',spy,raising=False)
 refuse('VENT_REFUSED_OVERSIZE:request',request)
 assert visited==([] if kind is dict else [1])


def _node(kind,n):return {str(i):0 for i in range(n)} if kind is dict else kind(range(n))


@pytest.mark.parametrize('kind,limit',[(dict,32),(list,64),(tuple,64)])
@pytest.mark.parametrize('wrap',['list','tuple','deep'])
def test_cardinality_boundary_for_elements_inside_sequences(kind,limit,wrap):
 def put(n):
  v=_node(kind,n)
  return {'extra':[v] if wrap=='list' else (v,) if wrap=='tuple' else [[v]]}
 refuse('VENT_REFUSED_UNKNOWN:request',put(limit))
 refuse('VENT_REFUSED_OVERSIZE:request',put(limit+1))


@pytest.mark.parametrize('shape',['nested_dict','in_list','in_niche','root_tuple'])
def test_only_root_niches_list_uses_declared_cap(shape):
 big=[0]*65
 r={'nested_dict':{'extra':{'niches':big}},'in_list':{'extra':[{'niches':big}]},'in_niche':{'niches':[{'niches':big}]},'root_tuple':{'niches':tuple(range(65))}}[shape]
 refuse('VENT_REFUSED_OVERSIZE:request',r)


import tracemalloc
@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_cardinality_peak_allocation_bounded(kind):
 hostile=_node(kind,200000);request=hostile if kind is dict else {'extra':hostile}
 tracemalloc.start()
 try:refuse('VENT_REFUSED_OVERSIZE:request',request);peak=tracemalloc.get_traced_memory()[1]
 finally:tracemalloc.stop()
 assert peak<100_000,peak
