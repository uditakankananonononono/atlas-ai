from __future__ import annotations
from math import exp, isfinite
from typing import Any
import copy, time
from typing import Protocol


class PreferenceStore(Protocol):
    """Persistence port. Atlas wiring supplies a tenant-scoped Postgres implementation."""
    def get_preferences(self, tenant_id: str) -> dict[str, dict[str, Any]]: ...
    def set_preference(self, tenant_id: str, key: str, value: dict[str, Any], source: str) -> None: ...
    def delete_preferences(self, tenant_id: str, *, key: str | None = None, key_prefix: str | None = None) -> int: ...


class InMemoryPreferenceStore:
    """Process-local reference store for tests; not durable."""
    def __init__(self) -> None: self._d: dict[str, dict[str, dict[str, Any]]] = {}
    def get_preferences(self, tenant_id): return {k: {"value": copy.deepcopy(v["value"]), "source": v["source"]} for k, v in self._d.get(tenant_id, {}).items()}
    def set_preference(self, tenant_id, key, value, source): self._d.setdefault(tenant_id, {})[key] = {"value": copy.deepcopy(value), "source": source}
    def delete_preferences(self, tenant_id, *, key=None, key_prefix=None):
        t = self._d.get(tenant_id, {}); gone = [k for k in t if (key is not None and k == key) or (key_prefix is not None and k.startswith(key_prefix))]
        for k in gone: del t[k]
        return len(gone)

class PreferenceCodec:
    """Inspectable pairwise preference model; models tastes, not a person's whole mind."""
    def __init__(self, store, learning_rate: float=0.12, l2: float=0.015):
        self.store=store; self.learning_rate=learning_rate; self.l2=l2
        if not 0 < learning_rate <= 1 or not 0 <= l2 <= 1: raise ValueError("invalid optimizer settings")

    def _key(self, dimension: str) -> str:
        # No truncation: truncating would silently merge distinct dimensions.
        if not isinstance(dimension, str) or not dimension.strip() or len(dimension) > 80:
            raise ValueError("dimension must be a non-empty string of at most 80 characters")
        return "frontier_preference:"+dimension

    def get(self, tenant_id: str, dimension: str) -> dict[str,Any]:
        found=self.store.get_preferences(tenant_id).get(self._key(dimension))
        return copy.deepcopy(found["value"]) if found else {"dimension":dimension,"weights":{},"comparisons":0,"updated_at":None}

    def compare(self, tenant_id: str, dimension: str, features_a: dict[str,float], features_b: dict[str,float], preferred: str,
                *, source: str="explicit_user_pairwise_choice") -> dict[str,Any]:
        if preferred not in {"a","b","tie"}: raise ValueError("preferred must be a, b, or tie")
        if not dimension.strip() or len(features_a)>100 or len(features_b)>100: raise ValueError("dimension required; max 100 features per option")
        all_keys=set(features_a)|set(features_b)
        if not all_keys: raise ValueError("at least one preference feature is required")
        if any(not isinstance(k,str) or not k.strip() or len(k)>100 for k in all_keys): raise ValueError("preference feature names must be non-empty and at most 100 characters")
        if any(not isinstance(v,(int,float)) or not isfinite(float(v)) or abs(float(v))>1000 for v in list(features_a.values())+list(features_b.values())): raise ValueError("features must be finite small numbers")
        model=self.get(tenant_id,dimension); weights={k:float(v) for k,v in model["weights"].items()}
        delta={k:float(features_a.get(k,0))-float(features_b.get(k,0)) for k in all_keys}
        z=sum(weights.get(k,0)*v for k,v in delta.items()); z=max(-40,min(40,z)); p=1/(1+exp(-z))
        y=0.5 if preferred=="tie" else (1.0 if preferred=="a" else 0.0)
        # A tie supplies weaker evidence: half-rate update.
        rate=self.learning_rate*(0.35 if preferred=="tie" else 1.0)
        for k in all_keys: weights[k]=weights.get(k,0)+rate*((y-p)*delta[k]-self.l2*weights.get(k,0))
        model.update({"dimension":dimension,"weights":{k:round(v,8) for k,v in sorted(weights.items())},
                      "comparisons":int(model.get("comparisons",0))+1,"updated_at":time.time(),
                      "last_choice":preferred,"provenance":source,"confidence":"low" if int(model.get("comparisons",0))<5 else "still heuristic; validate with new comparisons"})
        self.store.set_preference(tenant_id,self._key(dimension),model,source)
        return copy.deepcopy(model)

    def score(self, tenant_id: str, dimension: str, features: dict[str,float]) -> dict[str,Any]:
        if len(features)>100 or any(not isinstance(k,str) or not k.strip() or not isinstance(v,(int,float)) or not isfinite(float(v)) or abs(float(v))>1000 for k,v in features.items()):
            raise ValueError("features must be a bounded map of finite numbers")
        model=self.get(tenant_id,dimension); score=sum(float(model["weights"].get(k,0))*float(v) for k,v in features.items())
        return {"dimension":dimension,"score":round(score,8),"comparisons":model["comparisons"],"confidence":model.get("confidence","low"),
                "explanation":{"contributions":{k:round(float(model["weights"].get(k,0))*float(v),8) for k,v in features.items()},
                               "note":"Inspectable preference estimate, not a simulation of the user's full cognition."}}

    def erase(self, tenant_id: str, dimension: str | None=None) -> int:
        if dimension: return self.store.delete_preferences(tenant_id, key=self._key(dimension))
        # Erase only this subsystem's preferences, not all user preferences.
        return self.store.delete_preferences(tenant_id, key_prefix="frontier_preference:")
