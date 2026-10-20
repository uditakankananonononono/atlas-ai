# c28: Hopfield (Hebbian) magnitude pruning vs random pruning, retrieval overlap under cue noise, by load. Scouting, synthetic seeds 880012000-009, 0 fixture seeds.
import numpy as np
N=200
def run(alpha,keep,mode,seed,flip=0.15,T=6):
    r=np.random.default_rng(seed);P=int(alpha*N);X=r.choice([-1,1],(P,N));W=X.T@X/N;np.fill_diagonal(W,0)
    off=np.abs(W[np.triu_indices(N,1)])
    if keep<1:
        if mode=='mag':
            th=np.quantile(off,1-keep);M=np.abs(W)>=th
        else: 
            M=np.triu(r.random((N,N))<keep,1);M=M|M.T
        W=W*M
    ov=[]
    for p in range(min(P,20)):
        s=X[p]*np.where(r.random(N)<flip,-1,1)
        for _ in range(T): s=np.where(W@s>=0,1,-1)
        ov.append(abs(s@X[p])/N)
    return np.mean(ov)
for alpha in (0.05,0.10,0.14):
    out={}
    for keep in (1.0,0.5,0.25,0.1):
        for mode in (('mag','rand') if keep<1 else ('mag',)):
            out[f'{mode}{keep}']=round(float(np.mean([run(alpha,keep,mode,880012000+s) for s in range(10)])),3)
    print(alpha,out)
