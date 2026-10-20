# c30: k-WTA (global competition) vs fixed-threshold expansion code, nearest-prototype ID, by input correlation rho and gain drift. Scouting seeds 880014000-007, 0 fixture seeds.
import numpy as np
d,m,C=40,800,10
def run(rho,gain,mode,seed,noise=1.0,N=20,shots=3):
    r=np.random.default_rng(seed);common=r.standard_normal(d)
    pro=np.sqrt(rho)*common+np.sqrt(1-rho)*r.standard_normal((C,d))
    Wm=(r.random((m,d))<6/d).astype(float);Wm*=1
    h0=Wm@pro.T;theta=np.quantile(h0,0.95)
    def f(x,g):
        h=g*(Wm@x)
        if mode=='wta':
            o=np.zeros(m);o[np.argsort(-h)[:int(.05*m)]]=1;return o
        return (h>theta).astype(float)
    def samp(c,g):return f(pro[c]+noise*np.std(pro)*r.standard_normal(d),g)
    mu=np.array([np.mean([samp(c,1.0) for _ in range(shots)],0) for c in range(C)])
    ok=0
    for c in range(C):
        for _ in range(N):ok+=np.argmax(mu@samp(c,gain))==c
    return ok/(C*N)
for rho in (0.0,0.5,0.9):
    out={}
    for gain in (1.0,1.5):
        for mode in ('wta','thr'):
            out[f'{mode}_g{gain}']=round(float(np.mean([run(rho,gain,mode,880014000+s*10+t) for s in range(8) for t in range(5)])),3)
    print(rho,out)
