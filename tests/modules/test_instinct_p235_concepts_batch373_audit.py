import unittest,itertools as it
from app.modules.instinct_doc import p235_concepts_batch373 as m
checks=0
def eq(a,b):
 global checks
 assert a==b,(a,b);checks+=1
def check(t):
 n=len(t);universe=set(range(n));subsets=[set(i for i in range(n)if mask>>i&1)for mask in range(1<<n)]
 closed=[s for s in subsets if all(t[a][b]in s for a,b in it.product(s,repeat=2))]
 def closure(seed):return set.intersection(*(s for s in closed if set(seed)<=s))
 generators=[s for s in subsets if closure(s)==universe];eq(m.semigroup_minimal_generating_sets(t),sorted(tuple(sorted(s))for s in generators if not any(r<s for r in generators)))
 eq(m.semigroup_idempotent_generated_subsemigroup(t),sorted(closure([i for i in range(n)if t[i][i]==i])))
 left=[s for s in subsets if all(t[x][a]in s for a in s for x in universe)];right=[s for s in subsets if all(t[a][x]in s for a in s for x in universe)]
 for family,fn in((left,m.semigroup_green_l_classes),(right,m.semigroup_green_r_classes)):
  ideals=[frozenset(set.intersection(*(s for s in family if a in s)))for a in range(n)];eq(fn(t),sorted(set(tuple(i for i in range(n)if ideals[i]==v)for v in ideals)))
 eq(m.semigroup_two_sided_ideals(t),sorted(tuple(sorted(s))for s in left if s and s in right))
 pairs=list(it.combinations(range(n),2));partitions=[]
 for mask in range(1<<len(pairs)):
  rel={(i,i)for i in range(n)}
  for k,(a,b)in enumerate(pairs):
   if mask>>k&1:rel|={(a,b),(b,a)}
  if any((a,c)not in rel for a,b in rel for x,c in rel if x==b):continue
  blocks=sorted(set(tuple(b for b in range(n)if(a,b)in rel)for a in range(n)));ids={x:i for i,b in enumerate(blocks)for x in b};quotient={};ok=True
  for a,b in it.product(range(n),repeat=2):
   key=ids[a],ids[b];value=ids[t[a][b]]
   if key in quotient and quotient[key]!=value:ok=False;break
   quotient[key]=value
  if ok:partitions.append(tuple(blocks))
 eq(m.semigroup_congruences(t),sorted(partitions))
 autos=[]
 for p in it.permutations(range(n)):
  inverse=[p.index(i)for i in range(n)];relabeled=tuple(tuple(p[t[inverse[a]][inverse[b]]]for b in range(n))for a in range(n))
  if relabeled==t:autos.append(p)
 eq(m.semigroup_automorphisms(t),autos)
 # Sandwichmapsf_a(b)=aba; mutualinverseconditionasfixedpairs.
 eq(m.semigroup_regular_inverses(t),[tuple(b for b in range(n)if t[a][t[b][a]]==a and t[b][t[a][b]]==b)for a in range(n)])
 orbits=[]
 for a in range(n):
  f=lambda x:t[x][a];slow=f(a);fast=f(f(a))
  while slow!=fast:slow=f(slow);fast=f(f(fast))
  mu=0;slow=a
  while slow!=fast:slow=f(slow);fast=f(fast);mu+=1
  period=1;fast=f(slow)
  while slow!=fast:fast=f(fast);period+=1
  seq=[];x=a
  for _ in range(mu+period):seq.append(x);x=f(x)
  orbits.append((tuple(seq[:mu]),tuple(seq[mu:])))
 eq(m.semigroup_power_orbits(t),orbits)
 zeros=[z for z in range(n)if all(t[z][x]==t[x][z]==z for x in range(n))]
 if not zeros:nil=None
 else:
  nonzero=universe-set(zeros);adj={a:{t[a][b]for b in universe}&nonzero for a in nonzero};memo={}
  def longest(a,ancestors):
   if a in ancestors:raise ValueError('cycle')
   if a not in memo:memo[a]=1+max((longest(b,ancestors|{a})for b in adj[a]),default=0)
   return memo[a]
  try:nil=1+max((longest(a,set())for a in nonzero),default=0)
  except ValueError:nil=None
 eq(m.semigroup_nilpotency_index(t),nil)
class Own(unittest.TestCase):
 def test_all_small_and_four(self):
  count=0
  for n in range(1,4):
   for cells in it.product(range(n),repeat=n*n):
    t=tuple(tuple(cells[i*n:(i+1)*n])for i in range(n))
    if all(t[t[a][b]][c]==t[a][t[b][c]]for a,b,c in it.product(range(n),repeat=3)):check(t);count+=1
  assert count==122
  four=[tuple(tuple(f(a,b)for b in range(4))for a in range(4))for f in(lambda a,b:min(a,b),lambda a,b:max(a,b),lambda a,b:a,lambda a,b:b,lambda a,b:(a+b)%4,lambda a,b:min(3,a+b+1),lambda a,b:0)]
  funcs=list(it.product(range(2),repeat=2));four.append(tuple(tuple(funcs.index(tuple(f[g[x]]for x in range(2)))for g in funcs)for f in funcs))
  for t in four:check(t)
if __name__=='__main__':unittest.main(exit=False);print('checks',checks)
