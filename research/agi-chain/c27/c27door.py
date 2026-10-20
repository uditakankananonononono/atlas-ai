# c27: real DoOR odor statistics vs iid abs-Gaussian prototypes; expansion(random sparse, k=5% WTA) vs raw nearest-prototype. Scouting, synthetic seeds 880011000-007, 0 fixture seeds.
import pandas as pd,numpy as np
d=pd.read_csv('door_response_matrix.csv',sep=';',quotechar='"');d.columns=[c.strip('"') for c in d.columns]
M=d.apply(pd.to_numeric,errors='coerce');M=M.drop(columns=[c for c in M if M[c].isna().all()])
cols=M.columns[M.notna().sum(0)>=100]; X=M[cols]; X=X[X.notna().sum(1)>=int(0.7*len(cols))]
X=X.fillna(X.mean()).values; print('odors',X.shape[0],'receptors',X.shape[1])
def enc(Wm,x,k):
    h=Wm@x;o=np.zeros_like(h);o[np.argsort(-h)[:k]]=1;return o
def run(P,r,noise,expand,C=10,shots=3,N=20,m=1000,deg=6):
    d=P.shape[1]; idx=r.choice(len(P),C,replace=False); pro=P[idx]; sd=pro.std()
    if expand:
        Wm=np.zeros((m,d))
        for i in range(m): Wm[i,r.choice(d,deg,replace=False)]=1
        f=lambda x:enc(Wm,x,int(.05*m))
    else: f=lambda x:x
    mu=np.array([np.mean([f(pro[c]+noise*sd*r.standard_normal(d)) for _ in range(shots)],0) for c in range(C)])
    ok=0
    for c in range(C):
        for _ in range(N): ok+=np.argmax(mu@f(pro[c]+noise*sd*r.standard_normal(d)))==c
    return ok/(C*N)
for nz in (0.5,1.0,1.5):
  out={}
  for name in ('real','iid'):
    for ex in (0,1):
      v=[]
      for s in range(8):
        r=np.random.default_rng(880011000+s)
        P=X if name=='real' else np.abs(r.standard_normal(X.shape))*X.std()+0
        v.append(np.mean([run(P,np.random.default_rng(1000*s+t),nz,ex) for t in range(10)]))
      out[f'{name}_{"exp" if ex else "raw"}']=round(float(np.mean(v)),3)
  print(nz,out)
