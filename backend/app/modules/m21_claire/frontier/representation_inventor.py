from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from math import copysign, log1p, sqrt, isfinite
from typing import Any, Callable

@dataclass(frozen=True)
class TabularObservation:
    record_id: str
    split: str  # train, validation, confirmation
    features: dict[str, float]
    target: float
    source_group: str

class RepresentationInventor:
    """Searches a finite symbolic feature language with a sealed confirmation set.

    Selection occurs on validation only. The confirmation set is touched exactly once,
    after selecting a candidate. The system retains the transformed feature only if it
    improves over the baseline there too. This is a CPU-friendly scientific prototype,
    not a universal abstraction-discovery system.
    """
    def __init__(self, ridge: float=1e-5, max_candidates: int=120):
        self.ridge=max(1e-8,min(float(ridge),1.0)); self.max_candidates=max(10,min(int(max_candidates),500))

    def search(self, observations: list[TabularObservation], *, min_validation_gain: float=0.03,
               min_confirmation_gain: float=0.01) -> dict[str,Any]:
        if not 12<=len(observations)<=10000: raise ValueError("need 12..10000 total observations")
        if not 0<=min_validation_gain<1 or not 0<=min_confirmation_gain<1: raise ValueError("gain thresholds must be [0,1)")
        ids=[o.record_id for o in observations]
        if len(set(ids))!=len(ids): raise ValueError("record_id values must be unique across all splits")
        splits={k:[o for o in observations if o.split==k] for k in ("train","validation","confirmation")}
        if any(not rows for rows in splits.values()): raise ValueError("train, validation, confirmation splits are all required")
        if len(splits["train"])<6 or len(splits["validation"])<3 or len(splits["confirmation"])<3:
            raise ValueError("minimum split sizes: train 6, validation 3, confirmation 3")
        features=sorted({k for o in splits["train"] for k in o.features})  # vocabulary from train only
        extra=sorted({k for o in observations if o.split!="train" for k in o.features}-set(features))
        if extra: raise ValueError(f"validation/confirmation rows use feature names absent from train: {extra[:10]}")
        if not features or len(features)>15: raise ValueError("need 1..15 candidate feature columns")
        for o in observations:
            if o.split not in splits: raise ValueError("unknown split name")
            if not o.source_group.strip(): raise ValueError("source_group is required for provenance/independence checks")
            if not isfinite(float(o.target)): raise ValueError("targets must be finite")
            for name,val in o.features.items():
                if not isfinite(float(val)): raise ValueError(f"non-finite value for {name}")
        # Exact row duplicates crossing any boundary are blocked; source groups across sets are reported.
        signature_splits={}
        for o in observations:
            sig=tuple(sorted((k,float(v)) for k,v in o.features.items()))  # input only: a changed label is still the same row
            signature_splits.setdefault(sig,set()).add(o.split)
        leaked=[s for s,sp in signature_splits.items() if len(sp)>1]
        group_splits={}
        for o in observations: group_splits.setdefault(o.source_group,set()).add(o.split)
        group_leaks=sorted(g for g,sp in group_splits.items() if len(sp)>1)
        if leaked: raise ValueError("exact duplicate observations cross train/validation/confirmation split")
        if group_leaks: raise ValueError(f"source groups cross split boundaries: {group_leaks[:10]}")

        baseline_fns=[(f"raw:{f}",lambda row,f=f:float(row.features.get(f,0))) for f in features]
        baseline=self._evaluate(splits,baseline_fns,confirmation=False)
        candidates=self._candidate_functions(features)
        scored=[]
        for name, fn in candidates:
            funcs=baseline_fns+[(name,fn)]
            result=self._evaluate(splits,funcs,confirmation=False)
            gain=self._gain(baseline["validation_rmse"],result["validation_rmse"])
            scored.append({"name":name,"validation_rmse":result["validation_rmse"],"validation_gain":gain,"feature_fn":fn})
        scored.sort(key=lambda x:(-x["validation_gain"],x["name"]))
        best=next((x for x in scored if x["validation_gain"]>=min_validation_gain),None)
        if best is None:
            return {"status":"no_candidate_cleared_validation_gate","baseline":{"train_rmse":baseline["train_rmse"],"validation_rmse":baseline["validation_rmse"]},
                "candidate_count":len(scored),"best_validation_candidate":{k:v for k,v in scored[0].items() if k!="feature_fn"} if scored else None,
                "confirmation_used":False,"retained_representation":None}
        chosen_fns=baseline_fns+[(best["name"],best["feature_fn"])]
        # The confirmation split is first accessed only after candidate selection is frozen.
        confirmed_baseline=self._evaluate(splits,baseline_fns,confirmation=True)
        confirmed=self._evaluate(splits,chosen_fns,confirmation=True)
        confirm_gain=self._gain(confirmed_baseline["confirmation_rmse"],confirmed["confirmation_rmse"])
        accepted=confirm_gain>=min_confirmation_gain
        return {"status":"representation_retained" if accepted else "rejected_on_confirmation",
            "baseline":{"train_rmse":baseline["train_rmse"],"validation_rmse":baseline["validation_rmse"],"confirmation_rmse":confirmed_baseline["confirmation_rmse"]},
            "selected_on_validation":{"name":best["name"],"validation_gain":best["validation_gain"],"validation_rmse":best["validation_rmse"]},
            "confirmation":{"baseline_rmse":confirmed_baseline["confirmation_rmse"],"candidate_rmse":confirmed["confirmation_rmse"],"relative_gain":confirm_gain,"used_for_selection":False},
            "candidate_count":len(scored),"searched_language":"raw features + square + signed-log + absolute-value + pairwise product + difference + safe ratio",
            "retained_representation":{"name":best["name"],"formula":best["name"],"feature_combination":"raw columns plus this additional symbolic term",
                "train_fitted_readout":{"intercept":confirmed["coefficients"][0],
                    "raw_feature_weights":{f:confirmed["coefficients"][i+1] for i,f in enumerate(features)},
                    "new_dimension_weight":confirmed["coefficients"][-1],
                    "fit_data":"training split only"}} if accepted else None,
            "limitations":["Finite hand-authored operator grammar; not a search over all possible mathematics.","Requires sufficient independent source groups and a truly untouched confirmation set.","A good split can still be unrepresentative; replication is required."]}

    def _candidate_functions(self, features: list[str]):
        c=[]
        for f in features:
            c.extend([
              (f"square({f})",lambda o,f=f:float(o.features.get(f,0))**2),
              (f"abs({f})",lambda o,f=f:abs(float(o.features.get(f,0)))),
              (f"signed_log1p({f})",lambda o,f=f:copysign(log1p(abs(float(o.features.get(f,0)))),float(o.features.get(f,0))))])
        for a,b in combinations(features,2):
            c.extend([(f"product({a},{b})",lambda o,a=a,b=b:float(o.features.get(a,0))*float(o.features.get(b,0))),
              (f"difference({a},{b})",lambda o,a=a,b=b:float(o.features.get(a,0))-float(o.features.get(b,0))),
              (f"safe_ratio({a},{b})",lambda o,a=a,b=b:float(o.features.get(a,0))/(abs(float(o.features.get(b,0)))+1e-6))])
        return c[:self.max_candidates]

    def _evaluate(self,splits,functions,confirmation=True):
        train=splits["train"]
        matrix=[[1.0]+[fn(o) for _,fn in functions] for o in train]
        target=[float(o.target) for o in train]
        coefficients=self._ridge_fit(matrix,target)
        def rmse(rows):
            if not rows:return None
            errors=[]
            for o in rows:
                x=[1.0]+[fn(o) for _,fn in functions]; pred=sum(a*b for a,b in zip(coefficients,x)); errors.append((pred-float(o.target))**2)
            return sqrt(sum(errors)/len(errors))
        return {"train_rmse":rmse(train),"validation_rmse":rmse(splits["validation"]),
                "confirmation_rmse":rmse(splits["confirmation"]) if confirmation else None,"coefficients":coefficients}

    def _ridge_fit(self, x, y):
        n=len(x[0]); a=[[sum(row[i]*row[j] for row in x)+(self.ridge if i==j and i>0 else 0.0) for j in range(n)] for i in range(n)]
        b=[sum(row[i]*yy for row,yy in zip(x,y)) for i in range(n)]
        # Gaussian elimination with partial pivoting.
        for col in range(n):
            pivot=max(range(col,n),key=lambda r:abs(a[r][col]))
            if abs(a[pivot][col])<1e-12: a[pivot][col]+=1e-8
            if pivot!=col: a[col],a[pivot]=a[pivot],a[col]; b[col],b[pivot]=b[pivot],b[col]
            div=a[col][col]
            for j in range(col,n): a[col][j]/=div
            b[col]/=div
            for r in range(n):
                if r==col: continue
                mult=a[r][col]
                for j in range(col,n): a[r][j]-=mult*a[col][j]
                b[r]-=mult*b[col]
        return b

    @staticmethod
    def _gain(base: float, candidate: float) -> float:
        if base is None or candidate is None: return 0.0
        if base < 1e-12: return 0.0 if candidate >= base else 1.0
        return max(-1.0,min(1.0,(base-candidate)/base))
