import itertools as it,random,unittest
from fractions import Fraction
from functools import lru_cache
from app.modules.instinct_doc import p235_concepts_batch329 as m
checks=0
def eq(a,b):
 global checks
 assert a==b,(a,b);checks+=1
class Independent(unittest.TestCase):
 def test_routes(self):
  rng=random.Random(1329);cases=[(n,list(h))for n in range(4)for k in range(1,min(6,2**n)+1)for h in it.combinations(range(2**n),k)]+[(4,sorted(rng.sample(range(16),rng.randrange(1,7))))for _ in range(100)]
  for n,h in cases:
   labels={x:tuple(int(c)for c in format(x,'0%db'%max(1,n))[::-1][:n])for x in h};subsets=[tuple(i for i in range(n)if s//2**i%2)for s in range(2**n)]
   def trace(x,S):return tuple(labels[x][i]for i in S)
   shattered=[s for s,S in enumerate(subsets)if all(any(trace(x,S)==p for x in h)for p in it.product((0,1),repeat=len(S)))];d=max(len(subsets[s])for s in shattered)
   eq(m.flearn_shattered_coordinate_sets(n,h),shattered)
   cert=[]
   for s in shattered:
    if len(subsets[s])==d:
     patterns=sorted({sum(labels[x][i]*2**i for i in subsets[s])for x in h});cert.append((s,[min(x for x in h if sum(labels[x][i]*2**i for i in subsets[s])==p)for p in patterns]))
   eq(m.flearn_vc_dimension_witnesses(n,h),(d,cert))
   def teaches(v):
    out=[]
    for x in v:
     candidates=[s for s,S in enumerate(subsets)if sum(trace(y,S)==trace(x,S)for y in v)==1];k=min(len(subsets[s])for s in candidates);out.append((x,[s for s in candidates if len(subsets[s])==k]))
    return out
   eq(m.flearn_minimum_teaching_sets(n,h),teaches(h));left=h[:];layers=[]
   while left:
    t=teaches(left);low=min(len(subsets[s[0]])for x,s in t);removed=[x for x,s in t if len(subsets[s[0]])==low];layers.append((low,removed));left=[x for x in left if x not in removed]
   eq(m.flearn_recursive_teaching_layers(n,h),layers)
   @lru_cache(None)
   def trees(v):
    # Return both adversarial-complete and identification optima using explicit label partitions.
    if len(v)==1:return (0,None),(0,v[0])
    splits=[(i,tuple(x for x in v if labels[x][i]==0),tuple(x for x in v if labels[x][i]==1))for i in range(n)];splits=[t for t in splits if t[1]and t[2]]
    adv=[];query=[]
    for i,a,b in splits:
     aa,aq=trees(a);ba,bq=trees(b);adv.append((1+min(aa[0],ba[0]),i,a,b));query.append((1+max(aq[0],bq[0]),i,aq[1],bq[1]))
    ad=max(t[0]for t in adv);qd,qi,qa,qb=min(query,key=lambda t:t[:2]);ai,a,b=next((i,a,b)for d,i,a,b in adv if d==ad)
    def complete(v,d):
     if not d:return None
     for i in range(n):
      a=tuple(x for x in v if not labels[x][i]);b=tuple(x for x in v if labels[x][i])
      if a and b and min(trees(a)[0][0],trees(b)[0][0])>=d-1:return i,complete(a,d-1),complete(b,d-1)
    return(ad,complete(v,ad)),(qd,(qi,qa,qb))
   ad,qd=trees(tuple(h));eq(m.flearn_littlestone_optimal_tree(n,h),ad);eq(m.flearn_optimal_membership_query_tree(n,h),qd)
   stars=[]
   for x in h:
    for s,S in enumerate(subsets):
     spokes=[]
     for i in S:
      cand=[y for y in h if all(labels[y][j]==(1-labels[x][j]if j==i else labels[x][j])for j in S)]
      if not cand:break
      spokes.append(min(cand))
     else:stars.append((x,s,spokes))
   k=max(len(subsets[s])for x,s,p in stars);eq(m.flearn_star_number_witnesses(n,h),(k,[t for t in stars if len(subsets[t[1]])==k]))
   for x in h:
    radii=[]
    for r in range(1,n+1):
     ball=[y for y in h if sum(a!=b for a,b in zip(labels[x],labels[y]))<=r];D=[i for i in range(n)if any(labels[y][i]!=labels[x][i]for y in ball)];radii.append((Fraction(len(D),r),r,sum(2**i for i in D)))
    k=max((t[0]for t in radii),default=Fraction(0));eq(m.flearn_disagreement_coefficient(n,h,x),(k,[(r,s)for v,r,s in radii if v==k]))
   sample=[[rng.randrange(n),rng.randrange(2)]for _ in range(8)]if n else[];cost=[sum(labels[x][i]!=b for i,b in sample)for x in h];eq(m.flearn_minimum_consistent_sample_errors(n,h,sample),(min(cost),[x for x,c in zip(h,cost)if c==min(cost)]))
   good=[]
   for k in range(n+1):
    for seq in it.permutations(range(n),k):
     if all(any(trace(a,seq[:j])==trace(b,seq[:j])and labels[a][i]!=labels[b][i]for a,b in it.combinations(h,2))for j,i in enumerate(seq)):good.append(list(seq))
   k=max(map(len,good));eq(m.flearn_eluder_independent_sequences(n,h),sorted(s for s in good if len(s)==k))
if __name__=='__main__':unittest.main(exit=False);print('checks',checks)
