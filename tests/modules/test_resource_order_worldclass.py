"""Count-first worldclass admission, using real builtin containers."""
import pytest
from app.modules.c30 import worldclass as w


def scan(value):
    matches={name:set() for name,_ in w._FORBIDDEN}
    w._scan_forbidden(value,matches)
    return matches


def refusal(value, code):
    with pytest.raises(ValueError) as exc:scan(value)
    assert str(exc.value)=='PLAN_REFUSED_'+code

@pytest.mark.parametrize('kind',[dict,list])
def test_width_200_201(kind):
    value={str(i):0 for i in range(200)} if kind is dict else [0]*200
    scan(value)
    if kind is dict:value['extra']=0
    else:value.append(0)
    refusal(value,'OVERSIZE:request')

@pytest.mark.parametrize('field',['runs','baselines'])
def test_schema_list_500_501(field):
    scan({field:[0]*500})
    refusal({field:[{'send':1}]+[0]*500},'OVERSIZE:'+field)

@pytest.mark.parametrize('kind',[dict,list])
def test_hostile_exact_builtin_no_child_helper(monkeypatch,kind):
    value={str(i):0 for i in range(201)} if kind is dict else [0]*201
    visits=[]
    def children(node):
        visits.append(node)
        raise AssertionError('unadmitted container iterated')
    monkeypatch.setattr(w,'_children',children,raising=False)
    refusal(value,'OVERSIZE:request')
    assert visits==[]

@pytest.mark.parametrize('field',['runs','baselines'])
def test_schema_list_cap_no_helper(monkeypatch,field):
    child=[0]*501;value={field:child};visits=[]
    original=getattr(w,'_children',None)
    def children(node):
        if node is child:visits.append(node);raise AssertionError('schema list iterated')
        return original(node) if original else node.items()
    monkeypatch.setattr(w,'_children',children,raising=False)
    refusal(value,'OVERSIZE:'+field)
    assert visits==[]

def test_depth32_33():
    value=0
    for _ in range(32):value=[value]
    scan(value)
    refusal([value],'OVERSIZE:request')

def test_container_nodes10000_10001():
    # Scalars are not charged; 1 root +50 lists +9949 empty lists.
    value=[[[] for _ in range(199)] for _ in range(49)]+[[[] for _ in range(198)]]
    scan(value)
    value[-1].append([])
    refusal(value,'OVERSIZE:request')

def test_cycles_aliases():
    value=[];value.append(value);refusal(value,'BAD_TYPE:request')
    value={};value['x']=value;refusal(value,'BAD_TYPE:request')
    shared={'send':1};assert scan([shared,shared])['SEND']=={'send'}

def test_raw_keys_200_201():
    scan({'x'*200:0})
    refusal({'x'*201:0},'OVERSIZE:key')
    refusal({'send':1,1:0},'BAD_TYPE:key')

def test_subclass_containers_keys():
    class D(dict):pass
    class L(list):pass
    class S(str):pass
    for value in [D(),L()]:refusal(value,'BAD_TYPE:request')
    refusal({S('send'):1},'BAD_TYPE:key')

def test_preflight_before_forbidden():
    request={'send':1,'extra':[0]*201}
    with pytest.raises(ValueError) as exc:w.run(request)
    assert str(exc.value)=='PLAN_REFUSED_OVERSIZE:request'

def test_full_named_schema_capacity_remains_admitted():
    run={'benchmark':'b','metric':'m','higher_is_better':True,'value':1,'run_date':'2026-10-10'}
    base={'benchmark':'b','metric':'m','value':0,'source_url':'https://x.example','reported_date':'2026-10-10'}
    runs=[dict(run,run_id=str(i)) for i in range(500)]
    baselines=[dict(base,name=str(i)) for i in range(500)]
    scan({'as_of':'2026-10-11','runs':runs,'baselines':baselines})

def test_depth_cap_no_child_helper(monkeypatch):
    child=[0];value=child
    for _ in range(33):value=[value]
    original=w._children;visits=[]
    def children(node):
        if node is child:visits.append(node);raise AssertionError('deep child iterated')
        return original(node)
    monkeypatch.setattr(w,'_children',children)
    refusal(value,'OVERSIZE:request')
    assert visits==[]
