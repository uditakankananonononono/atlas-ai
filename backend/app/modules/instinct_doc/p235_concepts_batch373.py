"""P235 b373: exact finite associative semigroup structure.
Every public function takes table:exact tuple of1..4 exact tuple rows,
each length n,entries exact ints0..n-1. Validate outer/count,each row
shape/length,then each row's entry types before ranges,then associativity.
Outputs fresh lists/tuples of exact ints,canonical lexicographic order.
Power orbit:(preperiod tuple,cycle tuple),starting a^1.
Generating sets:inclusion-minimal nonempty subsets,not just minimum size.
Green L/R classes compare principal ideals with identity adjoined.
Ideals:nonempty two-sided absorbing subsets. Congruences:canonical block
partitions,blocks/elements sorted. Automorphisms:permutation tuples.
Regular inverses row a:all b with aba=a,bab=b. Nilpotency:least positive
length k for which all k-fold products equal a two-sided zero,None if
absent;S^k stabilizes within n strict descents. Idempotent-generated
subsemigroup:all products of idempotents,sorted.
No infinite semigroups,free-group words or group-presentation inference.
"""
import itertools as it
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: exact bounded finite semigroup structure,not free-group reduction or group-presentation solving'
NOT_CLAIMED=('infinite semigroups','group presentation solving','global novelty','production readiness')


def _check(name,table):
 f=make_fail(name)
 if type(table) is not tuple:f('bad_type:table')
 n=len(table)
 if not 1<=n<=4:f('bad_value:size')
 for row in table:
  if type(row) is not tuple:f('bad_type:row')
  if len(row)!=n:f('bad_value:row_length')
  if any(type(v) is not int for v in row):f('bad_type:entry')
  if any(not 0<=v<n for v in row):f('bad_value:entry')
 if any(table[table[a][b]][c]!=table[a][table[b][c]] for a,b,c in it.product(range(n),repeat=3)):f('bad_value:associativity')
 return n


def semigroup_power_orbits(table):
 n=_check('semigroup_power_orbits',table);result=[]
 for a in range(n):
  seq=[];positions={};v=a
  while v not in positions:positions[v]=len(seq);seq.append(v);v=table[v][a]
  split=positions[v];result.append((tuple(seq[:split]),tuple(seq[split:])))
 return result


def semigroup_minimal_generating_sets(table):
 n=_check('semigroup_minimal_generating_sets',table);result=[]
 for size in range(1,n+1):
  for seed in it.combinations(range(n),size):
   if any(set(old)<=set(seed) for old in result):continue
   generated=set(seed)
   while True:
    new=generated|{table[a][b] for a in generated for b in generated}
    if new==generated:break
    generated=new
   if len(generated)==n:result.append(seed)
 return sorted(result)


def semigroup_green_l_classes(table):
 n=_check('semigroup_green_l_classes',table);groups={}
 for a in range(n):groups.setdefault(frozenset([a]+[table[x][a] for x in range(n)]),[]).append(a)
 return sorted(tuple(group) for group in groups.values())


def semigroup_green_r_classes(table):
 n=_check('semigroup_green_r_classes',table);unclassified=set(range(n));result=[]
 while unclassified:
  a=min(unclassified);ideal={a,*table[a]};group=[]
  for b in sorted(unclassified):
   if {b,*table[b]}==ideal:group.append(b)
  result.append(tuple(group));unclassified.difference_update(group)
 return result


def semigroup_two_sided_ideals(table):
 n=_check('semigroup_two_sided_ideals',table);result=[]
 for mask in range(1,1<<n):
  members=tuple(a for a in range(n) if mask>>a&1)
  if all(table[x][a] in members and table[a][x] in members for a in members for x in range(n)):result.append(members)
 return sorted(result)


def semigroup_congruences(table):
 n=_check('semigroup_congruences',table);result=[]
 def grow(labels):
  if len(labels)==n:
   if all(labels[table[x][a]]==labels[table[x][b]] and labels[table[a][x]]==labels[table[b][x]] for a in range(n) for b in range(n) if labels[a]==labels[b] for x in range(n)):
    result.append(tuple(tuple(i for i in range(n) if labels[i]==j) for j in range(max(labels)+1)))
   return
  for label in range(max(labels)+2):grow(labels+(label,))
 grow((0,))
 return sorted(result)


def semigroup_automorphisms(table):
 n=_check('semigroup_automorphisms',table)
 return [p for p in it.permutations(range(n)) if all(p[table[a][b]]==table[p[a]][p[b]] for a,b in it.product(range(n),repeat=2))]


def semigroup_regular_inverses(table):
 n=_check('semigroup_regular_inverses',table)
 return [tuple(b for b in range(n) if table[table[a][b]][a]==a and table[table[b][a]][b]==b) for a in range(n)]


def semigroup_nilpotency_index(table):
 n=_check('semigroup_nilpotency_index',table);zeros=[z for z in range(n) if all(table[z][a]==z and table[a][z]==z for a in range(n))]
 if not zeros:return None
 values=set(range(n));length=1
 while True:
  if values==set(zeros):return length
  new={table[a][b] for a in values for b in range(n)}
  if new==values:return None
  values=new;length+=1


def semigroup_idempotent_generated_subsemigroup(table):
 n=_check('semigroup_idempotent_generated_subsemigroup',table);generators=[a for a in range(n) if table[a][a]==a];reached=set(generators);todo=list(generators)
 for a in todo:
  for e in generators:
   b=table[a][e]
   if b not in reached:reached.add(b);todo.append(b)
 return sorted(reached)
