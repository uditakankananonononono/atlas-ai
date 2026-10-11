import importlib
import pytest
from datetime import date
CARDS=[(1283, 'witness_preparation1283', 'WITNES1283:', ['firsthand_recollection', 'documents', 'uncertainty', 'prohibited_coaching']), (1284, 'jury_selection1284', 'JURYSE1284:', ['case_neutral_topics', 'cause_grounds', 'equal_protection_review']), (1285, 'appellate_practice1285', 'APPELL1285:', ['appealability', 'preservation', 'record_cites', 'review_standard', 'requested_relief']), (1286, 'legal_writing1286', 'LEGALW1286:', ['question', 'short_answer_alternatives', 'facts', 'sourced_rules', 'analysis_gaps']), (1288, 'brief_writing1288', 'BRIEFW1288:', ['record_proposition', 'authority', 'counterauthority', 'analysis', 'requested_relief']), (1289, 'oral_argument1289', 'ORALAR1289:', ['likely_questions', 'record_cites', 'authorities', 'concessions', 'unknowns']), (1290, 'legal_ethics1290', 'LEGALE1290:', ['actor', 'role', 'duty', 'rule_source', 'facts', 'ethics_review']), (1291, 'professional_responsibility1291', 'PROFES1291:', ['competence', 'diligence', 'candor', 'supervision', 'communication']), (1292, 'conflicts_of_interest1292', 'CONFLI1292:', ['clients', 'former_clients', 'adverse_parties', 'matters', 'consent_questions']), (1293, 'attorney_client_privilege1293', 'ATTORN1293:', ['communication', 'participants', 'purpose', 'confidentiality', 'waiver', 'exceptions']), (1294, 'legal_malpractice1294', 'LEGALM1294:', ['duty', 'standard_evidence', 'breach_allegation', 'causation', 'damages_assertions']), (1295, 'pro_bono_practice1295', 'PROBON1295:', ['scope', 'eligibility_source', 'competence', 'capacity', 'engagement_approval'])]
MODULES=[importlib.import_module('app.modules.m20_general_cognitive_worker.'+c[1]) for c in CARDS]
def request(c,**kw):return {'row':c[0],'as_of':'2026-10-12','entries':[{'element':c[3][0],'status':'supplied','source_ref':'SECRET'}],**kw}
def refuse(m,c,code,r):
 with pytest.raises(ValueError)as e:m.run(r)
 assert str(e.value)==c[2]+' '+code
@pytest.mark.parametrize('i',range(12))
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
@pytest.mark.parametrize('i',range(12))
def test_row_and_nonshared_vocabulary(i):
 c=CARDS[i];m=MODULES[i]
 for j,other in enumerate(CARDS):
  if j==i:continue
  refuse(m,c,'UNKNOWN:row',request(c,row=other[0]))
  for word in set(other[3])-set(c[3]):refuse(m,c,'UNKNOWN:element',request(c,entries=[{'element':word,'status':'supplied','source_ref':'SECRET'}]))
@pytest.mark.parametrize('i',range(12))
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
@pytest.mark.parametrize('i',range(12))
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

@pytest.mark.parametrize('i',range(12))
def test_integer_key_with_token_keeps_send_precedence(i):
 c=CARDS[i];m=MODULES[i]
 refuse(m,c,'SEND:token',{1:0,'token':0})

@pytest.mark.parametrize('i',range(12))
def test_exact_32_entry_dict_admitted_before_forbidden(i):
 c=CARDS[i];m=MODULES[i];r=request(c)
 entry=r['entries'][0];entry.update({str(k):0 for k in range(28)});entry['token']=0
 assert type(entry) is dict and len(entry)==32
 refuse(m,c,'SEND:token',r)

@pytest.mark.parametrize('i',range(12))
def test_raw_key_exact_200_admitted(i):
 c=CARDS[i];m=MODULES[i]
 refuse(m,c,'UNKNOWN:request',{'x'*200:0})

@pytest.mark.parametrize('i',range(12))
@pytest.mark.parametrize('count,code',[(32,'UNKNOWN:request'),(33,'OVERSIZE:request')])
def test_generic_dict_value_exact_width(i,count,code):
 c=CARDS[i];m=MODULES[i]
 refuse(m,c,code,{'extra':{str(k):0 for k in range(count)}})
