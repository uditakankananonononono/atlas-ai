import importlib
import pytest
from datetime import date
CARDS=[(1280, 'depositions1280', 'DEPOSI1280:', ['witness_topics', 'exhibits', 'record_support', 'privilege_flags', 'noncoaching_boundaries'])]
MODULES=[importlib.import_module('app.modules.m20_general_cognitive_worker.'+c[1]) for c in CARDS]
def request(c,**kw):return {'row':c[0],'as_of':'2026-10-12','entries':[{'element':c[3][0],'status':'supplied','source_ref':'SECRET'}],**kw}
def refuse(m,c,code,r):
 with pytest.raises(ValueError)as e:m.run(r)
 assert str(e.value)==c[2]+' '+code
@pytest.mark.parametrize('i',range(1))
def test_partitions_dates_and_boundary(i):
 c=CARDS[i];m=MODULES[i];e=c[3][0]
 r=request(c,entries=[{'element':e,'status':'supplied','source_ref':'SECRET','entry_date':'2026-10-10'},{'element':e,'status':'missing'}])
 out=m.run(r);a=out['elements'][0]
 assert a=={'element':e,'status':'referenced','also_declared_missing':True,'latest_entry_date':'2026-10-10','days_since_latest':2}
 assert out['coverage']=={'elements_total':len(c[3]),'referenced':1,'disputed':0,'declared_missing':0,'unaddressed':len(c[3])-1}
 assert out['counsel_review_required'] is True and out['legal_conclusion'] is False and out['references_verified'] is False
 assert out['scope']['jurisdiction']=='jurisdiction not supplied or validated'
 r['entries'].append({'element':e,'status':'disputed','source_ref':'OTHER','entry_date':'2026-10-11'})
 assert m.run(r)['elements'][0]=={'element':e,'status':'disputed','also_declared_missing':True,'latest_entry_date':'2026-10-11','days_since_latest':1}
 assert m.run(request(c,entries=[{'element':e,'status':'missing'}]))['elements'][0]['status']=='declared_missing'
 assert 'SECRET' not in str(out)
@pytest.mark.parametrize('i',range(1))
def test_row_and_nonshared_vocabulary(i):
 c=CARDS[i];m=MODULES[i]
 for j,other in enumerate(CARDS):
  if j==i:continue
  refuse(m,c,'UNKNOWN:row',request(c,row=other[0]))
  for word in set(other[3])-set(c[3]):refuse(m,c,'UNKNOWN:element',request(c,entries=[{'element':word,'status':'supplied','source_ref':'SECRET'}]))
@pytest.mark.parametrize('i',range(1))
def test_refusals_and_declared_caps(i):
 c=CARDS[i];m=MODULES[i];e=c[3][0]
 def ent(**kw):return {'element':e,'status':'supplied','source_ref':'ref',**kw}
 refuse(m,c,'EMPTY:entries',request(c,entries=[]))
 refuse(m,c,'OVERSIZE:entries',request(c,entries=[{'token':1}]*201))
 out=m.run(request(c,entries=[ent(source_ref=str(k))for k in range(200)]));assert out['coverage']['referenced']==1
 refuse(m,c,'BAD_TYPE:entries',request(c,entries=[ent(),ent()]))
 for day in ('2026-02-30','2026-10-13','٢٠٢٦-10-10'):refuse(m,c,'BAD_TYPE:entry_date',request(c,entries=[ent(entry_date=day)]))
 refuse(m,c,'BAD_TYPE:as_of',request(c,as_of='2026-02-30'))
 refuse(m,c,'BAD_TYPE:row',request(c,row=True))
 refuse(m,c,'UNKNOWN:status',request(c,entries=[ent(status='unknown')]))
 for status in ('supplied','disputed'):
  for ref in (None,'',5):refuse(m,c,'BAD_TYPE:source_ref',request(c,entries=[ent(status=status,source_ref=ref)]))
 for ref in ('ref',5):refuse(m,c,'BAD_TYPE:source_ref',request(c,entries=[ent(status='missing',source_ref=ref)]))
 assert m.run(request(c,entries=[ent(source_ref='x'*200)]))['coverage']['referenced']==1
 r=request(c,entries=[ent(source_ref='x'*201)]);r['token']=1;refuse(m,c,'OVERSIZE:source_ref',r)
 for k,reason in [('token','SEND'),('pay','SPEND'),('file','EFFECT'),('password','NOCREDS')]:
  r=request(c);r[k]=1;refuse(m,c,reason+':'+k,r)
 r=request(c);r['pay']=1;r['serve']=1;r['approve']=1;r['token']=1;refuse(m,c,'SEND:approve',r)
 r=request(c);r['odd']=1;refuse(m,c,'UNKNOWN:request',r)
class D(dict):pass
class L(list):pass
class S(str):pass
class I(int):pass
@pytest.mark.parametrize('kind,limit',[(dict,32),(list,64),(tuple,64)])
def test_cardinality_and_peak(kind,limit):
 c=CARDS[0];m=MODULES[0]
 def node(n):return {str(i):0 for i in range(n)} if kind is dict else kind(range(n))
 refuse(m,c,'UNKNOWN:request',{'extra':[node(limit)]})
 refuse(m,c,'OVERSIZE:request',{'extra':[node(limit+1)]})
 import tracemalloc
 hostile=node(200000);r=hostile if kind is dict else {'extra':hostile}
 tracemalloc.start()
 try:refuse(m,c,'OVERSIZE:request',r);peak=tracemalloc.get_traced_memory()[1]
 finally:tracemalloc.stop()
 assert peak<100000,peak
@pytest.mark.parametrize('i',range(1))
def test_exact_types_and_hygiene(i):
 c=CARDS[i];m=MODULES[i];e=c[3][0]
 refuse(m,c,'BAD_TYPE:request',D(request(c)))
 refuse(m,c,'BAD_TYPE:entries',request(c,entries=L([])))
 refuse(m,c,'BAD_TYPE:row',request(c,row=I(c[0])))
 refuse(m,c,'BAD_TYPE:as_of',request(c,as_of=S('2026-10-12')))
 refuse(m,c,'BAD_TYPE:key',{S('row'):c[0]})
 for field in ('element','status','source_ref'):
  r=request(c);r['entries'][0][field]=S(r['entries'][0][field]);refuse(m,c,'BAD_TYPE:'+field,r)
  for char in ('\x00','\x81','\u200b','\u2028','\u2029','\n','\r','\t'):
   r=request(c);r['entries'][0][field]='x'+char;refuse(m,c,'CONTROL_CHARS:'+field,r)
 r=request(c);r['entries'][0]['source_ref']='x\u00a0x';assert m.run(r)['coverage']['referenced']==1
 r=request(c);r['entries'][0]['extra']=1;refuse(m,c,'UNKNOWN:entries',r)
 r=request(c);r['bad\u200b']=1;refuse(m,c,'CONTROL_CHARS:key',r)
 refuse(m,c,'OVERSIZE:key',{'x'*201:1})
def test_resource_limits():
 c=CARDS[0];m=MODULES[0];r={};r['loop']=r;refuse(m,c,'BAD_TYPE:request',r)
 def nested(n):
  v=0
  for _ in range(n):v=[v]
  return {'extra':v}
 refuse(m,c,'UNKNOWN:request',nested(31));refuse(m,c,'OVERSIZE:request',nested(32))
 def tree(n):
  if n==1:return []
  count=min(64,n-1);q,rem=divmod(n-1,count)
  return [tree(q+(i<rem))for i in range(count)]
 refuse(m,c,'UNKNOWN:request',{'extra':tree(9999)})
 refuse(m,c,'OVERSIZE:request',{'extra':tree(10000)})

def test_extra_boundary_precedence_and_dates():
 c=CARDS[0];m=MODULES[0]
 r={str(i):0 for i in range(32)};r['entries']=[{'token':1}]*201
 refuse(m,c,'OVERSIZE:request',r)
 r=request(c);r['entries'][0].update({str(i):0 for i in range(30)})
 r['entries'][0]['source_ref']='x'*201;refuse(m,c,'OVERSIZE:request',r)
 refuse(m,c,'UNKNOWN:request',{str(i):0 for i in range(32)})
 r=request(c);r['as_of']='2026-10-12x';r['token']=1;refuse(m,c,'OVERSIZE:as_of',r)
 r=request(c);r['entries'][0]['entry_date']='2026-10-12x';r['token']=1;refuse(m,c,'OVERSIZE:entry_date',r)
 for field in ('element','status'):
  r=request(c);r['entries'][0][field]='x'*200;refuse(m,c,'UNKNOWN:'+field,r)
  r['entries'][0][field]='x'*201;r['token']=1;refuse(m,c,'OVERSIZE:'+field,r)
 r=request(c);r['entries'][0]['entry_date']='2026-10-12';assert m.run(r)['elements'][0]['days_since_latest']==0
 r=request(c);r['entries'][0]['entry_date']='2026-09-30';assert m.run(r)['elements'][0]['days_since_latest']==12
 r=request(c);r['entries'][0]['entry_date']=None;refuse(m,c,'BAD_TYPE:entry_date',r)
 r=request(c);r['entries'][0]=D(r['entries'][0]);refuse(m,c,'BAD_TYPE:entries',r)
 r=request(c);r['entries'][0]['entry_date']=S('2026-10-10');refuse(m,c,'BAD_TYPE:entry_date',r)
 r=request(c);r['entries'][0]['status']='missing';r['entries'][0]['source_ref']=None
 assert m.run(r)['elements'][0]['status']=='declared_missing'
 for r in ({'extra':{'entries':[0]*65}},{'entries':tuple(range(65))}):refuse(m,c,'OVERSIZE:request',r)

@pytest.mark.parametrize('value',['20261010','2026-W41-6','2026-1-10','2026-10-1','2026-10-10'+chr(10)])
@pytest.mark.parametrize('field',['as_of','entry_date'])
def test_strict_date_syntax(field,value):
 c=CARDS[0];m=MODULES[0];r=request(c)
 if field=='as_of':r[field]=value
 else:r['entries'][0][field]=value
 refuse(m,c,('OVERSIZE:' if len(value)>10 else 'CONTROL_CHARS:' if chr(10) in value else 'BAD_TYPE:')+field,r)

@pytest.mark.parametrize('word',['elements', 'witnesses', 'motions', 'stipulations', 'unresolved_proof_gaps'])
def test_other_row_nonshared_word_refused(word):
 c=CARDS[0];r=request(c);r['entries'][0]['element']=word
 refuse(MODULES[0],c,'UNKNOWN:element',r)

def test_other_row_integer_refused():
 c=CARDS[0];refuse(MODULES[0],c,'UNKNOWN:row',request(c,row=1281))


def test_integer_key_and_token_send_precedence():
 c=CARDS[0];r=request(c);r[5]=0;r['token']=0
 refuse(MODULES[0],c,'SEND:token',r)


def test_exact_32_key_entry_including_token():
 c=CARDS[0];r=request(c);entry=r['entries'][0]
 entry.update({str(i):0 for i in range(28)});entry['token']=0
 assert len(entry)==32
 refuse(MODULES[0],c,'SEND:token',r)


def test_raw_200_key_unknown_boundary():
 c=CARDS[0];refuse(MODULES[0],c,'UNKNOWN:request',{'x'*200:0})


def test_direct_dict_32_33_boundaries():
 c=CARDS[0]
 refuse(MODULES[0],c,'UNKNOWN:request',{'extra':{str(i):0 for i in range(32)}})
 refuse(MODULES[0],c,'OVERSIZE:request',{'extra':{str(i):0 for i in range(33)}})
