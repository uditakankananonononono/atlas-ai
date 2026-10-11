"""S5.8 supplied idea tickets, offline data only."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import pytest
SRC=Path(__file__).resolve().parents[2]/'backend/app/modules/c36/act.py'
def load():
    spec=importlib.util.spec_from_file_location('act_s58',SRC);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
@pytest.fixture
def m():return load()
def idea(i='1',title='Alpha',**kw):
    return dict(id=i,title=title,body='Supplied body',category='cute',**kw)
def req(rows=None):return {'as_of':'2026-10-11','ideas':[idea()] if rows is None else rows}
def refuse(m,r,code):
    with pytest.raises(ValueError) as exc:m.run(r)
    assert str(exc.value)=='VENT_REFUSED_'+code

def test_ticket(m):
    t=m.run(req([idea(acceptance=['exact  criterion'],concepts=['z','a'])]))['tickets'][0]
    assert t=={'ticket_id':'S58-1','title':'Alpha','body':'Supplied body','category':'cute','concepts':['a','z'],'acceptance_tests':[{'text':'exact  criterion','status':'supplied'}],'status':'proposed','needs_her_review':True,'rank':1}

def test_templates(m):
    assert m.run(req())['tickets'][0]['acceptance_tests']==[
        {'text':'Output exists and is readable.','status':'TO_WRITE'},
        {'text':'Owner has reviewed the output.','status':'TO_WRITE'},
        {'text':'No spend, send or account action occurred.','status':'TO_WRITE'}]

def test_fixture25_merge_order_accounting(m):
    rows=[idea(str(i),'Title '+str(i),acceptance=['check '+str(i)] if i<4 else [],concepts=['z']) for i in range(22)]
    for i,row in enumerate(rows):row['category']=['cute','aesthetic','entrepreneurship','other'][i%4]
    rows += [dict(idea('22',' TITLE  0 ',acceptance=['later','check 0'],concepts=['a']),body='discarded body'),idea('23','title 1'),idea('24','title 2')]
    out=m.run(req(rows));assert out['counts']=={'supplied':25,'tickets':22,'merged_duplicate':3}
    t=next(t for t in out['tickets'] if t['ticket_id']=='S58-0')
    assert t['title']=='Title 0' and t['body']=='Supplied body' and t['category']=='cute'
    assert t['concepts']==['a','z'] and t['acceptance_tests']==[{'text':'check 0','status':'supplied'},{'text':'later','status':'supplied'}]
    assert [t['rank'] for t in out['tickets']]==list(range(1,23))
    order={'entrepreneurship':0,'aesthetic':1,'cute':2,'other':3}
    assert out['tickets']==sorted(out['tickets'],key=lambda t:(order[t['category']],t['ticket_id'][4:]))
    assert out['counts']['supplied']==out['counts']['tickets']+out['counts']['merged_duplicate']

def test_determinism_nonmutation_scope(m):
    r=req();old=copy.deepcopy(r);a=m.run(r);b=m.run(r);assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True);assert r==old;assert a['scope']['as_of']=='2026-10-11'

@pytest.mark.parametrize('field,limit',[('id',128),('title',200),('body',4000)])
def test_scalar_caps(m,field,limit):
    row=idea();row[field]='x'*limit;m.run(req([row]));row[field]='\x00'+'x'*limit;refuse(m,req([row]),'OVERSIZE:'+field)

@pytest.mark.parametrize('field,limit,count',[('acceptance',300,10),('concepts',100,20)])
def test_collection_caps(m,field,limit,count):
    row=idea(**{field:['x'*limit]*count});m.run(req([row]));row[field]=['x'*(limit+1)];refuse(m,req([row]),'OVERSIZE:'+field)
    row[field]=[1]*(count+1);refuse(m,req([row]),'OVERSIZE:'+field)

def test_ideas2000_2001(m):
    out=m.run(req([idea(str(i),'Same') for i in range(2000)]));assert out['counts']=={'supplied':2000,'tickets':1,'merged_duplicate':1999}
    refuse(m,req([False]*2001),'OVERSIZE:ideas')

def test_global_caps_before_validation(m):
    a=idea('1',title='bad\x00');b=idea('2',title='x'*201);refuse(m,req([a,b]),'OVERSIZE:title')
    a['acceptance']=[False];b['acceptance']=['x'*301];b['title']='fine';refuse(m,req([a,b]),'OVERSIZE:acceptance')

@pytest.mark.parametrize('key,code',[('launch','EFFECT:launch'),('token','SEND:token'),('card-number','SPEND:card_number'),('api-key','NOCREDS:api_key')])
def test_forbidden_recursive(m,key,code):refuse(m,dict(req(),extra=[{'nested':{key:1}}]),code)

def test_precedence(m):
    refuse(m,dict(req(),x={'launch':1,'pay':1,'send':1,'approval':1,'login':1}),'SEND:approval')
    refuse(m,dict(req(),x={'launch':1,'pay':1,'login':1}),'SPEND:pay')
    refuse(m,dict(req(),x={'launch':1,'login':1}),'EFFECT:launch')

@pytest.mark.parametrize('r,code',[(None,'BAD_TYPE:request'),([], 'BAD_TYPE:request'),({'as_of':'2026-10-11','ideas':[]},'EMPTY'),({'as_of':'2026-02-30','ideas':[idea()]},'BAD_TYPE:as_of'),({'as_of':'2026-10-111','ideas':[idea()]},'OVERSIZE:as_of'),({'as_of':'2026-10-11','ideas':[False]},'BAD_TYPE:ideas')])
def test_types_date_empty(m,r,code):refuse(m,r,code)

def test_category_duplicate_ids_unknown(m):
    r=req();r['ideas'][0]['category']='nope';refuse(m,r,'UNKNOWN:category')
    r['ideas'][0]['category']='x'*201;refuse(m,r,'OVERSIZE:category')
    refuse(m,req([idea(),idea()]),'BAD_TYPE:ideas')
    refuse(m,dict(req(),sensitive=1),'UNKNOWN:request')
    row=idea();row['unexpected']=1;refuse(m,req([row]),'UNKNOWN:ideas')
    refuse(m,req([idea(concepts=[{'unexpected':1}])]),'UNKNOWN:concepts')

@pytest.mark.parametrize('field',['id','title','body','acceptance','concepts'])
@pytest.mark.parametrize('char',['\x00','\u200b','\u2028','\u2029'])
def test_hygiene(m,field,char):
    row=idea();row[field]=['a'+char+'b'] if field in ('acceptance','concepts') else 'a'+char+'b';refuse(m,req([row]),'CONTROL_CHARS:'+field)

def test_zs_and_optional_null(m):
    row=idea(title=' A\u00a0B ',acceptance=None,concepts=None);assert m.run(req([row]))['tickets'][0]['title']==' A\u00a0B '

class HostileList(list):
    def __iter__(self):raise AssertionError('subclass iterated')
class HostileDict(dict):
    def items(self):raise AssertionError('subclass items')
    def __iter__(self):raise AssertionError('subclass iterated')
class HostileStr(str):pass

def test_subclass_no_iteration(m):
    refuse(m,HostileDict(req()),'BAD_TYPE:request')
    for field in ['ideas']:
        r=req();r[field]=HostileList(r[field]);refuse(m,r,'BAD_TYPE:ideas')
    for field in ['acceptance','concepts']:
        refuse(m,req([idea(**{field:HostileList(['a'])})]),'BAD_TYPE:'+field)
    refuse(m,req([HostileDict(idea())]),'BAD_TYPE:ideas')
    refuse(m,req([idea(title=HostileStr('x'))]),'BAD_TYPE:title')
    refuse(m,dict(req(),extra=HostileList()),'BAD_TYPE:request')

def test_raw_key_depth_cycle(m):
    refuse(m,dict(req(),**{'x'*201:1}),'OVERSIZE:key');refuse(m,dict(req(),**{'x'*200:1}),'UNKNOWN:request')
    r=req();r[1]=1;refuse(m,r,'BAD_TYPE:key')
    r=req();r['x']=r;refuse(m,r,'BAD_TYPE:request')
    x=0
    for _ in range(32):x=[x]
    refuse(m,dict(req(),x=x),'OVERSIZE:request')

def test_hostile_exact_builtin_helper(m,monkeypatch):
    calls=[]
    def children(node):calls.append(node);raise AssertionError('oversized root iterated')
    monkeypatch.setattr(m,'_children',children)
    refuse(m,{str(i):0 for i in range(33)},'OVERSIZE:request');assert calls==[]

def test_ast_purity(m):
    tree=ast.parse(SRC.read_text());imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):imports += [n.name for n in node.names]
        if isinstance(node,ast.ImportFrom):imports.append(node.module)
    assert set(imports)<={'datetime','unicodedata','app.modules.c30'}
    for name in ['send','spend','publish','post','execute','build','create_account','fetch']:assert not hasattr(m,name)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'eval','exec','open','compile','__import__'} for n in ast.walk(tree))

def test_resource_seams(m):
    m._admit({str(i):0 for i in range(32)},'request','root',0,set(),[0])
    refuse(m,{str(i):0 for i in range(33)},'OVERSIZE:request')
    m._admit([0]*64,'request','generic',0,set(),[0])
    refuse(m,dict(req(),extra=[0]*65),'OVERSIZE:request')
    chain=0
    for _ in range(32):chain=[chain]
    m._admit(chain,'request','generic',0,set(),[0])
    with pytest.raises(ValueError) as exc:m._admit([chain],'request','generic',0,set(),[0])
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:request'
    # container-only budget: root +154 lists +9845 empty leaves =10000.
    tree=[[[] for _ in range(64)] for _ in range(153)]+[[[] for _ in range(53)]]
    # Root must use schema ideas context to admit154 children.
    m._admit(tree,'ideas','ideas',0,set(),[0])
    tree[-1].append([])
    with pytest.raises(ValueError) as exc:m._admit(tree,'ideas','ideas',0,set(),[0])
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:request'

def test_global_known_list_count_before_items(m,monkeypatch):
    child=[False]*11;calls=[];original=m._children
    def children(node):
        if node is child:calls.append(node);raise AssertionError('unadmitted acceptance iterated')
        return original(node)
    monkeypatch.setattr(m,'_children',children)
    refuse(m,req([idea(acceptance=child)]),'OVERSIZE:acceptance');assert calls==[]

def test_nullable_vs_invalid_optional(m):
    for field in ['acceptance','concepts']:
        for value in [(),False,{},[None]]:refuse(m,req([idea(**{field:value})]),'BAD_TYPE:'+field)
    for field in ['id','title','body','category']:
        row=idea();row[field]=False;refuse(m,req([row]),'BAD_TYPE:'+field)
        row[field]=' ';refuse(m,req([row]),'EMPTY:'+field)

def test_merge_exact_acceptance_and_order(m):
    a=idea('z','Straße',acceptance=['A','A','a'],concepts=['Z','a','a']);b=idea('a','STRASSE',acceptance=['a',' B '],concepts=['A'])
    out=m.run(req([a,b]));assert out['counts']=={'supplied':2,'tickets':1,'merged_duplicate':1}
    t=out['tickets'][0];assert t['ticket_id']=='S58-z';assert t['concepts']==['A','Z','a']
    assert t['acceptance_tests']==[{'text':'A','status':'supplied'},{'text':'a','status':'supplied'},{'text':' B ','status':'supplied'}]

def test_forbidden_rawcap_and_subclass_priorities(m):
    r=req();r['token']=1;r['x'*201]=1;refuse(m,r,'OVERSIZE:key')
    r=req();r['token']=1;r['unknown']=HostileList();refuse(m,r,'BAD_TYPE:request')
    r=req();r['ideas'][0]['title']='x'*201;r['token']=1;refuse(m,r,'OVERSIZE:title')

def test_pure_policy_identity(m):
    from app.modules.c30 import policy
    assert m.policy is policy
    out=m.run(req());assert out['scope']==policy.scope(['supplied idea title merge and category/id-ordered proposed tickets'],['execution','sending','spending','publishing','building','feasibility validation','routes'],'supplied-ideas','2026-10-11')

@pytest.mark.parametrize('char',['\x00','\u200b','\u2028','\u2029'])
def test_key_hygiene_before_forbidden(m,char):refuse(m,dict(req(),**{'a'+char+'b':1}),'CONTROL_CHARS:key')

def test_context_routing_generic_and_alias(m):
    shared=[];m._admit([shared,shared],'request','generic',0,set(),[0])
    refuse(m,dict(req(),extra=[HostileDict()]),'BAD_TYPE:request')
    r=req([idea()]);r['ideas'][0]['acceptance']=[HostileList()];refuse(m,r,'BAD_TYPE:acceptance')
    r=req([idea()]);r['ideas'][0]['concepts']=[HostileList()];refuse(m,r,'BAD_TYPE:concepts')
    for field in ['id','title','body','category','acceptance','concepts']:
        row=idea();row[field]=[{'unknown':1}];refuse(m,req([row]),'UNKNOWN:'+field)

def test_raw_cap_seams(m):
    for field,limit in [('as_of',10)]:
        with pytest.raises(ValueError) as exc:m._raw_caps({field:'x'*(limit+1)})
        assert str(exc.value)=='VENT_REFUSED_OVERSIZE:'+field
    with pytest.raises(ValueError) as exc:m._raw_caps({'ideas':[0]*2001})
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:ideas'
    with pytest.raises(ValueError) as exc:m._raw_caps(req([idea(acceptance=[0]*11)]))
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:acceptance'
    # Structural caps are independently tested above; these seam checks pin
    # raw-cap pass itself, including ordering before scalar hygiene.

def test_missing_asof_ideas(m):
    refuse(m,{'ideas':[idea()]},'BAD_TYPE:as_of')
    refuse(m,{'as_of':'2026-10-11'},'BAD_TYPE:ideas')

def test_final_optional_caps_seam(m):
    # The validation cap itself remains pinned despite preflight redundancy.
    with pytest.raises(ValueError) as exc:m.cap([0]*11,10,'acceptance')
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:acceptance'

def test_initial_resource_state(m,monkeypatch):
    original=m._admit;starts=[]
    def admit(node,field,context,depth,active,budget):
        if context=='root':starts.append((depth,budget[0]))
        return original(node,field,context,depth,active,budget)
    monkeypatch.setattr(m,'_admit',admit);m.run(req());assert starts==[(0,0)]

def test_admit_ideas_cap_direct(m):
    with pytest.raises(ValueError) as exc:m._admit([0]*2001,'ideas','ideas',0,set(),[0])
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:ideas'

def test_clean_cap_seam(m):
    with pytest.raises(ValueError) as exc:m.clean('x'*201,'title',200)
    assert str(exc.value)=='VENT_REFUSED_OVERSIZE:title'

def test_date_exact_shape(m):
    for value in ['20261011','2026-W41-7','2026-1-01']:
        r=req();r['as_of']=value;refuse(m,r,'BAD_TYPE:as_of')

@pytest.mark.parametrize('key,reason',[(k,r) for r,keys in [
('SEND',{'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'}),
('SPEND',{'pay','purchase','spend','buy','checkout','card_number'}),
('EFFECT',{'act','execute','run','launch','publish','post','deploy','register','build','upload'}),
('NOCREDS',{'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'})] for k in sorted(keys)])
def test_all_forbidden_members(m,key,reason):
    refuse(m,dict(req(),extra={key.upper().replace('_','-'):1}),reason+':'+key)

def test_full_max_optional_payload(m):
    rows=[idea(str(i),'same',acceptance=['x']*10,concepts=['x']*20) for i in range(2000)]
    assert m.run(req(rows))['counts']=={'supplied':2000,'tickets':1,'merged_duplicate':1999}

def test_named_caps_do_not_relax_dict_width(m):
    for field in ['ideas','acceptance','concepts']:
        value={str(i):0 for i in range(33)}
        r=dict(req(),ideas=value) if field=='ideas' else req([idea(**{field:value})])
        refuse(m,r,'OVERSIZE:request')

def test_category_exact_200_201_edge(m):
    row=idea();row['category']='x'*200
    refuse(m,req([row]),'UNKNOWN:category')
    row['category']='x'*201
    refuse(m,req([row]),'OVERSIZE:category')

@pytest.mark.parametrize('payload,code',[
    ({'acceptance':['x']*11},'UNKNOWN:request'),
    ({'concepts':['x']*25},'UNKNOWN:request'),
    (req([dict(idea(),body={'acceptance':['x']*11})]),'UNKNOWN:body'),
])
def test_collection_key_outside_idea_context(m,payload,code):
    refuse(m,payload,code)
