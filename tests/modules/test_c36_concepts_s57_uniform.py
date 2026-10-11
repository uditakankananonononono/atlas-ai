import importlib.util
from pathlib import Path
import pytest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/c36/concepts.py'
s=importlib.util.spec_from_file_location('s57_uniform',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def page(**kw):return {'id':'1','title':'A','categories':[],'links':[],**kw}
def req(**kw):return {'as_of':'2026-10-11','pages':[page()],**kw}
def refuse(code,r):
 with pytest.raises(ValueError)as e:m.run(r)
 assert str(e.value)=='VENT_REFUSED_'+code
class D(dict):pass
class L(list):pass
class S(str):pass
@pytest.mark.parametrize('field,value',[('request',D(req())),('pages',L([page()])),('row',D(page())),('as_of',S('2026-10-11')),('id',S('1')),('title',S('A')),('categories',L([])),('links',L([])),('entry',S('B'))])
def test_exact_boundaries(field,value):
 if field=='request':r=value
 elif field in ('pages','as_of'):r=req(**{field:value})
 elif field=='row':r=req(pages=[value])
 elif field=='entry':r=req(pages=[page(links=[value])])
 else:r=req(pages=[page(**{field:value})])
 refuse('BAD_TYPE:'+('pages' if field=='row' else 'links' if field=='entry' else field),r)
@pytest.mark.parametrize('control',['\x00','\x81','\u200b','\u2028','\u2029','\n','\r','\t'])
def test_all_label_controls(control):refuse('CONTROL_CHARS:title',req(pages=[page(title='A'+control)]))
def test_caps_before_forbidden_and_content():
 r=req(pages=[page(title='x'*201)]);r['token']=1
 refuse('OVERSIZE:title',r)
 refuse('OVERSIZE:links',req(pages=[page(title='A\u200b',links=['x']*201)]))
@pytest.mark.parametrize('kind,cap',[(dict,32),(list,64),(tuple,64)])
def test_generic_cardinality(kind,cap):
 def node(n):return {str(i):0 for i in range(n)} if kind is dict else kind(range(n))
 refuse('UNKNOWN:request',{'extra':node(cap)})
 refuse('OVERSIZE:request',{'extra':node(cap+1)})
@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_materialization(monkeypatch,kind):
 import builtins
 hostile={str(i):0 for i in range(100000)} if kind is dict else kind(range(100000))
 r=hostile if kind is dict else {'extra':hostile}
 def spy(v):
  assert len(v)<=64,'uncapped traversal'
  return builtins.reversed(v)
 monkeypatch.setattr(m,'reversed',spy,raising=False)
 refuse('OVERSIZE:request',r)
def test_cycles_and_depth():
 r={};r['loop']=r;refuse('BAD_TYPE:request',r)
 def nested(n):
  x=0
  for _ in range(n):x=[x]
  return {'extra':x}
 refuse('UNKNOWN:request',nested(31));refuse('OVERSIZE:request',nested(32))
def test_key_caps_controls_and_subclass():
 refuse('UNKNOWN:request',{'x'*200:1});refuse('OVERSIZE:key',{'x'*201:1})
 refuse('CONTROL_CHARS:key',{'x\u200b':1});refuse('BAD_TYPE:key',{S('x'):1})

def test_container_budget_n_and_n_plus_one():
 def tree(n):
  if n==1:return []
  count=min(64,n-1);q,rem=divmod(n-1,count)
  return [tree(q+(i<rem))for i in range(count)]
 refuse('UNKNOWN:request',{'extra':tree(99999)})
 refuse('OVERSIZE:request',{'extra':tree(100000)})
def test_shared_references_and_cap_precedence():
 shared=[];refuse('UNKNOWN:request',{'extra':[shared,shared]})
 refuse('OVERSIZE:pages',req(pages=[{'token':1}]*20001))
 refuse('OVERSIZE:as_of',req(as_of='x'*11,pages=[page(title='x\u200b')]))
@pytest.mark.parametrize('field,limit',[('categories',50),('links',200)])
def test_schema_list_cap_beats_forbidden(field,limit):
 r=req(pages=[page(**{field:[{'token':1}]*(limit+1)})])
 refuse('OVERSIZE:'+field,r)

def test_root_cardinality_precedes_known_scan():
 r={str(i):0 for i in range(32)};r['pages']=[{'token':1}]*20001
 refuse('OVERSIZE:request',r)
 r={str(i):0 for i in range(31)};r['pages']=[{'token':1}]*20001
 refuse('OVERSIZE:pages',r)
def test_entry_and_date_raw_caps_before_controls():
 r=req(pages=[page(links=['x'*201])]);r['token']=1
 refuse('OVERSIZE:links',r)
 r=req(as_of='x'*11);r['token']=1
 refuse('OVERSIZE:as_of',r)


@pytest.mark.parametrize('shape',['page_dict','list','tuple','categories','links','deep_dict'])
def test_hostile_peak_allocation_bounded(shape):
 import tracemalloc
 if shape in ('page_dict','deep_dict'):
  hostile={str(i):0 for i in range(200000)}
 elif shape=='tuple':hostile=tuple(range(200000))
 else:hostile=list(range(200000))
 if shape=='page_dict':request=req(pages=[hostile])
 elif shape in ('categories','links'):request=req(pages=[page(**{shape:hostile})])
 elif shape=='deep_dict':request={'extra':[[{'deep':hostile}]]}
 else:request={'extra':hostile}
 code='OVERSIZE:'+shape if shape in ('categories','links') else 'OVERSIZE:request'
 tracemalloc.start()
 try:
  refuse(code,request);peak=tracemalloc.get_traced_memory()[1]
 finally:tracemalloc.stop()
 assert peak<100000,peak


def _p(**kw):return {'id':'1','title':'A','categories':[],'links':[],**kw}
def _r(pages,**kw):return {'as_of':'2026-10-11','pages':pages,**kw}


def test_root_key_boundary_32_33():
 refuse('UNKNOWN:request',{str(i):0 for i in range(32)})
 refuse('OVERSIZE:request',{str(i):0 for i in range(33)})


@pytest.mark.parametrize('extra,code',[(28,'UNKNOWN:pages'),(29,'OVERSIZE:request')])
def test_page_row_key_boundary_32_33(extra,code):
 row=_p(**{'x%d'%i:0 for i in range(extra)})
 assert len(row)==4+extra and (len(row)==32 or len(row)==33)
 refuse(code,_r([row]))


def test_dict_inside_sequence_boundary_32_33():
 refuse('UNKNOWN:pages',_r([_p(x=[{str(i):0 for i in range(32)}])]))
 refuse('OVERSIZE:request',_r([_p(x=[{str(i):0 for i in range(33)}])]))


def test_raw_id_cap_before_control_scan():
 refuse('OVERSIZE:id',_r([_p(id='a'*128+'\x00')]))
 refuse('CONTROL_CHARS:id',_r([_p(id='a'*127+'\x00')]))


@pytest.mark.parametrize('value,code',[('', 'EMPTY:as_of'),(5,'BAD_TYPE:as_of'),(None,'BAD_TYPE:as_of'),('2026-10-11\n','OVERSIZE:as_of'),('2026-10-1\n','CONTROL_CHARS:as_of'),('2026-13-01','BAD_TYPE:as_of')])
def test_as_of_reasons(value,code):
 r=_r([_p()]);r['as_of']=value
 refuse(code,r)


def test_missing_as_of_bad_type():
 r=_r([_p()]);del r['as_of'];refuse('BAD_TYPE:as_of',r)


@pytest.mark.parametrize('field',['categories','links'])
def test_entry_control_chars_and_id_title_controls(field):
 refuse('CONTROL_CHARS:'+field,_r([_p(**{field:['a\x00']})]))
 refuse('CONTROL_CHARS:title',_r([_p(title='a\x00')]))
 refuse('CONTROL_CHARS:id',_r([_p(id='a\x00')]))


def test_raw_id_cap_before_unknown_key():
 refuse('OVERSIZE:id',_r([_p(id='a'*129,x=1)]))
 refuse('UNKNOWN:pages',_r([_p(id='a'*128,x=1)]))
