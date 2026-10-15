import itertools as it,copy,math,pytest
from fractions import Fraction as F
from app.modules.instinct_doc import p235_concepts_batch331 as m
class T(tuple):pass
class I(int):pass
NAMES=('urn_multivariate_without_replacement','urn_multivariate_with_replacement','urn_distinct_colors_without_replacement','urn_distinct_colors_with_replacement','urn_first_color_hit','urn_last_color_hit','urn_full_coverage_probability','urn_missing_colors_distribution','urn_collision_pairs_distribution','urn_runs_without_replacement')

def exact(a,b):
 assert type(a) is type(b)
 if type(b) in (list,tuple):
  assert len(a)==len(b)
  for x,y in zip(a,b):exact(x,y)
 else:assert a==b

def aggregate(values):
 bins={}
 for v,p in values:bins[v]=bins.get(v,F(0))+p
 return sorted(bins.items())

def oracle(counts,draws,replacement):
 # Color sequences weighted by sequential sampling,not combinations formula.
 result=[]
 for sequence in it.product(range(len(counts)),repeat=draws):
  remaining=list(counts);mass=F(1)
  for color in sequence:
   mass*=F(remaining[color],sum(remaining))
   if not replacement:remaining[color]-=1
   if not mass:break
  if mass:result.append((sequence,mass))
 return result

def check(counts,draws):
 no=oracle(counts,draws,False);yes=oracle(counts,draws,True)
 def vector(seq):return tuple(seq.count(i) for i in range(len(counts)))
 laws=[aggregate((vector(s),p) for s,p in no),aggregate((vector(s),p) for s,p in yes)]
 expected=[laws[0],laws[1],aggregate((len(set(s)),p) for s,p in no),aggregate((len(set(s)),p) for s,p in yes),None,None,sum((p for s,p in no if len(set(s))==len(counts)),F(0)),aggregate((sum(1<<i for i in range(len(counts)) if i not in s),p) for s,p in no),aggregate((sum(s[i]==s[j] for i in range(len(s)) for j in range(i+1,len(s))),p) for s,p in no),aggregate((sum(i==0 or s[i]!=s[i-1] for i in range(len(s))),p) for s,p in no)]
 for name,e in zip(NAMES,expected):
  if 'color_hit' in name:
   for color in range(len(counts)):
    law=aggregate(((s.index(color)+1 if 'first' in name else len(s)-tuple(reversed(s)).index(color)) if color in s else 0,p) for s,p in no)
    exact(getattr(m,name)(counts,draws,color),law)
  else:
   before=copy.deepcopy((counts,draws));out=getattr(m,name)(counts,draws);exact(out,e);assert (counts,draws)==before
   if type(out) is list:out.clear();exact(getattr(m,name)(counts,draws),e)
 for law in laws:assert sum(p for v,p in law)==1

def test_sequence_oracles():
 for n in range(1,4):
  for counts in it.product((1,2),repeat=n):
   for draws in range(sum(counts)+1):check(counts,draws)
 for counts in ((3,),(3,3),(3,3,2),(1,3,3)):
  for draws in (0,1,2,3):check(counts,draws)
 # Full population cap;allcountvectors deterministic,ordered positions brute.
 check((3,3,2),8)


def test_validation_scope_fallback(monkeypatch):
 for name in NAMES:
  def fail(counts,draws,code,color=0):
   args=(counts,draws,color) if 'color_hit' in name else (counts,draws);old=copy.deepcopy(args)
   with pytest.raises(ValueError) as e:getattr(m,name)(*args)
   assert str(e.value)=='P235:'+name+':'+code and args==old
  for c in (None,[],T((1,))):fail(c,None,'bad_type:counts')
  for c in ((),(1,)*4):fail(c,None,'bad_value:length_counts')
  fail((1,1,1,None),None,'bad_value:length_counts')
  for i in range(3):
   for bad in (None,True,False,I(1),1.0,0,4):
    c=[1]*3;c[i]=bad;fail(tuple(c),None,'bad_type:cell_counts' if type(bad) is not int else 'bad_value:cell_counts')
  fail((3,3,3),None,'bad_value:total_counts')
  for d in (None,True,False,I(0),0.0):fail((1,),d,'bad_type:draws')
  for d in (-1,2):fail((1,),d,'bad_value:draws')
  if 'color_hit' in name:
   for color in (None,True,I(0),0.0):fail((1,),0,'bad_type:color',color)
   for color in (-1,1):fail((1,),0,'bad_value:color',color)
   fail((1,),2,'bad_value:draws',-1)
 assert m.SCOPE=='PARTIAL: exact bounded labelled-urn finite sampling and color occupancy distributions'
 assert m.NOT_CLAIMED==('observed data validity','statistical inference','unbounded sampling','global novelty','production readiness')
 import pathlib,builtins,importlib.util
 source=pathlib.Path(m.__file__).read_text();original=builtins.__import__
 def execute(missing):
  def custom(name,*args,**kwargs):
   if name=='app.modules.instinct_doc.p235_concepts_registry':raise ModuleNotFoundError('blocked',name=missing)
   return original(name,*args,**kwargs)
  ns={'__builtins__':dict(vars(builtins),__import__=custom)};exec(compile(source,'standalone','exec'),ns);return ns
 assert execute('app.modules.instinct_doc.p235_concepts_registry')['urn_full_coverage_probability']((1,),1)==F(1)
 with pytest.raises(ModuleNotFoundError):execute('other_dependency')
 monkeypatch.setattr(importlib.util,'find_spec',lambda name:object())
 with pytest.raises(ModuleNotFoundError):execute('app.modules.instinct_doc.p235_concepts_registry')
