"""AUTHORED, NOT RUN. M14 attempted-wave continuation policy (ATLAS-1 prep).

Contract under test: docs/M14_DAG_CONTINUATION_PREP.md at base 7d6098ff. Additive only: uses
existing APIs, no product edits. Static tests read git-tracked text and import no product code.
Real tests follow the existing test_m14_sandbox_wave.py conventions (sqlite engine, ORM Session
via the sessionmaker, fresh SandboxWaveService = "second process") and skip when real Bubblewrap
namespace capability is unavailable.
"""
import asyncio
import re
import shutil
import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import ApprovalEffectRow
from app.modules.m14_project_builder import sandbox_wave as sw
from app.modules.m14_project_builder.schemas import Budget, ProjectPlan, ProjectTask
from app.modules.m14_project_builder.sql_repository import ProjectRow

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m14_project_builder/sandbox_wave.py"
DOC = ROOT / "docs/M14_DAG_CONTINUATION_PREP.md"
TENANT, ACTOR, PROJECT = "t", "owner", "p"


class Interrupt(BaseException):
    """Simulated process death: not an Exception, so _task's except Exception cannot absorb it."""


# --------------------------------------------------------------------------
# static drift detectors (no sandbox, no product import)
# --------------------------------------------------------------------------

def test_static_contract_literals_present_in_source():
    src = SRC.read_text()
    for literal in (
        "project already attempted this wave unit",
        "wave cannot be claimed",
        "operation state changed; do not replay",
        "claim_key:Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)",
        "unknown_after_claim",
        "'all_dag_completed':False",
        "'independent_quality_verified':False",
    ):
        assert literal in src, literal


def test_static_no_resume_retry_or_recovery_entry_point():
    src = SRC.read_text()
    assert not re.search(r"def\s+\w*(resume|retry|continue|reclaim|recover|abandon|supersede)\w*", src, re.I)


def test_static_claim_key_only_written_by_claim_transaction():
    allowed = (
        re.compile(r"claim_key:Mapped\["),
        re.compile(r"^\s*claim_key=digest\(\{'tenant':tenant,'project':row\.project_id\}\)\s*$"),
        re.compile(r"SandboxWaveRow\.claim_key==claim_key"),
        re.compile(r"\.values\(state='claimed',claim_key=claim_key\)"),
    )
    for line in SRC.read_text().splitlines():
        if "claim_key" in line:
            assert any(p.search(line) for p in allowed), f"unexpected claim_key use: {line.strip()}"


def test_static_finalize_is_single_transaction_writing_rows_result_and_state_together():
    src = SRC.read_text()
    block = src[src.index("outcomes=await asyncio.gather"):src.index("def _task")]
    assert block.count("self.sessions.begin()") == 1
    assert "SandboxWaveTaskRow(" in block and "SandboxWaveArtifactRow(" in block
    assert "row.result=result;row.state='awaiting_review'" in block


def test_static_doc_names_required_clauses():
    text = DOC.read_text()
    for needle in (
        "Second-process contract",
        "Explicitly NOT resumed, retried, or inferred",
        "Unresolved semantics",
        "AUTHORED-NOT-RUN",
        "unknown_after_claim=True",
        "no continuation",
    ):
        assert needle.lower() in text.lower(), needle


def test_static_doc_stage_table_has_every_named_boundary():
    text = DOC.read_text()
    for stage in ("S0", "S1", "S2a", "S2b", "S3", "S4", "S5", "S6"):
        assert re.search(rf"^\| {stage} \|", text, re.M), stage


# --------------------------------------------------------------------------
# real-execution fixtures (existing convention; ORM Session, never a bare Connection select)
# --------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path):
    root = Path(tempfile.mkdtemp(prefix="atlas-wave-test-", dir=Path.home()))
    root.chmod(0o700)
    engine = create_engine("sqlite:///" + str(tmp_path / "wave.db"), connect_args={"check_same_thread": False})
    sessions = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    svc = sw.SandboxWaveService(sessions, str(root))
    try:
        svc._probe()
    except sw.WaveUnavailable:
        pytest.skip("real Bubblewrap namespace capability unavailable")
    # a1 and a2 are independent (ready); c depends on a1 (never ready at this base).
    plan = ProjectPlan(goal="demo", tasks=[
        ProjectTask(id="a1", title="write one", objective="write result one", agent_kind="coder"),
        ProjectTask(id="a2", title="write two", objective="write result two", agent_kind="coder"),
        ProjectTask(id="c", title="dependent", objective="dependent task", agent_kind="coder", dependencies=["a1"]),
    ])
    with sessions.begin() as db:
        db.add(ProjectRow(tenant_id=TENANT, id=PROJECT, goal="demo", brief={},
                          budget=Budget().model_dump(mode="json"), status="planned", revision=1,
                          plan=plan.model_dump(mode="json")))
    yield svc, sessions, root
    engine.dispose()
    shutil.rmtree(root)


def request():
    ok = "open('/output/result.txt','w').write('x')"
    return sw.WaveDraft(
        tasks={"a1": sw.TaskCode(code=ok), "a2": sw.TaskCode(code=ok),
               "c": sw.TaskCode(code="raise Exception('dependent must not run')")},
        max_parallel=2, timeout_seconds=5)


def approved(svc):
    d = svc.draft(TENANT, ACTOR, PROJECT, request())
    s = svc.submit(TENANT, ACTOR, d["id"])
    svc.gate.decide(s["approval_id"], ApprovalStatus.APPROVED, decided_by="owner")
    return d["id"], s["approval_id"]


def facts(sessions, wid):
    with sessions() as db:
        row = db.get(sw.SandboxWaveRow, wid)
        return {
            "state": row.state,
            "key": row.claim_key,
            "result": row.result,
            "effects": db.scalar(select(func.count()).select_from(ApprovalEffectRow)),
            "tasks": db.scalar(select(func.count()).select_from(sw.SandboxWaveTaskRow)),
            "artifacts": db.scalar(select(func.count()).select_from(sw.SandboxWaveArtifactRow)),
        }


def project_plan(sessions):
    with sessions() as db:
        return db.scalar(select(ProjectRow).where(ProjectRow.id == PROJECT)).plan


def must_conflict(fn, label):
    """Raise AssertionError (not pytest.fail) so mutation tests can catch a violated policy."""
    try:
        fn()
    except sw.WaveConflict:
        return
    except Exception as exc:  # any other outcome also violates the contract
        raise AssertionError(f"policy violated ({label}): expected WaveConflict, got {type(exc).__name__}") from exc
    raise AssertionError(f"policy violated ({label}): expected WaveConflict, call succeeded")


def assert_second_process_policy(sessions, root, wid, plan_before, expected_key):
    """The documented contract for a later process that finds a permanent attempted-wave key."""
    fresh = sw.SandboxWaveService(sessions, str(root))
    dispatched = []
    fresh._task = lambda *a, **k: dispatched.append(a) or (_ for _ in ()).throw(AssertionError("re-dispatch"))
    view = fresh.get(TENANT, ACTOR, wid)
    if view["state"] != "claimed":
        raise AssertionError("policy violated (partial state read as complete): state=" + view["state"])
    if view["unknown_after_claim"] is not True or view["result"] is not None:
        raise AssertionError("policy violated: claimed wave must read unknown with no result")
    must_conflict(lambda: fresh.claim(TENANT, ACTOR, wid), "claim on claimed wave")
    must_conflict(lambda: asyncio.run(fresh.execute(TENANT, ACTOR, wid)), "execute on claimed wave")
    if dispatched:
        raise AssertionError("policy violated: second process dispatched a task")
    if fresh.artifacts(TENANT, ACTOR, wid) != []:
        raise AssertionError("policy violated: artifacts listed for an unfinished wave")
    before = facts(sessions, wid)
    wid2, aid2 = approved(fresh)
    must_conflict(lambda: fresh.claim(TENANT, ACTOR, wid2), "fresh draft for attempted project")
    after2 = facts(sessions, wid2)
    if after2["state"] != "awaiting_approval" or after2["key"] is not None:
        raise AssertionError("policy violated: second draft changed state or key")
    with sessions() as db:
        if db.scalar(select(func.count()).select_from(ApprovalEffectRow)) != before["effects"]:
            raise AssertionError("policy violated: second approval was consumed")
    after = facts(sessions, wid)
    if after != before or after["key"] != expected_key:
        raise AssertionError("policy violated: durable state of the attempted wave changed")
    if project_plan(sessions) != plan_before:
        raise AssertionError("policy violated: plan mutated (dependent or ready task progressed)")


def expected_key():
    return sw.digest({"tenant": TENANT, "project": PROJECT})


# --------------------------------------------------------------------------
# interruption at each named stage boundary
# --------------------------------------------------------------------------

def interrupt_pre_commit_probe(svc, sessions, wid, mp):
    def unavailable():
        raise sw.WaveUnavailable("namespace denied")
    mp.setattr(svc, "_probe", unavailable)
    with pytest.raises(sw.WaveUnavailable):
        svc.claim(TENANT, ACTOR, wid)


def interrupt_pre_commit_consume(svc, sessions, wid, mp):
    original = svc.gate.consume_effect

    def fault(*a, **kw):
        original(*a, **kw)
        kw["_session"].flush()
        raise Interrupt()
    mp.setattr(svc.gate, "consume_effect", fault)
    with pytest.raises(Interrupt):
        svc.claim(TENANT, ACTOR, wid)


def interrupt_after_claim_commit(svc, sessions, wid, mp):
    svc.claim(TENANT, ACTOR, wid)  # committed; process "dies" before dispatch


def interrupt_mid_dispatch_none_finished(svc, sessions, wid, mp):
    def dead(*a, **k):
        raise Interrupt()
    mp.setattr(svc, "_task", dead)
    with pytest.raises(Interrupt):
        asyncio.run(svc.execute(TENANT, ACTOR, wid))


def interrupt_mid_dispatch_one_finished(svc, sessions, wid, mp):
    original, done = svc._task, threading.Event()

    def task(task_id, code, config):
        if task_id == "a2":
            done.wait(60)  # keep a1's real sandbox run finished before we die, no teardown race
            raise Interrupt()
        try:
            return original(task_id, code, config)
        finally:
            done.set()
    mp.setattr(svc, "_task", task)
    with pytest.raises(Interrupt):
        asyncio.run(svc.execute(TENANT, ACTOR, wid))


def interrupt_finalize_before_commit(svc, sessions, wid, mp):
    def boom(session):
        if any(isinstance(o, sw.SandboxWaveTaskRow) for o in session.new):
            raise Interrupt()
    event.listen(sessions, "before_commit", boom)
    try:
        with pytest.raises(Interrupt):
            asyncio.run(svc.execute(TENANT, ACTOR, wid))
    finally:
        event.remove(sessions, "before_commit", boom)


ATTEMPTS = {
    "S3_after_claim_commit": interrupt_after_claim_commit,
    "S4_mid_dispatch_none_finished": interrupt_mid_dispatch_none_finished,
    "S4_mid_dispatch_one_finished": interrupt_mid_dispatch_one_finished,
    "S5_finalize_before_commit": interrupt_finalize_before_commit,
}
NON_ATTEMPTS = {
    "S2a_probe_unavailable": interrupt_pre_commit_probe,
    "S2b_consume_fault_before_commit": interrupt_pre_commit_consume,
}


@pytest.mark.parametrize("stage", sorted(ATTEMPTS))
def test_interruption_after_claim_leaves_permanent_key_and_no_partial_completion(env, monkeypatch, stage):
    svc, sessions, root = env
    wid, _ = approved(svc)
    plan_before = project_plan(sessions)
    ATTEMPTS[stage](svc, sessions, wid, monkeypatch)
    f = facts(sessions, wid)
    assert f["state"] == "claimed" and f["state"] != "awaiting_review"
    assert f["key"] == expected_key()
    assert f["effects"] == 1
    assert (f["tasks"], f["artifacts"], f["result"]) == (0, 0, None)
    assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


@pytest.mark.parametrize("stage", sorted(NON_ATTEMPTS))
def test_interruption_before_claim_commit_is_not_an_attempt(env, monkeypatch, stage):
    svc, sessions, root = env
    wid, _ = approved(svc)
    NON_ATTEMPTS[stage](svc, sessions, wid, monkeypatch)
    f = facts(sessions, wid)
    assert f["state"] == "awaiting_approval" and f["key"] is None
    assert (f["effects"], f["tasks"], f["artifacts"], f["result"]) == (0, 0, 0, None)
    monkeypatch.undo()
    fresh = sw.SandboxWaveService(sessions, str(root))
    fresh.claim(TENANT, ACTOR, wid)  # nothing was attempted, so the existing guards allow it
    assert facts(sessions, wid)["key"] == expected_key()


def test_completed_wave_is_also_closed_and_not_upgraded(env):
    svc, sessions, root = env
    wid, _ = approved(svc)
    result = asyncio.run(svc.execute(TENANT, ACTOR, wid))
    assert result["state"] == "awaiting_review"
    assert result["result"]["all_dag_completed"] is False
    assert result["result"]["independent_quality_verified"] is False
    assert {t["task_id"] for t in result["result"]["tasks"]} == {"a1", "a2"}  # c never dispatched
    fresh = sw.SandboxWaveService(sessions, str(root))
    must_conflict(lambda: asyncio.run(fresh.execute(TENANT, ACTOR, wid)), "execute on awaiting_review")
    wid2, _ = approved(fresh)
    must_conflict(lambda: fresh.claim(TENANT, ACTOR, wid2), "second wave for project")
    assert facts(sessions, wid)["effects"] == 1


def test_in_process_task_failure_is_a_finalized_unknown_receipt_not_an_interruption(env, monkeypatch):
    svc, sessions, root = env
    wid, _ = approved(svc)

    def bad_read(path, limit):
        raise sw.WaveError("artifact read failed")
    monkeypatch.setattr(sw, "LocalBoundedRead", bad_read)
    # _task catches Exception and returns an 'unknown' receipt; finalize still commits (state S6)
    result = asyncio.run(svc.execute(TENANT, ACTOR, wid))
    assert result["state"] == "awaiting_review"
    assert {t["execution_state"] for t in result["result"]["tasks"]} == {"unknown"}
    assert result["result"]["all_dag_completed"] is False


# --------------------------------------------------------------------------
# partial-state rows: never read as completion
# --------------------------------------------------------------------------

def inject_partial_rows(sessions, wid):
    with sessions.begin() as db:
        db.add(sw.SandboxWaveTaskRow(id="00000000-0000-0000-0000-000000000001", wave_id=wid, task_id="a1",
                                     receipt={"task_id": "a1", "execution_state": "sandbox_executed"}))


def test_injected_partial_task_row_on_claimed_wave_does_not_make_it_complete(env):
    svc, sessions, root = env
    wid, _ = approved(svc)
    plan_before = project_plan(sessions)
    svc.claim(TENANT, ACTOR, wid)
    inject_partial_rows(sessions, wid)
    fresh = sw.SandboxWaveService(sessions, str(root))
    view = fresh.get(TENANT, ACTOR, wid)
    assert view["state"] == "claimed" and view["unknown_after_claim"] is True and view["result"] is None
    must_conflict(lambda: asyncio.run(fresh.execute(TENANT, ACTOR, wid)), "execute with partial task row")
    must_conflict(lambda: fresh.claim(TENANT, ACTOR, wid), "claim with partial task row")
    assert project_plan(sessions) == plan_before


@pytest.mark.xfail(strict=True, reason="KNOWN GAP (doc item 2): artifacts() does not check wave state; "
                   "if the read path ever filters by state this XPASSes and the doc must be updated")
def test_gap_artifacts_read_path_does_not_hide_rows_of_unfinished_wave(env):
    svc, sessions, root = env
    wid, _ = approved(svc)
    svc.claim(TENANT, ACTOR, wid)
    with sessions.begin() as db:
        db.add(sw.SandboxWaveArtifactRow(id="00000000-0000-0000-0000-000000000002", wave_id=wid, task_id="a1",
                                         name="result.txt", sha256="0" * 64, content_base64=""))
    assert svc.artifacts(TENANT, ACTOR, wid) == []


# --------------------------------------------------------------------------
# mutations: treating partial / interrupted state as complete or resumable MUST FAIL the policy
# --------------------------------------------------------------------------

def attempted_claimed_wave(env):
    svc, sessions, root = env
    wid, _ = approved(svc)
    plan_before = project_plan(sessions)
    svc.claim(TENANT, ACTOR, wid)
    return sessions, root, wid, plan_before


def test_policy_baseline_passes_unmutated(env):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)
    assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


def test_mutation_view_reports_complete_when_any_task_row_exists_is_detected(env, monkeypatch):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)
    inject_partial_rows(sessions, wid)
    original = sw.SandboxWaveService._view

    def mutated(row):
        view = original(row)
        return {**view, "state": "awaiting_review", "unknown_after_claim": False}
    monkeypatch.setattr(sw.SandboxWaveService, "_view", staticmethod(mutated))
    with pytest.raises(AssertionError, match="partial state read as complete"):
        assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


def test_mutation_claim_resumes_a_claimed_wave_is_detected(env, monkeypatch):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)
    original = sw.SandboxWaveService.claim

    def mutated(self, tenant, actor, wave_id):
        with self.sessions() as db:
            row = self._owned(db, wave_id, tenant, actor)
            if row.state == "claimed":
                return row.payload, self._probe()  # resume: hand back the saved payload
        return original(self, tenant, actor, wave_id)
    monkeypatch.setattr(sw.SandboxWaveService, "claim", mutated)
    with pytest.raises(AssertionError, match="policy violated"):
        assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


def test_mutation_attempted_key_not_permanent_is_detected(env):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)
    with sessions.begin() as db:
        db.get(sw.SandboxWaveRow, wid).claim_key = None  # key cleared
    with pytest.raises(AssertionError, match="policy violated"):
        assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


def test_mutation_interrupted_wave_marked_awaiting_review_is_detected(env):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)
    with sessions.begin() as db:
        row = db.get(sw.SandboxWaveRow, wid)
        row.state = "awaiting_review"
        row.result = {"tasks": [], "all_dag_completed": False}
    with pytest.raises(AssertionError, match="partial state read as complete"):
        assert_second_process_policy(sessions, root, wid, plan_before, expected_key())


def test_mutation_second_process_dispatches_is_detected(env, monkeypatch):
    sessions, root, wid, plan_before = attempted_claimed_wave(env)

    def mutated(self, tenant, actor, wave_id):
        return {"ready_task_ids": ["a1"], "config": request().model_dump(mode="json")}, {}
    monkeypatch.setattr(sw.SandboxWaveService, "claim", mutated)
    with pytest.raises(AssertionError, match="policy violated"):
        assert_second_process_policy(sessions, root, wid, plan_before, expected_key())
