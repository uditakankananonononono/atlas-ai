# c29: NK landscape (N=16,K=4), asexual GA, final fitness vs per-site mutation rate by population size. Scouting seeds 880013000-.., 0 fixture seeds.
import numpy as np
N,K=16,4
def land(r):
    nb=np.array([[i]+list(r.choice([j for j in range(N) if j!=i],K,replace=False)) for i in range(N)]);tab=r.random((N,2**(K+1)));return nb,tab
def fit(g,nb,tab):
    idx=(g[:,nb]*(2**np.arange(K+1))).sum(2);return tab[np.arange(N),idx].mean(1)
def run(pop,mu,seed,gens=150):
    r=np.random.default_rng(seed);nb,tab=land(r);g=r.integers(0,2,(pop,N))
    for _ in range(gens):
        f=fit(g,nb,tab);a=r.integers(0,pop,(pop,2));w=np.where(f[a[:,0]]>=f[a[:,1]],a[:,0],a[:,1])
        g=g[w]^(r.random((pop,N))<mu)
    return fit(g,nb,tab).max()
for pop in (10,100):
    print(pop,{mu:round(float(np.mean([run(pop,mu,880013000+s) for s in range(30)])),4) for mu in (0.002,0.01,0.03,0.1,0.25)})
