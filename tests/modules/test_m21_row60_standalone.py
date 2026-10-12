"""Row 60: m21_claire owner_interview.py and training.py. Standalone: both modules are loaded by path because the
m21_claire package import chain needs Python 3.11 (StrEnum). training.py gets a stub ApprovalRequest; owner_interview
uses an in-memory SQLite database. Offline."""
import importlib.util, pathlib, sys, types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_D = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m21_claire"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, _D / fname)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _AR:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_stub = types.ModuleType("app.core.models")
_stub.ApprovalRequest = _AR
_saved = {k: sys.modules.get(k) for k in ("app.core.models",)}
sys.modules["app.core.models"] = _stub
oi = _load("m21_owner_interview_standalone_mod", "owner_interview.py")
tr = _load("m21_training_standalone_mod", "training.py")
for k, v in _saved.items():
    if v is None:
        sys.modules.pop(k, None)
    else:
        sys.modules[k] = v

InterviewStore, QUESTIONS = oi.InterviewStore, oi.QUESTIONS


def store(t="t1", a="a1", eng=None):
    eng = eng or create_engine("sqlite://")
    return InterviewStore(t, a, sessionmaker(bind=eng)), eng


def ans(s, i=0, **kw):
    q = QUESTIONS[i]
    args = dict(question_id=q["id"], choice=q["choices"][0], reason="because", source_reference="owner chat")
    args.update(kw)
    return s.answer(**args)


# ---- owner_interview
def test_blank_tenant_or_actor_rejected():
    for t, a in (("", "a"), ("  ", "a"), ("t", ""), ("t", " ")):
        with pytest.raises(ValueError):
            store(t, a)


def test_consent_gates_questions_context_and_answers():
    s, _ = store()
    assert s.next_question() == {"status": "consent_required", "question": None}
    assert s.context() == {"status": "consent_required", "preferences": []}
    with pytest.raises(PermissionError):
        ans(s)
    assert s.consent(True)["enabled"] is True
    assert s.next_question()["status"] == "question"
    s.consent(False)
    assert s.next_question()["status"] == "consent_required"
    s.consent(True)  # update path of an existing row
    assert s.next_question()["status"] == "question"


def test_questions_progress_in_order_then_complete():
    s, _ = store()
    s.consent(True)
    for i, q in enumerate(QUESTIONS):
        n = s.next_question()
        assert n["question"]["id"] == q["id"] and n["answered"] == i and n["total"] == len(QUESTIONS)
        ans(s, i)
    assert s.next_question()["status"] == "complete" and s.next_question()["question"] is None


def test_answer_validation_and_claim_label():
    s, _ = store()
    s.consent(True)
    for kw in ({"question_id": "nope"}, {"choice": "not_a_choice"}, {"reason": "  "}, {"reason": "x" * 2001},
               {"source_reference": " "}, {"source_reference": "x" * 241}):
        with pytest.raises(ValueError):
            ans(s, **kw)
    r = ans(s, reason="  padded  ", source_reference=" src ")
    assert r["reason"] == "padded" and r["source_reference"] == "src"
    assert r["claim"] == "owner_reported_preference_not_action_permission"
    assert ans(s, 1, reason="x" * 2000, source_reference="y" * 240)["question_id"] == QUESTIONS[1]["id"]


def test_duplicate_answer_needs_revoke_first():
    s, _ = store()
    s.consent(True)
    r = ans(s)
    with pytest.raises(ValueError):
        ans(s)
    assert s.revoke(r["id"]) is True
    assert s.revoke(r["id"]) is False
    assert ans(s)["id"] != r["id"]
    assert s.next_question()["answered"] == 1


def test_revoke_is_scoped_to_tenant_and_actor_and_unknown_ids():
    s, eng = store("t1", "a1")
    s.consent(True)
    r = ans(s)
    assert store("t2", "a1", eng)[0].revoke(r["id"]) is False
    assert store("t1", "a2", eng)[0].revoke(r["id"]) is False
    assert s.revoke(99999) is False
    assert s.revoke(r["id"]) is True


def test_context_lists_active_answers_with_domain_and_no_action_permission():
    s, _ = store()
    s.consent(True)
    a0, a1 = ans(s, 0), ans(s, 1)
    s.revoke(a0["id"])
    c = s.context()
    assert c["status"] == "owner_reported_preferences" and c["external_action_permission"] is False
    assert [p["question_id"] for p in c["preferences"]] == [QUESTIONS[1]["id"]]
    p = c["preferences"][0]
    assert p["domain"] == QUESTIONS[1]["domain"] and p["evidence_id"] == a1["id"]
    assert p["reason"] == "because" and p["source_reference"] == "owner chat"


def test_answers_isolated_by_tenant_and_actor():
    s, eng = store("t1", "a1")
    o, _ = store("t1", "a2", eng)
    s.consent(True)
    o.consent(True)
    ans(s)
    assert o.next_question()["answered"] == 0 and o.context()["preferences"] == []
    ans(o)  # same question for another actor is allowed


def test_delete_all_removes_revoked_and_active_only_for_this_owner():
    s, eng = store("t1", "a1")
    o, _ = store("t1", "a2", eng)
    s.consent(True)
    o.consent(True)
    r = ans(s)
    s.revoke(r["id"])
    ans(s)
    ans(s, 1)
    ans(o)
    assert s.delete_all() == 3
    assert s.context()["preferences"] == [] and len(o.context()["preferences"]) == 1
    assert s.delete_all() == 0


def test_question_bank_is_fixed_and_well_formed():
    assert [q["id"] for q in QUESTIONS] == ["evidence", "reach_out", "opportunity", "uncertainty", "workflow"]
    assert oi.BY_ID.keys() == {q["id"] for q in QUESTIONS}
    assert all(len(q["choices"]) == 3 for q in QUESTIONS)


# ---- training
class Approvals:
    def __init__(self):
        self.put_calls = []

    def put(self, req):
        self.put_calls.append(req)
        return req


def test_voice_dataset_bounds_strip_and_hash():
    t = tr.TrainingService(Approvals())
    with pytest.raises(ValueError):
        t.voice_dataset(["x"] * 49)
    with pytest.raises(ValueError):
        t.voice_dataset(["x"] * 49 + ["   "])  # blank samples are dropped before counting
    with pytest.raises(ValueError):
        t.voice_dataset(["x"] * 2001)
    d = t.voice_dataset([" a%d " % i for i in range(50)])
    assert d.kind == "voice_lora" and len(d.examples) == 50 and d.examples[0] == {"text": "a0", "provenance": "owner_authored"}
    assert len(d.sha256) == 64 and d.sha256 == t.voice_dataset(["a%d" % i for i in range(50)]).sha256
    assert d.sha256 != t.voice_dataset(["b%d" % i for i in range(50)]).sha256
    assert len(t.voice_dataset(["x"] * 2000).examples) == 2000


def _rank(i, **kw):
    r = {"context": "c%d" % i, "options": ["a", "b", "c"], "ranking": ["c", "a", "b"]}
    r.update(kw)
    return r


def test_preference_dataset_validation_and_provenance():
    t = tr.TrainingService(Approvals())
    ok = [_rank(i) for i in range(20)]
    d = t.preference_dataset(ok)
    assert d.kind == "preference" and len(d.examples) == 20 and d.examples[0]["provenance"] == "owner_ranked"
    assert d.examples[0]["ranking"] == ["c", "a", "b"] and d.examples[0]["context"] == "c0"
    with pytest.raises(ValueError):
        t.preference_dataset(ok[:19])
    for bad in (_rank(0, options=["a"], ranking=["a"]), _rank(0, ranking=["a", "b"]),
                _rank(0, ranking=["a", "b", "z"]), _rank(0, options=[], ranking=[])):
        with pytest.raises(ValueError):
            t.preference_dataset([bad] + ok)
    assert t.preference_dataset([_rank(i) for i in range(20)]).sha256 == d.sha256


def test_propose_training_is_pending_approval_only():
    ap = Approvals()
    t = tr.TrainingService(ap)
    d = t.voice_dataset(["s%d" % i for i in range(50)])
    out = t.propose_training(d, "base-m", "lora")
    p = out["payload"]
    assert out["status"] == "pending" and out["approval_id"] == ap.put_calls[0].id
    assert ap.put_calls[0].module_id == 21 and ap.put_calls[0].action_type == "train_personalization_model"
    assert p["dataset_kind"] == "voice_lora" and p["dataset_sha256"] == d.sha256 and p["example_count"] == 50
    assert p["base_model"] == "base-m" and p["method"] == "lora"
    assert p["publishing"] is False and p["estimated_cost_requires_review"] is True
    assert p["execution_environment"] == "paired_local_pc_or_reviewed_gpu_worker"
    with pytest.raises(ValueError):
        t.propose_training(d, "base-m", "full")
    assert len(ap.put_calls) == 1
    pref = t.preference_dataset([_rank(i) for i in range(20)])
    assert t.propose_training(pref, "m", "dpo")["payload"]["method"] == "dpo"


def test_dataset_hash_covers_every_example():
    t = tr.TrainingService(Approvals())
    base = ["s%d" % i for i in range(50)]
    assert t.voice_dataset(base).sha256 != t.voice_dataset(base[:-1] + ["different"]).sha256
    r1 = [_rank(i) for i in range(20)]
    r2 = [_rank(i) for i in range(19)] + [_rank(19, ranking=["a", "b", "c"])]
    assert t.preference_dataset(r1).sha256 != t.preference_dataset(r2).sha256
