import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import itertools
import random
import sys
import types
import pytest
from app.modules.instinct_doc import p235_concepts_batch623 as m

MOD='app.modules.instinct_doc.p235_concepts_batch623'
REG='app.modules.instinct_doc.p235_concepts_registry'

class S(str):pass
class L(list):pass
class T(tuple):pass
class I(int):pass

def err(fn,*a,msg):
    with pytest.raises(ValueError) as e:fn(*a)
    assert str(e.value)=='P235:%s:%s'%(fn.__name__,msg)

def test_registry_text_and_scope():
    assert m.SCOPE=='PARTIAL bounded exact cover: exact-cover counting and search, selection checks, coverage diagnostics, intersection and frequency structure, essential sets'
    assert m.NOT_CLAIMED==('set cover minimization or approximation','universes over 12 elements or more than 16 sets','dancing-links performance','weighted or colored variants','global novelty','production readiness')
    assert type(m.NOT_CLAIMED) is tuple and importlib.util.find_spec(MOD)

def reload_with(mod_registry=None,finder=None,find_spec=None):
    saved=sys.modules.get(REG);orig=importlib.util.find_spec
    if mod_registry is not None:sys.modules[REG]=mod_registry
    if finder is not None:sys.meta_path.insert(0,finder)
    if find_spec is not None:importlib.util.find_spec=find_spec
    try:
        return importlib.reload(m)
    finally:
        importlib.util.find_spec=orig
        if finder is not None:sys.meta_path.remove(finder)
        if saved is None:sys.modules.pop(REG,None)
        else:sys.modules[REG]=saved

def test_registry_guard_branches():
    def fake_make_fail(name):
        def f(code):raise ValueError('FAKE:%s:%s'%(name,code))
        return f
    fake=types.ModuleType(REG);fake.make_fail=fake_make_fail
    mod=reload_with(mod_registry=fake)
    try:
        with pytest.raises(ValueError,match='FAKE:cover_count:bad_type:n'):mod.cover_count(True,[[1]])
        # registry absent: local fallback message
        sys.modules.pop(REG,None)
        mod=reload_with()
        with pytest.raises(ValueError,match='^P235:cover_count:bad_type:n$'):mod.cover_count(True,[[1]])
        class Bad(importlib.abc.MetaPathFinder):
            def find_spec(self,fullname,path,target=None):
                if fullname==REG:
                    class Ld(importlib.abc.Loader):
                        def create_module(self,spec):return None
                        def exec_module(self,module):raise ModuleNotFoundError('other',name='other_dep')
                    return importlib.machinery.ModuleSpec(fullname,Ld())
        with pytest.raises(ModuleNotFoundError):reload_with(finder=Bad())
        # name matches but spec says present: re-raise
        class Gone(importlib.abc.MetaPathFinder):
            def find_spec(self,fullname,path,target=None):
                if fullname==REG:
                    class Ld(importlib.abc.Loader):
                        def create_module(self,spec):return None
                        def exec_module(self,module):raise ModuleNotFoundError('gone',name=REG)
                    return importlib.machinery.ModuleSpec(fullname,Ld())
        def present(name):return object()
        with pytest.raises(ModuleNotFoundError):reload_with(finder=Gone(),find_spec=present)
        def boom_import(name):raise ImportError('x')
        def boom_value(name):raise ValueError('x')
        assert reload_with(find_spec=boom_import).cover_count(2,[[1],[2]])==1
        assert reload_with(find_spec=boom_value).cover_count(2,[[1],[2]])==1
        class Gone2(Gone):pass
        reload_with(finder=Gone2(),find_spec=boom_import)
        reload_with(finder=Gone2(),find_spec=boom_value)
    finally:
        sys.modules.pop(REG,None);importlib.reload(m)
    assert m.cover_count(2,[[1],[2]])==1


S7=[[1,2],[3,4],[1],[2],[3],[4],[1,2,3,4]]

def oracle_count(n,sets):
    m=len(sets);full=(1<<n)-1;tot=0
    for b in range(1<<m):
        seen=0;ok=True
        for i in range(m):
            if b>>i&1:
                mask=0
                for x in sets[i]:mask|=1<<(x-1)
                if mask&seen:ok=False;break
                seen|=mask
        if ok and seen==full:tot+=1
    return tot

def test_search_known_and_oracle():
    assert m.cover_count(4,S7)==5
    assert m.cover_exists(4,S7)==True
    assert m.cover_first(4,S7)==[0,1]
    assert m.cover_all(4,S7)==[[0,1],[0,4,5],[1,2,3],[2,3,4,5],[6]]
    assert m.cover_count(2,[[1]])==0
    assert m.cover_exists(2,[[1]])==False
    assert m.cover_first(2,[[1]])==[]
    assert m.cover_all(2,[[1]])==[]
    assert m.cover_count(1,[[1]])==1
    assert m.cover_all(1,[[1]])==[[0]]
    fixtures=[(4,S7),(3,[[1,2],[2,3],[1],[2],[3]]),(5,[[1,2],[2,3],[3,4],[4,5],[1],[3],[5],[2,4]]),
              (4,[[1,2,3],[4],[1],[2,3,4],[2],[3]]),(6,[[1,2],[3,4],[5,6],[1],[2],[3],[4],[5],[6],[1,3,5],[2,4,6]])]
    for n,sets in fixtures:
        assert m.cover_count(n,sets)==oracle_count(n,sets)
        assert m.cover_all(n,sets)==sorted(sorted(p) for p in m.cover_all(n,sets))
        assert (m.cover_first(n,sets)==[])==(m.cover_count(n,sets)==0)
        if m.cover_count(n,sets):assert m.cover_first(n,sets)==min(m.cover_all(n,sets))
    big=[[1],[2],[3],[4]]+[[1,2]]*6+[[3,4]]*6
    assert m.cover_count(4,big)==49
    err(m.cover_all,4,big,msg='too_many:solutions')
    assert m.cover_exists(4,big)==True
    S32=[[1,2]]*2+[[3,4]]*4+[[5,6]]*4
    assert m.cover_count(6,S32)==32
    assert len(m.cover_all(6,S32))==32
    assert m.cover_first(6,S32)==[0,2,6]

def test_selection_and_structure():
    assert m.is_cover(4,S7,[0,1])==True
    assert m.is_cover(4,S7,[6])==True
    assert m.is_cover(4,S7,[0,3])==False
    assert m.is_cover(4,S7,[])==False
    assert m.is_cover(4,S7,[2,3,4,5])==True
    assert m.uncovered_elements(4,S7,[0])==[3,4]
    assert m.uncovered_elements(4,S7,[])==[1,2,3,4]
    assert m.uncovered_elements(4,S7,[6])==[]
    assert m.uncovered_elements(4,S7,[0,1])==[]
    assert m.overcovered_elements(4,S7,[0,2,3])==[1,2]
    assert m.overcovered_elements(4,S7,[0,1])==[]
    assert m.overcovered_elements(4,S7,[2,6])==[1]
    assert m.overcovered_elements(4,S7,[1,6])==[3,4]
    assert m.set_intersections(S7,4)==[[2,0,1,1,0,0,2],[0,2,0,0,1,1,2],[1,0,1,0,0,0,1],[1,0,0,1,0,0,1],[0,1,0,0,1,0,1],[0,1,0,0,0,1,1],[2,2,1,1,1,1,4]]
    assert m.element_frequency(4,S7)==[3,3,3,3]
    assert m.element_frequency(3,[[1,2],[2,3]])==[1,2,1]
    assert m.essential_sets(4,S7)==[]
    assert m.essential_sets(2,[[1],[1,2]])==[1]
    assert m.essential_sets(3,[[1],[2],[3],[1,2]])==[2]
    assert m.essential_sets(2,[[1],[2]])==[0,1]

def test_cap_pins_b623():
    n12=[[i] for i in range(1,13)]+[[1,2]]
    assert m.cover_count(12,n12)==2
    err(m.cover_count,13,[[1]],msg='bad_value:n')
    err(m.cover_count,0,[[1]],msg='bad_value:n')
    m16=[[1],[2],[3],[4],[1,2],[1,3],[1,4],[2,3],[2,4],[3,4],[1,2,3],[1,2,4],[1,3,4],[2,3,4],[1,2,3,4],[1,2]]
    assert len(m16)==16 and m.cover_exists(4,m16)==True
    err(m.cover_count,2,[[1],[2]]*9,msg='bad_length:sets')
    err(m.cover_count,1,[[1]]*17,msg='bad_length:sets')
    err(m.cover_count,3,[[1],[2],[3],[1,2],[2,3],[1,3],[1,2,3]]*3,msg='bad_length:sets')
    err(m.cover_count,2,[[1,1]],msg='bad_order:sets[0]')
    err(m.cover_count,3,[[1,2,4]],msg='bad_value:sets[0][2]')
    err(m.is_cover,3,[[1],[2],[3]],[0,1,1],msg='bad_order:pick')
    err(m.is_cover,2,[[1],[2]],[2],msg='bad_value:pick[0]')
    err(m.is_cover,2,[[1],[2]],[0,1,2],msg='bad_length:pick')
    err(m.is_cover,3,[[1],[2],[3]],[0,1,3],msg='bad_value:pick[2]')
    assert m.is_cover(2,[[1],[2]],[0,1])==True

def test_validation_and_order_pins_b623():
    err(m.cover_count,True,[[1]],msg='bad_type:n')
    err(m.cover_count,2,True,msg='bad_type:sets')
    err(m.cover_count,2,[],msg='bad_length:sets')
    err(m.cover_count,2,[T([1]),[2]],msg='bad_type:sets[0]')
    err(m.cover_count,2,[[2],T([1])],msg='bad_type:sets[1]')
    err(m.cover_count,2,[[],[2]],msg='bad_length:sets[0]')
    err(m.cover_count,3,[[1,2,4],[1]],msg='bad_value:sets[0][2]')
    err(m.cover_count,3,[[1],[1,2,4]],msg='bad_value:sets[1][2]')
    err(m.cover_count,2,[[True],[2]],msg='bad_type:sets[0][0]')
    err(m.cover_count,2,[[1],[I(2)]],msg='bad_type:sets[1][0]')
    err(m.cover_count,2,[[0],[2]],msg='bad_value:sets[0][0]')
    err(m.cover_count,2,[[1],[0]],msg='bad_value:sets[1][0]')
    err(m.cover_count,2,[[2,1],[2]],msg='bad_order:sets[0]')
    err(m.cover_count,2,[[1],[2,1]],msg='bad_order:sets[1]')
    err(m.is_cover,2,[[1],[2]],True,msg='bad_type:pick')
    err(m.is_cover,2,[[1],[2]],[True],msg='bad_type:pick[0]')
    err(m.is_cover,2,[[1],[2]],[-1],msg='bad_value:pick[0]')
    err(m.is_cover,3,[[1],[2],[3]],[0,1,0],msg='bad_order:pick')
    err(m.is_cover,2,[[1],[2]],[1,0],msg='bad_order:pick')
    err(m.cover_count,0,[],msg='bad_value:n')
    err(m.cover_count,2,[[0],True],msg='bad_value:sets[0][0]')
    err(m.is_cover,0,[],True,msg='bad_value:n')
    err(m.uncovered_elements,2,[[1],[2]],[0,0],msg='bad_order:pick')
