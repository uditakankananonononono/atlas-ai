import pytest
from app.modules.c36 import anything as a

def item(**kw):return {'id':'1','text':'tool','kind_hint':None,**kw}
def req(**kw):return {'as_of':'2026-10-11','requests':[item()],**kw}
def refuse(code,r):
 with pytest.raises(ValueError)as e:a.run(r)
 assert str(e.value)=='VENT_REFUSED_'+code
@pytest.mark.parametrize('kind,limit',[(dict,32),(list,64),(tuple,64)])
@pytest.mark.parametrize('wrap',['dict','list','tuple'])
def test_cardinality_boundaries(kind,limit,wrap):
 def request(n):
  v={str(i):0 for i in range(n)} if kind is dict else kind(range(n))
  return {'extra':v if wrap=='dict' else [v] if wrap=='list' else (v,)}
 refuse('UNKNOWN:request',request(limit));refuse('OVERSIZE:request',request(limit+1))
def test_root_and_row_key_boundaries():
 refuse('UNKNOWN:request',{str(i):0 for i in range(32)})
 refuse('OVERSIZE:request',{str(i):0 for i in range(33)})
 for n,code in [(29,'UNKNOWN:requests'),(30,'OVERSIZE:request')]:
  refuse(code,req(requests=[item(**{str(i):0 for i in range(n)})]))
@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_peak_allocation(kind):
 import tracemalloc
 v={str(i):0 for i in range(200000)} if kind is dict else kind(range(200000))
 r=v if kind is dict else {'extra':v}
 tracemalloc.start()
 try:refuse('OVERSIZE:request',r);peak=tracemalloc.get_traced_memory()[1]
 finally:tracemalloc.stop()
 assert peak<100000,peak
@pytest.mark.parametrize('field,limit',[('id',128),('text',2000),('kind_hint',200)])
def test_raw_caps_before_forbidden(field,limit):
 r=req(requests=[item(**{field:'x'*(limit+1)})]);r['token']=1
 refuse('OVERSIZE:'+field,r)
def test_count_and_date_raw_caps_before_scan():
 refuse('OVERSIZE:requests',req(requests=[{'token':1}]*1001))
 r=req(as_of='x'*11);r['token']=1;refuse('OVERSIZE:as_of',r)
def test_key_caps_and_controls():
 refuse('UNKNOWN:request',{'x'*200:1});refuse('OVERSIZE:key',{'x'*201:1})
 refuse('CONTROL_CHARS:key',{'x\u200b':1})
def test_cycles_depth_and_node_budget():
 r={};r['loop']=r;refuse('BAD_TYPE:request',r)
 def deep(n):
  v=0
  for _ in range(n):v=[v]
  return {'extra':v}
 refuse('UNKNOWN:request',deep(31));refuse('OVERSIZE:request',deep(32))
 def tree(n):
  if n==1:return []
  count=min(64,n-1);q,rem=divmod(n-1,count)
  return [tree(q+(i<rem))for i in range(count)]
 refuse('UNKNOWN:request',{'extra':tree(9999)})
 refuse('OVERSIZE:request',{'extra':tree(10000)})
@pytest.mark.parametrize('field',['id','text','kind_hint'])
@pytest.mark.parametrize('control',['\x00','\x81','\u200b','\u2028','\u2029','\n','\r','\t'])
def test_full_control_labels(field,control):
 refuse('CONTROL_CHARS:'+field,req(requests=[item(**{field:'x'+control})]))
def test_only_root_requests_list_exempt():
 for r in ({'extra':{'requests':[0]*65}},{'extra':[{'requests':[0]*65}]},{'requests':tuple(range(65))}):
  refuse('OVERSIZE:request',r)

def test_hint_boundary_and_bad_date_precedence():
 refuse('BAD_TYPE:kind_hint',req(requests=[item(kind_hint='x'*200)]))
 refuse('OVERSIZE:kind_hint',req(requests=[item(kind_hint='x'*201)]))
 r=req(as_of=5,requests=[item(text='x'*2001)]);refuse('OVERSIZE:text',r)

def test_root_and_row_caps_before_declared_scan():
 r={str(i):0 for i in range(32)};r['requests']=[{'token':1}]*1001
 refuse('OVERSIZE:request',r)
 row=item(**{str(i):0 for i in range(29)});row['text']='x'*2001;row['extra']=0
 assert len(row)==33
 refuse('OVERSIZE:request',req(requests=[row]))


@pytest.mark.parametrize('control',['\u2028','\u2029'])
def test_zl_zp_dictionary_keys(control):
 refuse('CONTROL_CHARS:key',{'bad'+control:1})


@pytest.mark.parametrize('kind',[list,dict])
def test_shared_noncyclic_references_not_cycles(kind):
 shared=kind();refuse('UNKNOWN:request',{'extra':[shared,shared]})


def test_tuple_container_budget_n_and_n_plus_one():
 def tree(n):
  if n==1:return ()
  count=min(64,n-1);q,rem=divmod(n-1,count)
  return tuple(tree(q+(i<rem))for i in range(count))
 refuse('UNKNOWN:request',{'extra':tree(9999)})
 refuse('OVERSIZE:request',{'extra':tree(10000)})
