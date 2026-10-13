from __future__ import annotations
from copy import deepcopy
from typing import Any
import hashlib, json, re
from ._canon import canonical_json

class SkillRejected(ValueError): pass

_ALLOWED = {"copy", "normalize_text", "contains_any", "weighted_score", "threshold_label", "map_value", "concat", "set_constant"}

class SkillEcology:
    """A small compositional skill language; no eval, imports, shell, or arbitrary Python.

    A skill earns the label `validated_on_holdout` when every authored unit test passes
    and a caller-supplied held-out set whose inputs are disjoint from the authored tests
    reaches minimum_accuracy (default 0.9, so not every held-out case need pass). Disjointness is enforced; that the held-out set was truly kept away from the
    skill's author is NOT verified. This is local benchmark evidence, not proof of
    competence.
    """
    def __init__(self): self.registry: dict[str, dict[str, Any]] = {}; self.quarantine: list[dict[str, Any]] = []

    def validate_spec(self, spec: dict[str, Any]) -> None:
        if not isinstance(spec,dict): raise SkillRejected("skill must be an object")
        for key in ("skill_id","name","version","operations","tests"):
            if key not in spec: raise SkillRejected(f"missing {key}")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{3,100}", str(spec["skill_id"])): raise SkillRejected("invalid skill_id")
        if not isinstance(spec["operations"],list) or not 1<=len(spec["operations"])<=40: raise SkillRejected("operations must contain 1..40 items")
        if not isinstance(spec["tests"],list) or not 1<=len(spec["tests"])<=100: raise SkillRejected("tests must contain 1..100 items")
        for i,case in enumerate(spec["tests"]):
            if not isinstance(case,dict) or not isinstance(case.get("input"),dict) or not isinstance(case.get("expected"),dict) or not case["expected"]:
                raise SkillRejected(f"test {i} must include object input and non-empty expected output")
        for op in spec["operations"]:
            if op.get("op") not in _ALLOWED: raise SkillRejected(f"operation not allow-listed: {op.get('op')}")
            required={"copy":["source","target"],"normalize_text":["source","target"],"contains_any":["source","target","tokens"],
                "weighted_score":["target","weights"],"threshold_label":["source","target","threshold"],"map_value":["source","target","mapping"],
                "concat":["sources","target"],"set_constant":["field","value"]}[op["op"]]
            if any(k not in op for k in required): raise SkillRejected(f"{op['op']} missing required fields: {[k for k in required if k not in op]}")
            for name in ("source","target","field"):
                if name in op and (not isinstance(op[name],str) or not op[name].strip() or len(op[name])>100):
                    raise SkillRejected(f"{op['op']} field {name} must be a short non-empty string")
            if op["op"]=="contains_any" and (not isinstance(op["tokens"],list) or not op["tokens"]):
                raise SkillRejected("contains_any tokens must be a non-empty list")
            if op["op"]=="weighted_score" and (not isinstance(op["weights"],dict) or not op["weights"]):
                raise SkillRejected("weighted_score weights must be a non-empty object")
        # Reject incidental code-like fields to keep the DSL declarative and auditable.
        forbidden={"python","code","shell","command","module","import","eval"}
        if any(any(k.casefold() in forbidden for k in row) for row in spec["operations"]):
            raise SkillRejected("arbitrary code fields are forbidden")

    def run(self, spec: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        self.validate_spec({**spec,"tests":spec.get("tests") or [{"input":{},"expected":{}}]})
        out=deepcopy(record)
        for op in spec["operations"]:
            kind=op["op"]; target=op.get("target")
            if kind=="set_constant": out[op["field"]]=op.get("value")
            elif kind=="copy":
                if op["source"] not in out: raise SkillRejected(f"precondition failed: field {op['source']} absent")
                out[target]=deepcopy(out[op["source"]])
            elif kind=="normalize_text":
                value=out.get(op["source"])
                if not isinstance(value,str): raise SkillRejected("normalize_text source must be string")
                value=value.strip()
                if op.get("lowercase",True): value=value.casefold()
                if op.get("collapse_spaces",True): value=" ".join(value.split())
                out[target]=value
            elif kind=="contains_any":
                value=out.get(op["source"],"")
                if not isinstance(value,str): value=str(value)
                tokens=op.get("tokens",[])
                if not isinstance(tokens,list) or len(tokens)>100: raise SkillRejected("tokens must be a bounded list")
                out[target]=any(str(t).casefold() in value.casefold() for t in tokens)
            elif kind=="weighted_score":
                weights=op.get("weights",{})
                if not isinstance(weights,dict) or len(weights)>100: raise SkillRejected("weights must be a bounded map")
                score=0.0
                for field,weight in weights.items():
                    value=out.get(field,0)
                    if not isinstance(value,(int,float)) or not isinstance(weight,(int,float)): raise SkillRejected("weighted_score accepts numeric fields and weights only")
                    score+=float(value)*float(weight)
                out[target]=round(score,8)
            elif kind=="threshold_label":
                value=out.get(op["source"])
                if not isinstance(value,(int,float)): raise SkillRejected("threshold source must be numeric")
                out[target]=op.get("above") if value>=float(op["threshold"]) else op.get("below")
            elif kind=="map_value":
                mapping=op.get("mapping",{})
                if not isinstance(mapping,dict) or len(mapping)>500: raise SkillRejected("mapping must be bounded")
                out[target]=mapping.get(str(out.get(op["source"])),op.get("default"))
            elif kind=="concat":
                fields=op.get("sources",[])
                if not isinstance(fields,list) or len(fields)>20: raise SkillRejected("concat sources must be bounded")
                out[target]=str(op.get("separator"," ")).join(str(out.get(f,"")) for f in fields)
        return out

    def test(self, spec: dict[str, Any], examples: list[dict[str, Any]] | None=None) -> dict[str, Any]:
        self.validate_spec(spec)
        cases=examples if examples is not None else spec["tests"]
        if not cases or len(cases)>500: raise SkillRejected("test set must contain 1..500 examples")
        if any(not isinstance(case,dict) or not isinstance(case.get("input"),dict) or not isinstance(case.get("expected"),dict) or not case["expected"] for case in cases):
            raise SkillRejected("every evaluated case needs object input and non-empty expected output")
        failures=[]
        for i,case in enumerate(cases):
            try: actual=self.run({**spec,"tests":spec["tests"]},case["input"])
            except Exception as exc:
                failures.append({"index":i,"error":type(exc).__name__}); continue
            expected=case.get("expected",{})
            mismatch={k:{"expected":v,"actual":actual.get(k,"__MISSING__")} for k,v in expected.items() if actual.get(k,"__MISSING__")!=v}
            if mismatch: failures.append({"index":i,"mismatch":mismatch})
        return {"passed":not failures,"n":len(cases),"failures":failures[:30],"accuracy":(len(cases)-len(failures))/len(cases)}

    def register(self, spec: dict[str, Any], held_out: list[dict[str, Any]], *, minimum_accuracy: float=0.9) -> dict[str, Any]:
        self.validate_spec(spec)
        if not 0.5<=minimum_accuracy<=1: raise ValueError("minimum_accuracy must be 0.5..1")
        authored_inputs={canonical_json(c["input"]) for c in spec["tests"]}
        if any(isinstance(c,dict) and canonical_json(c.get("input")) in authored_inputs for c in (held_out or [])):
            self.quarantine.append({"skill_id":spec["skill_id"],"reason":"holdout_reuses_authored_test_inputs"})
            raise SkillRejected("held-out set must not reuse any authored test input")
        authored=self.test(spec)
        confirmation=self.test(spec,held_out)
        if not authored["passed"] or confirmation["accuracy"]<minimum_accuracy:
            self.quarantine.append({"skill_id":spec["skill_id"],"reason":"validation_gate_failed","unit_tests":authored,"held_out":confirmation})
            raise SkillRejected("skill failed unit-test or untouched holdout gate")
        digest=hashlib.sha256(canonical_json(spec).encode()).hexdigest()
        stored={**deepcopy(spec),"sha256":digest,"status":"validated_on_holdout","unit_tests":authored,
                "held_out":confirmation,"holdout_provenance":"input-disjoint from authored tests; independence from the author is caller-attested, not verified","limitations":["Holdout size and representativeness matter.","This does not prove general capability outside tested inputs."]}
        self.registry[spec["skill_id"]]=stored
        return deepcopy(stored)

    def compose(self, skill_ids: list[str], *, skill_id: str, name: str, version: str="1.0",
                tests: list[dict[str,Any]] | None=None) -> dict[str, Any]:
        if not 2<=len(skill_ids)<=5: raise SkillRejected("compose between 2 and 5 skills")
        missing=[i for i in skill_ids if i not in self.registry or self.registry[i].get("status")!="validated_on_holdout"]
        if missing: raise SkillRejected(f"unvalidated or quarantined skills cannot be composed: {missing}")
        operations=[]
        for sid in skill_ids: operations.extend(deepcopy(self.registry[sid]["operations"]))
        if len(operations)>40: raise SkillRejected("composed skill exceeds 40-operation limit")
        composed={"skill_id":skill_id,"name":name,"version":version,"operations":operations,
                  "tests":deepcopy(tests or []),"composed_from":skill_ids}
        if tests:
            self.validate_spec(composed)
            composed["status"]="composition_candidate_requires_held_out_evaluation"
        else:
            # No output contract was supplied; this is only a proposal, never a verified skill.
            composed["status"]="unvalidated_composition_proposal"
        return composed

    def regression_check(self, skill_id: str, old_spec: dict[str,Any], new_spec: dict[str,Any], regression_cases: list[dict[str,Any]]) -> dict[str,Any]:
        old=self.test(old_spec,regression_cases); new=self.test(new_spec,regression_cases)
        regression=new["accuracy"] < old["accuracy"]
        result={"skill_id":skill_id,"old_accuracy":old["accuracy"],"new_accuracy":new["accuracy"],"regression":regression}
        if regression:
            self.quarantine.append({**result,"reason":"regression_detected"})
            if skill_id in self.registry: self.registry[skill_id]["status"]="quarantined"
        return result
