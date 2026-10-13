"""Bounded research engine for Claire's representation/experiment/learning loop.

This is a reproducible research harness, not AGI. It searches a small, explicit
symbolic grammar; evaluates on caller-supplied held-out examples; and reports
failures rather than self-certifying broad capability claims.

No eval/exec, shell, arbitrary code generation, model weights, or external side
 effects are used here. The expression interpreter has explicit depth and node caps.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("expression values must be finite numbers")
    return float(value)


def eval_expr(expr: dict[str, Any], row: dict[str, Any], *, max_depth: int = 10, max_nodes: int = 80) -> float:
    """Evaluate the safe symbolic DSL. Only allow-listed nodes are accepted."""
    node_counter = [0]
    def visit(node: Any, depth: int) -> float:
        node_counter[0] += 1
        if node_counter[0] > max_nodes or depth > max_depth:
            raise ValueError("expression budget exceeded")
        if not isinstance(node, dict):
            raise ValueError("expression node must be an object")
        op = node.get("op")
        if op == "field":
            name = node.get("name")
            if not isinstance(name, str) or name not in row:
                raise ValueError(f"missing field: {name}")
            return _num(row[name])
        if op == "const":
            return _num(node.get("value"))
        args = node.get("args", [])
        if not isinstance(args, list) or len(args) > 4:
            raise ValueError("args must be a list of at most 4 values")
        vals = [visit(a, depth + 1) for a in args]
        if op == "abs" and len(vals) == 1: return abs(vals[0])
        if op == "square" and len(vals) == 1: return vals[0] * vals[0]
        if op == "sqrt_abs" and len(vals) == 1: return math.sqrt(abs(vals[0]))
        if op == "log1p_abs" and len(vals) == 1: return math.log1p(abs(vals[0]))
        if op == "neg" and len(vals) == 1: return -vals[0]
        if op == "add" and len(vals) == 2: return vals[0] + vals[1]
        if op == "sub" and len(vals) == 2: return vals[0] - vals[1]
        if op == "mul" and len(vals) == 2: return vals[0] * vals[1]
        if op == "div" and len(vals) == 2:
            if abs(vals[1]) < 1e-12: raise ValueError("division by near-zero")
            return vals[0] / vals[1]
        if op == "min" and len(vals) == 2: return min(vals)
        if op == "max" and len(vals) == 2: return max(vals)
        raise ValueError(f"unsupported operation or arity: {op}")
    out = visit(expr, 0)
    if not math.isfinite(out) or abs(out) > 1e100:
        raise ValueError("expression result is outside numeric safety bounds")
    return out


def expr_complexity(expr: dict[str, Any]) -> int:
    if expr.get("op") in {"field", "const"}: return 1
    return 1 + sum(expr_complexity(a) for a in expr.get("args", []) if isinstance(a, dict))


def _numeric_fields(rows: Sequence[dict[str, Any]]) -> list[str]:
    if not rows: return []
    fields = set.intersection(*(set(r.keys()) for r in rows))
    return sorted(k for k in fields if all(
        isinstance(r[k], (int, float)) and not isinstance(r[k], bool) and math.isfinite(float(r[k]))
        for r in rows
    ))


def _resolve_task_type(task_type: str, targets: Sequence[Any]) -> str:
    if task_type in {"classification", "regression"}: return task_type
    if task_type != "auto": raise ValueError("task_type must be auto, classification, or regression")
    numeric=all(isinstance(y,(int,float)) and not isinstance(y,bool) and math.isfinite(float(y)) for y in targets)
    # Prefer explicit task_type when numeric classes have high cardinality; auto is only a heuristic.
    unique_targets = {json.dumps(y, sort_keys=True, separators=(",", ":"), default=str) for y in targets}
    return "regression" if numeric and len(unique_targets) > max(4,len(targets)//2) else "classification"


def _knn_predict(train: Sequence[dict[str, Any]], vector_fn: Callable[[dict[str, Any]], list[float]],
                 row: dict[str, Any], *, k: int = 3, metric: str = "euclidean", task_type: str="auto") -> Any:
    if not train: raise ValueError("training cases cannot be empty")
    resolved=_resolve_task_type(task_type,[c["expected"] for c in train])
    vectors = [vector_fn(c["input"]) for c in train]
    q = vector_fn(row)
    if not q or any(len(v) != len(q) for v in vectors): raise ValueError("inconsistent feature dimensions")
    mins = [min(v[j] for v in vectors) for j in range(len(q))]
    spans = [max(1e-9, max(v[j] for v in vectors) - mins[j]) for j in range(len(q))]
    def dist(v):
        diffs = [abs((v[j] - q[j]) / spans[j]) for j in range(len(q))]
        return sum(diffs) if metric == "manhattan" else math.sqrt(sum(d*d for d in diffs))
    nearest = sorted(((dist(v), c["expected"]) for v, c in zip(vectors, train)), key=lambda p: p[0])[:max(1, min(k, len(train)))]
    targets = [y for _, y in nearest]
    if resolved=="regression": return statistics.mean(float(y) for y in targets)
    weighted = Counter()
    for d, y in nearest: weighted[str(type(y).__name__) + ":" + json.dumps(y, sort_keys=True, default=str)] += 1.0 / (1e-6 + d)
    key = max(weighted, key=weighted.get)
    for y in targets:
        if str(type(y).__name__) + ":" + json.dumps(y, sort_keys=True, default=str) == key: return y
    return targets[0]


def _score_predictions(cases: Sequence[dict[str, Any]], preds: Sequence[Any], *, task_type: str="auto",
                       reference_targets: Sequence[Any] | None=None) -> dict[str, Any]:
    if not cases: raise ValueError("held-out cases cannot be empty")
    if len(cases)!=len(preds): raise ValueError("predictions count must match cases")
    ys = [c["expected"] for c in cases]
    resolved=_resolve_task_type(task_type,list(reference_targets) if reference_targets is not None else ys)
    if resolved=="regression":
        if not all(isinstance(y,(int,float)) and not isinstance(y,bool) for y in ys):
            raise ValueError("regression task requires numeric expected values")
        ref=list(reference_targets) if reference_targets else ys
        scale=max(1e-9,max(float(y) for y in ref)-min(float(y) for y in ref))
        mae=statistics.mean(abs(float(a)-float(y)) for a,y in zip(preds,ys))
        return {"metric":"normalized_mae","score":1.0-mae/scale,"mae":mae,
                "passed":sum(abs(float(a)-float(y))<=.1*scale for a,y in zip(preds,ys)),"total":len(ys),"task_type":"regression","normalization_range":scale}
    correct=sum(a==y for a,y in zip(preds,ys))
    return {"metric":"accuracy","score":correct/len(ys),"correct":correct,"total":len(ys),"task_type":"classification"}


@dataclass(frozen=True)
class RepresentationResult:
    representation: list[dict[str, Any]]
    score: float
    metric: str
    complexity: int
    adjusted_score: float
    predictions_hash: str


class RepresentationInventor:
    """Search bounded symbolic feature spaces and keep only held-out winners."""
    def __init__(self, *, max_candidates: int = 160, complexity_penalty: float = 0.002):
        if not 8 <= max_candidates <= 2000: raise ValueError("max_candidates must be in [8, 2000]")
        if not 0 <= complexity_penalty <= .1: raise ValueError("complexity_penalty must be in [0, .1]")
        self.max_candidates, self.complexity_penalty = max_candidates, complexity_penalty

    def candidates(self, rows: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        fields = _numeric_fields(rows)
        atoms = [{"op": "field", "name": f} for f in fields]
        candidates: list[list[dict[str, Any]]] = [[a] for a in atoms]
        for a in atoms:
            for op in ("abs", "square", "sqrt_abs", "log1p_abs", "neg"):
                candidates.append([{"op": op, "args": [a]}])
        # Pairwise operators provide compact new coordinate systems (differences,
        # ratios and interactions), not arbitrary generated code.
        for a, b in itertools.combinations(atoms, 2):
            for op in ("add", "sub", "mul", "div", "min", "max"):
                candidates.append([{"op": op, "args": [a, b]}])
        candidates.append(atoms[:min(4, len(atoms))])
        unique, seen = [], set()
        for rep in candidates:
            sig = _hash(rep)
            if sig not in seen:
                seen.add(sig); unique.append(rep)
            if len(unique) >= self.max_candidates: break
        return unique

    @staticmethod
    def _vector(rep: list[dict[str, Any]], row: dict[str, Any]) -> list[float]:
        return [eval_expr(e, row) for e in rep]

    def search(self, train: Sequence[dict[str, Any]], validation: Sequence[dict[str, Any]],
               confirmation: Sequence[dict[str, Any]] | None = None, *, top_k: int = 10, task_type: str="auto") -> dict[str, Any]:
        """Select on validation; evaluate the selected representation once on confirmation."""
        if len(train) < 2 or not validation: raise ValueError("need >=2 train cases and >=1 validation case")
        if confirmation is not None and not confirmation: raise ValueError("confirmation set cannot be empty")
        all_cases=[*train,*validation,*(confirmation or [])]
        if any("input" not in x or "expected" not in x for x in all_cases):
            raise ValueError("each case needs input and expected")
        resolved_task=_resolve_task_type(task_type,[x["expected"] for x in train])
        fields = _numeric_fields([x["input"] for x in train])
        if not fields: raise ValueError("training cases have no shared numeric input fields")
        scored = []
        for rep in self.candidates([x["input"] for x in train]):
            try:
                vf = lambda row, _rep=rep: self._vector(_rep, row)
                preds = [_knn_predict(train, vf, case["input"], task_type=resolved_task) for case in validation]
                scores = _score_predictions(validation, preds, task_type=resolved_task, reference_targets=[x["expected"] for x in train])
                complexity = sum(expr_complexity(e) for e in rep)
                adjusted = scores["score"] - self.complexity_penalty * complexity
                scored.append(RepresentationResult(rep, scores["score"], scores["metric"], complexity,
                                                    adjusted, _hash(preds)))
            except (ValueError, ZeroDivisionError, OverflowError):
                continue
        baseline_rep = [{"op":"field", "name":f} for f in fields[:8]]
        baseline_preds = [_knn_predict(train, lambda row: self._vector(baseline_rep, row), c["input"], task_type=resolved_task) for c in validation]
        baseline = _score_predictions(validation, baseline_preds, task_type=resolved_task, reference_targets=[x["expected"] for x in train])
        scored.sort(key=lambda r: (r.adjusted_score, r.score, -r.complexity), reverse=True)
        best = scored[0] if scored else None
        confirmation_report = None
        best_payload = asdict(best) if best else None
        if best is not None and confirmation is not None:
            selected_vf=lambda row:self._vector(best.representation,row)
            confirm_preds=[_knn_predict(train,selected_vf,c["input"],task_type=resolved_task) for c in confirmation]
            confirm_scores=_score_predictions(confirmation,confirm_preds,task_type=resolved_task,reference_targets=[x["expected"] for x in train])
            baseline_confirm_preds=[_knn_predict(train,lambda row:self._vector(baseline_rep,row),c["input"],task_type=resolved_task) for c in confirmation]
            baseline_confirm=_score_predictions(confirmation,baseline_confirm_preds,task_type=resolved_task,reference_targets=[x["expected"] for x in train])
            confirmation_report={"selected_representation":confirm_scores,"baseline":baseline_confirm,
                                 "improvement_over_baseline":confirm_scores["score"]-baseline_confirm["score"],
                                 "selected_prediction_hash":_hash(confirm_preds),"candidate_selection_used_confirmation":False}
            best_payload["confirmation_score"] = confirm_scores["score"]
            best_payload["confirmation_metric"] = confirm_scores["metric"]
        return {
            "candidate_count": len(scored), "task_type": resolved_task, "selection_baseline": baseline, "baseline": baseline,
            "best": best_payload, "top": [asdict(r) for r in scored[:max(1, min(top_k, 50))]],
            "improvement_over_baseline": (best.score - baseline["score"]) if best else None,
            "independent_confirmation": confirmation_report, "confirmation_required": confirmation is None,
            "validation_protocol": "Candidates ranked only on validation. Confirmation is evaluated only after selecting the best candidate.",
            "interpretation": "A finite symbolic search result is not evidence of AGI or scientific novelty by itself.",
        }



class FormalismMiner:
    """Enumerate executable equations and compare them on separate train/test cases."""
    def __init__(self, *, max_formulas: int = 400):
        self.max_formulas = max(10, min(int(max_formulas), 5000))

    def mine(self, train: Sequence[dict[str, Any]], validation: Sequence[dict[str, Any]],
             confirmation: Sequence[dict[str, Any]] | None = None, *, target_name: str = "target", top_k: int = 10) -> dict[str, Any]:
        if not train or not validation: raise ValueError("train and validation must be non-empty")
        if confirmation is not None and not confirmation: raise ValueError("confirmation set cannot be empty")
        all_rows=[*train,*validation,*(confirmation or [])]
        if any(target_name not in r for r in all_rows): raise ValueError(f"all rows must contain {target_name}")
        def input_row(r): return {k:v for k,v in r.items() if k != target_name}
        features = _numeric_fields([input_row(r) for r in train])
        atoms = [{"op":"field", "name":f} for f in features]
        formulas = list(atoms)
        for a in atoms: formulas += [{"op":op,"args":[a]} for op in ("abs","square","sqrt_abs","log1p_abs","neg")]
        for a,b in itertools.combinations(atoms,2): formulas += [{"op":op,"args":[a,b]} for op in ("add","sub","mul","div","min","max")]
        scored=[]
        for formula in formulas[:self.max_formulas]:
            try:
                px=[eval_expr(formula,input_row(r)) for r in train]
                pv=[eval_expr(formula,input_row(r)) for r in validation]
                ys=[float(r[target_name]) for r in train]; yv=[float(r[target_name]) for r in validation]
                xm,ym=statistics.mean(px),statistics.mean(ys); var=sum((x-xm)**2 for x in px)
                slope=sum((x-xm)*(y-ym) for x,y in zip(px,ys))/var if var>1e-12 else 0.0
                offset=ym-slope*xm; pred=[slope*x+offset for x in pv]
                scale=max(1e-9,max(ys)-min(ys)); mae=statistics.mean(abs(a-b) for a,b in zip(pred,yv))
                scored.append({"formula":formula,"affine_scale":slope,"affine_offset":offset,"validation_mae":mae,
                               "validation_normalized_score":1-mae/scale,"complexity":expr_complexity(formula),
                               "validation_prediction_hash":_hash(pred)})
            except (ValueError, TypeError, ZeroDivisionError, OverflowError): continue
        scored.sort(key=lambda x:(x["validation_normalized_score"],-x["complexity"]),reverse=True)
        if confirmation is not None and scored:
            item=scored[0]; formula=item["formula"]
            px=[eval_expr(formula,input_row(r)) for r in train]
            ys=[float(r[target_name]) for r in train]; xm,ym=statistics.mean(px),statistics.mean(ys)
            var=sum((x-xm)**2 for x in px); slope=sum((x-xm)*(y-ym) for x,y in zip(px,ys))/var if var>1e-12 else 0.0
            offset=ym-slope*xm
            pred=[slope*eval_expr(formula,input_row(r))+offset for r in confirmation]
            yt=[float(r[target_name]) for r in confirmation]
            item["confirmation_mae"]=statistics.mean(abs(a-b) for a,b in zip(pred,yt))
            item["confirmation_normalized_score"]=1-item["confirmation_mae"]/max(1e-9,max(ys)-min(ys))
            item["confirmation_prediction_hash"]=_hash(pred)
        return {"formula_count":len(scored),"features":features,"top":scored[:max(1,min(top_k,50))],
                "confirmation_required":confirmation is None,"target_name":target_name,
                "selection_protocol":"formulas ranked on validation only; optional confirmation set scored after selection",
                "warning":"Formula search uses a finite grammar. A formula can fit correlations without identifying a causal mechanism."}



class CognitiveMultiverse:
    """Compare diverse bounded minds; reward unique held-out wins as well as score."""
    def evaluate(self, train: Sequence[dict[str, Any]], validation: Sequence[dict[str, Any]],
                 confirmation: Sequence[dict[str, Any]] | None = None, *, task_type: str="auto") -> dict[str, Any]:
        if not train or not validation: raise ValueError("train and validation cannot be empty")
        if confirmation is not None and not confirmation: raise ValueError("confirmation cannot be empty")
        resolved_task=_resolve_task_type(task_type,[r["expected"] for r in train])
        fields=_numeric_fields([r["input"] for r in train])
        if not fields: raise ValueError("no numeric fields")
        minds=[]; val_predictions={}
        for k,metric,transform in itertools.product((1,3,5),("euclidean","manhattan"),("raw","nonlinear","cross")):
            if transform=="raw": reps=[{"op":"field","name":f} for f in fields[:6]]
            elif transform=="nonlinear": reps=[{"op":"log1p_abs","args":[{"op":"field","name":f}]} for f in fields[:6]]
            else:
                reps=[{"op":"sub","args":[{"op":"field","name":a},{"op":"field","name":b}]} for a,b in itertools.combinations(fields[:6],2)] or [{"op":"field","name":fields[0]}]
                reps=reps[:6]
            vf=lambda row,_r=reps:[eval_expr(e,row) for e in _r]
            preds=[]
            for case in validation:
                try: preds.append(_knn_predict(train,vf,case["input"],k=k,metric=metric,task_type=resolved_task))
                except Exception: preds.append(None)
            score=_score_predictions(validation,preds,task_type=resolved_task,reference_targets=[r["expected"] for r in train]); mind_id=f"mind-{k}-{metric}-{transform}"; val_predictions[mind_id]=preds
            minds.append({"id":mind_id,"genome":{"k":k,"metric":metric,"transform":transform},"score":score["score"],
                          "metric":score["metric"],"validation_prediction_hash":_hash(preds)})
        by_case=[]
        for i,c in enumerate(validation):
            correct=[m for m in minds if val_predictions[m["id"]][i]==c["expected"]]
            by_case.append({"case_id":c.get("id",str(i)),"correct_minds":[m["id"] for m in correct]})
        for m in minds:
            unique=sum(1 for c in by_case if m["id"] in c["correct_minds"] and len(c["correct_minds"])==1)
            m["unique_correct_cases"]=unique; m["collective_value"]=round(m["score"]+0.1*unique/max(1,len(validation)),6)
        minds.sort(key=lambda m:(m["collective_value"],m["score"]),reverse=True)
        confirmation_report=None
        if confirmation is not None and minds:
            # Only the winner selected by validation is evaluated on confirmation.
            winner=minds[0]; genome=winner["genome"]; fields_now=fields
            if genome["transform"]=="raw": reps=[{"op":"field","name":f} for f in fields_now[:6]]
            elif genome["transform"]=="nonlinear": reps=[{"op":"log1p_abs","args":[{"op":"field","name":f}]} for f in fields_now[:6]]
            else:
                reps=[{"op":"sub","args":[{"op":"field","name":a},{"op":"field","name":b}]} for a,b in itertools.combinations(fields_now[:6],2)] or [{"op":"field","name":fields_now[0]}]
                reps=reps[:6]
            vf=lambda row:[eval_expr(e,row) for e in reps]
            cp=[_knn_predict(train,vf,c["input"],k=genome["k"],metric=genome["metric"],task_type=resolved_task) for c in confirmation]
            confirm_score=_score_predictions(confirmation,cp,task_type=resolved_task,reference_targets=[r["expected"] for r in train])
            confirmation_report={"selected_by_validation":winner["id"],"score":confirm_score["score"],"metric":confirm_score["metric"],
                                 "prediction_hash":_hash(cp),"population_reselected_on_confirmation":False}
        return {"population_size":len(minds),"task_type":resolved_task,"minds":minds,"per_case_contributions":by_case,"selection_split":"validation",
                "independent_confirmation":confirmation_report,
                "confirmation_evaluated_after_candidate_population_was_fixed":confirmation is not None,
                "selection_rule":"capability + validation cases uniquely solved; diversity is rewarded only when useful",
                "warning":"These are configurations of a fixed k-NN family, not independent general intelligences."}



@dataclass
class OutcomeRecord:
    domain: str
    task_type: str
    complexity: float
    passed: bool
    predicted_confidence: float | None
    model_id: str
    observed_at: str


class EpistemicCartographer:
    """Track competence boundaries by domain/task and conservative Wilson intervals."""
    def __init__(self, max_records: int = 5000): self.max_records=max(100,min(max_records,50000)); self.records: list[OutcomeRecord]=[]

    def record(self, *, domain: str, task_type: str, complexity: float, passed: bool,
               predicted_confidence: float | None=None, model_id: str="default") -> None:
        if not domain.strip() or not task_type.strip(): raise ValueError("domain and task_type required")
        if not 0 <= complexity <= 1: raise ValueError("complexity must be in [0,1]")
        if predicted_confidence is not None and not 0 <= predicted_confidence <= 1: raise ValueError("confidence must be in [0,1]")
        self.records.append(OutcomeRecord(domain,task_type,float(complexity),bool(passed),predicted_confidence,model_id,_now()))
        self.records=self.records[-self.max_records:]

    @staticmethod
    def _wilson(success: int, n: int, z: float=1.96) -> tuple[float,float]:
        if n == 0: return (0.0,1.0)
        p=success/n; den=1+z*z/n
        center=(p+z*z/(2*n))/den
        margin=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
        return max(0,center-margin),min(1,center+margin)

    def report(self) -> dict[str, Any]:
        groups=defaultdict(list)
        for r in self.records: groups[(r.domain,r.task_type)].append(r)
        cells=[]
        for (domain,task),rs in sorted(groups.items()):
            n=len(rs); s=sum(r.passed for r in rs); lo,hi=self._wilson(s,n)
            conf=[r for r in rs if r.predicted_confidence is not None]
            brier=statistics.mean((r.predicted_confidence-float(r.passed))**2 for r in conf) if conf else None
            cells.append({"domain":domain,"task_type":task,"n":n,"success_rate":s/n,"wilson_95":[lo,hi],
                          "mean_complexity":statistics.mean(r.complexity for r in rs),"brier_score":brier,
                          "status":"weak_evidence" if n<20 else ("reliable_region_candidate" if lo>=.8 else "boundary_or_failure_region")})
        cells.sort(key=lambda c:(c["wilson_95"][0],c["n"]))
        return {"records":len(self.records),"regions":cells,
                "limitations":"Wilson intervals cover observed binomial outcomes only; groups may be biased or non-independent.",
                "boundary_regions":[c for c in cells if c["status"]!="reliable_region_candidate"]}

    def assess(self, *, domain: str, task_type: str) -> dict[str, Any]:
        relevant=[r for r in self.records if r.domain==domain and r.task_type==task_type]
        if not relevant: return {"domain":domain,"task_type":task_type,"status":"unknown","conservative_success_lower_bound":0.0,"sample_count":0}
        lo,hi=self._wilson(sum(r.passed for r in relevant),len(relevant))
        return {"domain":domain,"task_type":task_type,"status":"known_reliable" if len(relevant)>=20 and lo>=.8 else "uncertain_or_weak",
                "conservative_success_lower_bound":lo,"interval_upper_bound":hi,"sample_count":len(relevant)}


class ExperimentalOntologyDiscovery:
    """Propose new *simulation-only* interventions from observed numeric schemas."""
    def propose(self, rows: Sequence[dict[str, Any]], *, max_operators: int=40) -> list[dict[str, Any]]:
        if not rows: raise ValueError("rows cannot be empty")
        if not 1 <= max_operators <= 200: raise ValueError("max_operators must be in [1,200]")
        fields=_numeric_fields(rows); out=[]
        for f in fields:
            values=[float(r[f]) for r in rows]
            median=statistics.median(values)
            deltas=sorted({round(median-v,6) for v in values})
            candidates=[{"kind":"set_to_median","field":f,"value":median},
                       {"kind":"shift_by","field":f,"delta":statistics.pstdev(values) or 1.0},
                       {"kind":"scale_by","field":f,"factor":2.0}]
            for c in candidates:
                out.append({"id":str(uuid4()),"operator":c,"status":"proposal_only","execution_scope":"synthetic_simulation_only",
                            "hypothesis":"This intervention changes the target in a repeatable way; not yet tested.",
                            "must_check":["leakage","confounding","domain validity","held-out replication"]})
                if len(out)>=max_operators: return out
        return out

    def apply_to_copy(self, row: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        """Apply a declarative operator to a copied dictionary; never changes caller data."""
        kind,field=operator.get("kind"),operator.get("field")
        if field not in row: raise ValueError("operator field is absent")
        result=dict(row); current=_num(result[field])
        if kind=="set_to_median": result[field]=_num(operator.get("value"))
        elif kind=="shift_by": result[field]=current+_num(operator.get("delta"))
        elif kind=="scale_by": result[field]=current*_num(operator.get("factor"))
        else: raise ValueError("unsupported intervention operator")
        return result


class OpenEndedEvaluator:
    """Propose challenge dimensions from failure patterns; never self-approves metrics."""
    def propose_dimensions(self, failures: Sequence[dict[str, Any]], *, max_dimensions: int=8) -> list[dict[str, Any]]:
        if not 1 <= max_dimensions <= 30: raise ValueError("max_dimensions must be in [1,30]")
        mapping={
            "missing_fields":("Robustness to incomplete observations","Test controlled missingness without changing labels."),
            "distribution_shift":("Transfer under distribution shift","Evaluate on a source-separated or time-separated holdout."),
            "ambiguous_goal":("Clarification before action","Check if system asks a targeted question when success criteria conflict."),
            "long_horizon":("Long-horizon recovery","Test goal persistence after injected recoverable failures."),
            "cross_domain":("Cross-domain transfer","Train in one domain and test a distinct domain without retuning."),
            "no_confirmed_gain":("Replication of candidate improvement","Repeat the pre-registered comparison on a new independent dataset with a baseline; do not tune on that set."),
            "verification":("Independent result verification","Compare agent claim with independently recomputed output."),
        }
        seen=set(); out=[]
        for f in failures:
            key=str(f.get("failure_type",""))
            if key in mapping and key not in seen:
                title,protocol=mapping[key]; seen.add(key)
                out.append({"id":str(uuid4()),"dimension":title,"failure_count":int(f.get("count",1)),
                            "candidate_protocol":protocol,"status":"proposed_not_validated",
                            "acceptance_requires":"pre-registration + independent holdout + baseline comparison"})
            if len(out)>=max_dimensions: break
        return out


@dataclass
class ResearchRun:
    id: str
    started_at: str
    finished_at: str
    representation_report: dict[str, Any]
    multiverse_report: dict[str, Any]
    formalism_report: dict[str, Any]
    open_ended_dimensions: list[dict[str, Any]]
    outcome: str
    reproducibility_hash: str


class ClosedLoopResearchEngine:
    """One bounded, reproducible solve→critique→propose→test cycle."""
    def __init__(self, *, max_candidates: int=160):
        self.representations=RepresentationInventor(max_candidates=max_candidates)
        self.multiverse=CognitiveMultiverse(); self.formalisms=FormalismMiner(); self.evaluator=OpenEndedEvaluator()

    def run(self, *, train: Sequence[dict[str, Any]], validation: Sequence[dict[str, Any]],
            test: Sequence[dict[str, Any]], domain: str, target_name: str="target", task_type: str="auto") -> dict[str, Any]:
        """Search on validation; use the confirmation set only after selection."""
        if not train or not validation or not test: raise ValueError("train, validation and test splits are all required")
        # Reject exact-record or stable-ID overlap across splits to catch common leakage.
        split_data={"train":train,"validation":validation,"test":test}
        signatures={}
        ids={}
        for split_name,rows in split_data.items():
            signatures[split_name]={_hash({"input":row.get("input")}) for row in rows}  # input only: relabeled or re-ID'd copies are still leakage
            ids[split_name]={str(row.get("id")) for row in rows if row.get("id") is not None and str(row.get("id")).strip()}
        names=list(split_data)
        for i,left in enumerate(names):
            for right in names[i+1:]:
                if signatures[left].intersection(signatures[right]) or ids[left].intersection(ids[right]):
                    raise ValueError(f"split leakage detected between {left} and {right}; remove overlap before evaluation")
        started=_now()
        representation=self.representations.search(train,validation,confirmation=test,task_type=task_type)
        multiverse=self.multiverse.evaluate(train,validation,confirmation=test,task_type=task_type)
        flat_train=[{**c["input"],target_name:c["expected"]} for c in train]
        flat_val=[{**c["input"],target_name:c["expected"]} for c in validation]
        flat_test=[{**c["input"],target_name:c["expected"]} for c in test]
        if representation["task_type"] == "regression":
            formalism=self.formalisms.mine(flat_train,flat_val,confirmation=flat_test,target_name=target_name)
        else:
            formalism={"skipped": True, "reason": "The current symbolic formula miner only scores continuous numeric targets; classification labels must not be treated as numeric magnitudes."}
        confirm=representation.get("independent_confirmation")
        confirm_gain=confirm.get("improvement_over_baseline") if confirm else None
        failures=[]
        if confirm_gain is None or confirm_gain<=.01: failures.append({"failure_type":"no_confirmed_gain","count":1})
        proposed=self.evaluator.propose_dimensions(failures)
        finished=_now()
        payload={"started_at":started,"finished_at":finished,"domain":domain,"representation_report":representation,
                 "multiverse_report":multiverse,"formalism_report":formalism,"open_ended_dimensions":proposed,
                 "split_counts":{"train":len(train),"validation":len(validation),"confirmation":len(test)},"task_type":representation["task_type"]}
        payload["id"]=str(uuid4()); payload["outcome"]="confirmation_gain_observed" if confirm_gain is not None and confirm_gain>.01 else "no_confirmed_improvement"
        payload["limitations"]=["finite DSL and finite candidate population","confirmation set must not be reused for tuning; use a new holdout after changes",
                                "not proof of causal discovery, scientific novelty, general intelligence, or AGI"]
        # Stable fingerprint of the input data and protocol, separate from the
        # timestamped report digest. It lets reruns verify they used the same inputs.
        payload["reproducibility_hash"]=_hash({"protocol_version":"claire-research-v1","domain":domain,
            "target_name":target_name,"task_type":representation["task_type"],"max_candidates":self.representations.max_candidates,
            "train":train,"validation":validation,"confirmation":test})
        payload["report_content_hash"]=_hash(payload)  # digest excludes this field itself
        return payload



def generate_concept_lattice(*, domains: Sequence[str], bottlenecks: Sequence[str], methods: Sequence[str],
                             constraints: Sequence[str]=( "low compute", "public data", "reproducible" ),
                             limit: int=1000) -> list[dict[str, Any]]:
    """Generate a bounded, deduplicated concept backlog; ideas are not evidence of novelty."""
    if not 1 <= limit <= 5000: raise ValueError("limit must be in [1,5000]")
    for name,seq in (("domains",domains),("bottlenecks",bottlenecks),("methods",methods),("constraints",constraints)):
        if not seq or any(not str(s).strip() for s in seq): raise ValueError(f"{name} must contain non-empty strings")
    out=[]; seen=set()
    for domain,bottleneck,method,constraint in itertools.product(domains,bottlenecks,methods,constraints):
        title=f"{method.strip()} for {bottleneck.strip()} in {domain.strip()}"
        question=f"Can {method.strip()} improve {bottleneck.strip()} for {domain.strip()} under {constraint.strip()}?"
        key=_hash([title,question])
        if key in seen: continue
        seen.add(key)
        out.append({"id":str(uuid4()),"title":title,"research_question":question,"domain":domain,
                    "bottleneck":bottleneck,"method_family":method,"constraint":constraint,
                    "status":"unreviewed_idea","evidence":[],"prior_art_review":"required","test_plan_required":True})
        if len(out)>=limit: break
    return out
