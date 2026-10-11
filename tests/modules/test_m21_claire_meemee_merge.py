"""C4 meemee-merge: ported meemee capabilities as additive Claire modules.

Every test is hermetic and deterministic: clocks and resolvers are injected.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m21_claire.meemee_goal_leasing import GoalConflict, GoalStore
from app.modules.m21_claire.meemee_job_queue import JobQueue
from app.modules.m21_claire.meemee_checkpoints import CheckpointConflict, CheckpointStore
from app.modules.m21_claire.meemee_checkins import (
    CheckInPreferences, CheckInScheduler, QuietHours, in_quiet_hours, next_due, slot_name,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, start: datetime = T0):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


# ---------------------------------------------------------------- goal leasing

def test_goal_create_requires_principal_and_description():
    store = GoalStore(clock=Clock())
    with pytest.raises(ValueError):
        store.create("", "x")
    with pytest.raises(ValueError):
        store.create("udita", "   ")


def test_goal_cannot_depend_on_itself_or_unknown_goal():
    store = GoalStore(clock=Clock())
    with pytest.raises(ValueError):
        store.create("udita", "self", depends_on=["self"], goal_id="self")
    with pytest.raises(KeyError):
        store.create("udita", "orphan", depends_on=["missing"])
    with pytest.raises(KeyError):
        store.create("udita", "child", parent_id="missing")


def test_goal_claim_respects_dependencies_priority_and_lease():
    clock = Clock()
    store = GoalStore(clock=clock)
    dep = store.create("udita", "dependency", priority=0)
    high = store.create("udita", "high", priority=5)
    store.create("udita", "blocked", priority=9, depends_on=[dep["id"]])
    claimed = store.claim("udita", "worker-1", lease_seconds=60)
    assert claimed["id"] == high["id"]  # blocked goal is skipped despite higher priority
    assert claimed["status"] == "active"
    assert claimed["lease_owner"] == "worker-1"
    # Live lease fences other workers out of "high"; only "dep" remains claimable.
    other = store.claim("udita", "worker-2", lease_seconds=60)
    assert other is not None and other["id"] == dep["id"]
    assert store.claim("udita", "worker-3", lease_seconds=60) is None
    # After expiry another worker can claim the still-open goal again.
    clock.advance(seconds=61)
    reclaimed = store.claim("udita", "worker-2", lease_seconds=60)
    assert reclaimed is not None and reclaimed["id"] == high["id"]


def test_goal_renew_requires_live_owned_lease():
    clock = Clock()
    store = GoalStore(clock=clock)
    goal = store.create("udita", "leased")
    store.claim("udita", "worker-1", lease_seconds=30)
    with pytest.raises(GoalConflict):
        store.renew("udita", goal["id"], "worker-2", lease_seconds=30)
    clock.advance(seconds=31)
    with pytest.raises(GoalConflict):
        store.renew("udita", goal["id"], "worker-1", lease_seconds=30)
    with pytest.raises(ValueError):
        store.renew("udita", goal["id"], "worker-1", lease_seconds=0)


def test_goal_transitions_are_checked_and_completion_needs_dependencies():
    clock = Clock()
    store = GoalStore(clock=clock)
    dep = store.create("udita", "dependency")
    goal = store.create("udita", "main", depends_on=[dep["id"]])
    claimed = store.claim("udita", "worker-1", lease_seconds=120)
    assert claimed["id"] == dep["id"]  # only the dependency is claimable
    store.transition("udita", dep["id"], "completed", worker_id="worker-1", outcome="ok")
    with pytest.raises(GoalConflict):
        store.transition("udita", dep["id"], "active")  # terminal states are final
    claimed = store.claim("udita", "worker-1", lease_seconds=120)
    assert claimed["id"] == goal["id"]
    with pytest.raises(GoalConflict):
        store.transition("udita", goal["id"], "completed", worker_id="worker-2")
    with pytest.raises(GoalConflict):
        store.transition("udita", goal["id"], "completed", worker_id="worker-1",
                         expected_version=claimed["version"] + 1)
    done = store.transition("udita", goal["id"], "completed", worker_id="worker-1",
                            expected_version=claimed["version"], outcome="shipped")
    assert done["status"] == "completed" and done["outcome"] == "shipped"
    assert done["lease_owner"] is None


def test_goal_completion_with_open_dependency_is_refused():
    store = GoalStore(clock=Clock())
    dep = store.create("udita", "dependency")
    goal = store.create("udita", "main", depends_on=[dep["id"]])
    store.claim("udita", "w", lease_seconds=60)
    store.transition("udita", goal["id"], "active")
    with pytest.raises(GoalConflict, match="dependencies"):
        store.transition("udita", goal["id"], "completed", worker_id="w")


def test_goal_list_is_principal_scoped_and_ordered():
    store = GoalStore(clock=Clock())
    store.create("udita", "low", priority=1)
    store.create("udita", "high", priority=9)
    store.create("other", "not hers", priority=99)
    listed = store.list("udita")
    assert [g["description"] for g in listed] == ["high", "low"]
    assert [g["description"] for g in store.list("udita", status="pending")] == ["high", "low"]


# ------------------------------------------------------------------- job queue

def test_job_enqueue_requires_goal_and_positive_attempts():
    queue = JobQueue(clock=Clock())
    with pytest.raises(ValueError):
        queue.enqueue("")
    with pytest.raises(ValueError):
        queue.enqueue("goal", max_attempts=0)
    with pytest.raises(ValueError):
        queue.enqueue("goal", principal=" ")


def test_job_claim_runs_due_jobs_once_and_counts_attempts():
    clock = Clock()
    queue = JobQueue(clock=clock)
    future = queue.enqueue("later", run_at=clock.now + timedelta(minutes=5))
    assert queue.claim() is None
    ident = queue.enqueue("now", principal="udita")
    job = queue.claim()
    assert job["id"] == ident and job["status"] == "running" and job["attempts"] == 1
    assert queue.claim() is None  # running jobs are not reclaimed; future job is not due
    clock.advance(minutes=6)
    queue.finish(ident, {"ok": True})
    job = queue.claim()
    assert job["id"] == future


def test_job_fail_retries_until_max_attempts_then_terminal():
    queue = JobQueue(clock=Clock())
    ident = queue.enqueue("flaky", max_attempts=2)
    first = queue.claim()
    assert first["attempts"] == 1
    assert queue.fail(ident, "boom") is True
    second = queue.claim()
    assert second["attempts"] == 2 and second["status"] == "running"
    assert queue.fail(ident, "boom again") is True
    job = queue.get(ident)
    assert job["status"] == "failed" and job["error"] == "boom again"
    assert queue.claim() is None


def test_job_cancel_semantics_for_queued_and_running():
    queue = JobQueue(clock=Clock())
    queued = queue.enqueue("queued")
    assert queue.cancel(queued) is True
    assert queue.get(queued)["status"] == "cancelled"
    running = queue.enqueue("running")
    queue.claim()
    assert queue.cancel(running) is False  # running jobs need cooperative cancellation
    assert queue.request_cancel(running) == "cancel_requested"
    assert queue.cancel_running(running) is True
    assert queue.get(running)["status"] == "cancelled"


def test_job_events_are_recorded_in_order():
    queue = JobQueue(clock=Clock())
    ident = queue.enqueue("tracked")
    queue.claim()
    queue.finish(ident, {"done": True})
    kinds = [event["kind"] for event in queue.events(ident)]
    assert kinds == ["enqueued", "running", "done"]
    with pytest.raises(KeyError):
        queue.events("missing")


def test_job_finish_and_fail_require_running():
    queue = JobQueue(clock=Clock())
    ident = queue.enqueue("x")
    assert queue.finish(ident, {}) is False
    assert queue.fail(ident, "e") is False
    queue.claim()
    assert queue.finish(ident, {"ok": 1}) is True
    assert queue.get(ident)["result"] == {"ok": 1}


def test_job_principal_scoping():
    queue = JobQueue(clock=Clock())
    mine = queue.enqueue("mine", principal="udita")
    queue.enqueue("theirs", principal="other")
    assert [j["id"] for j in queue.list_for_principal("udita")] == [mine]
    assert queue.get_owned(mine, "other") is None
    assert queue.get_owned(mine, "udita")["goal"] == "mine"


# ------------------------------------------------------------------ checkpoints

def test_checkpoint_save_requires_fields_and_canonicalizes_state():
    store = CheckpointStore()
    with pytest.raises(ValueError):
        store.save("", "run", "goal", "phase", {})
    saved = store.save("udita", "run-1", "goal-1", "plan", {"b": 1, "a": [2]})
    assert saved["sequence"] == 1 and saved["state"] == {"a": [2], "b": 1}
    assert len(saved["state_sha256"]) == 64


def test_checkpoint_sequence_conflict_and_expected_sequence():
    store = CheckpointStore()
    store.save("udita", "run-1", "goal-1", "plan", {"n": 1})
    with pytest.raises(CheckpointConflict):
        store.save("udita", "run-1", "goal-1", "act", {"n": 2}, expected_sequence=5)
    saved = store.save("udita", "run-1", "goal-1", "act", {"n": 2}, expected_sequence=1)
    assert saved["sequence"] == 2


def test_checkpoint_idempotency_key_replays_or_conflicts():
    store = CheckpointStore()
    first = store.save("udita", "run-1", "goal-1", "plan", {"n": 1}, idempotency_key="k1")
    replay = store.save("udita", "run-1", "goal-1", "plan", {"n": 1}, idempotency_key="k1")
    assert replay["id"] == first["id"] and replay["sequence"] == 1
    with pytest.raises(CheckpointConflict):
        store.save("udita", "run-1", "goal-1", "plan", {"n": 2}, idempotency_key="k1")
    with pytest.raises(CheckpointConflict):
        store.save("udita", "run-1", "goal-1", "other-phase", {"n": 1}, idempotency_key="k1")


def test_checkpoint_resume_and_history():
    store = CheckpointStore()
    store.save("udita", "run-1", "goal-1", "plan", {"n": 1})
    store.save("udita", "run-1", "goal-1", "act", {"n": 2})
    resumed = store.resume("udita", "run-1")
    assert resumed["next_sequence"] == 3 and resumed["phase"] == "act"
    assert resumed["state"] == {"n": 2} and resumed["goal_id"] == "goal-1"
    history = store.history("udita", "run-1", after=1)
    assert [c["sequence"] for c in history] == [2]
    with pytest.raises(KeyError):
        store.resume("udita", "missing")
    with pytest.raises(KeyError):
        store.get("udita", "run-1", 99)


def test_checkpoint_state_checksum_is_verified_on_read():
    store = CheckpointStore()
    saved = store.save("udita", "run-1", "goal-1", "plan", {"n": 1})
    # Simulate tampering with the stored canonical document.
    run = store._runs[("udita", "run-1")]
    run[0]["state"] = '{"n":999}'
    with pytest.raises(ValueError, match="checksum"):
        store.get("udita", "run-1", 1)
    del saved


# --------------------------------------------------------------------- checkins

def test_in_quiet_hours_windows_including_overnight_and_allday():
    quiet = QuietHours(start="22:00", end="07:00")
    assert in_quiet_hours(datetime(2026, 10, 11, 23, 30), quiet)
    assert in_quiet_hours(datetime(2026, 10, 11, 3, 0), quiet)
    assert not in_quiet_hours(datetime(2026, 10, 11, 12, 0), quiet)
    same = QuietHours(start="08:00", end="08:00")
    assert in_quiet_hours(datetime(2026, 10, 11, 12, 0), same)  # start == end means all day
    day = QuietHours(start="09:00", end="17:00")
    assert in_quiet_hours(datetime(2026, 10, 11, 9, 0), day)
    assert not in_quiet_hours(datetime(2026, 10, 11, 17, 0), day)


def test_next_due_requires_aware_clock_and_skips_quiet_hours():
    prefs = CheckInPreferences(cadence_minutes=60, quiet_hours=QuietHours("22:00", "07:00"))
    with pytest.raises(ValueError):
        next_due(prefs, UTC, datetime(2026, 10, 11, 20, 0))  # naive clock refused
    due = next_due(prefs, UTC, datetime(2026, 10, 11, 21, 30, tzinfo=UTC))
    assert not in_quiet_hours(due, prefs.quiet_hours)
    assert due == datetime(2026, 10, 11, 22, 45, tzinfo=UTC) or due > datetime(2026, 10, 11, 22, 30, tzinfo=UTC)
    no_quiet = CheckInPreferences(cadence_minutes=30)
    assert next_due(no_quiet, UTC, datetime(2026, 10, 11, 10, 0, tzinfo=UTC)) == datetime(2026, 10, 11, 10, 30, tzinfo=UTC)


def test_next_due_fails_when_quiet_hours_leave_no_slot():
    prefs = CheckInPreferences(cadence_minutes=1, quiet_hours=QuietHours("00:00", "23:59"))
    # Only one minute per day is deliverable at 1-minute cadence with 15-minute
    # quiet stepping, so this must exhaust the two-week guard.
    with pytest.raises(ValueError, match="quiet hours"):
        next_due(prefs, UTC, datetime(2026, 10, 11, 0, 0, tzinfo=UTC))


def test_slot_name_is_utc_and_stable():
    due = datetime(2026, 10, 11, 7, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert slot_name(due) == "20261011T0200Z"


def test_checkin_scheduler_reuses_pending_and_plans_after_quiet():
    scheduler = CheckInScheduler()
    prefs = CheckInPreferences(cadence_minutes=60, quiet_hours=QuietHours("22:00", "07:00"),
                               channel="whatsapp", address="+15550100000")
    scheduler.set_preferences("udita", prefs)
    after = datetime(2026, 10, 11, 20, 30, tzinfo=UTC)
    planned = scheduler.plan_user("udita", after=after)
    assert planned is not None and planned["channel"] == "whatsapp"
    assert not in_quiet_hours(planned["due"], prefs.quiet_hours)
    again = scheduler.plan_user("udita", after=after)
    assert again["slot"] == planned["slot"]  # polling does not duplicate check-ins
    disabled = CheckInPreferences(cadence_minutes=60, enabled=False)
    scheduler.set_preferences("nobody", disabled)
    assert scheduler.plan_user("nobody", after=after) is None
    assert scheduler.plan_user("unknown", after=after) is None


# ------------------------------------------------------------- device protocol

from app.modules.m21_claire.meemee_device_protocol import (
    ReplayGuard, VerifiedCommand, canonical_json, make_command, sign, verify_command,
)

SECRET = b"test-secret-key"


def test_canonical_json_is_sorted_and_rejects_non_finite():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"x": object()})


def test_make_and_verify_command_roundtrip():
    envelope = make_command("dev-1", "type_text", {"text": "hi"}, SECRET, issued_at=1_700_000_000)
    verified = verify_command(envelope, SECRET, expected_device_id="dev-1",
                              allowed_capabilities={"type_text"}, now=1_700_000_100)
    assert isinstance(verified, VerifiedCommand)
    assert verified.device_id == "dev-1" and verified.capability == "type_text"


def test_verify_command_rejects_tampering_and_wrong_device():
    envelope = make_command("dev-1", "type_text", {"text": "hi"}, SECRET, issued_at=1_700_000_000)
    tampered = {**envelope, "arguments": {"text": "rm -rf"}}
    with pytest.raises(ValueError, match="signature"):
        verify_command(tampered, SECRET, now=1_700_000_100)
    with pytest.raises(ValueError, match="another device"):
        verify_command(envelope, SECRET, expected_device_id="dev-2", now=1_700_000_100)
    with pytest.raises(PermissionError):
        verify_command(envelope, SECRET, allowed_capabilities={"click"}, now=1_700_000_100)
    with pytest.raises(ValueError, match="stale"):
        verify_command(envelope, SECRET, now=1_700_001_000)


def test_verify_command_rejects_bad_envelopes_and_replays():
    envelope = make_command("dev-1", "click", {}, SECRET, issued_at=1_700_000_000)
    with pytest.raises(ValueError, match="envelope"):
        verify_command({**envelope, "extra": 1}, SECRET, now=1_700_000_100)
    with pytest.raises(ValueError, match="signature"):
        verify_command({**envelope, "signature": "zz"}, SECRET, now=1_700_000_100)
    clock = [1_700_000_100.0]
    guard = ReplayGuard(ttl_seconds=300, clock=lambda: clock[0])
    verify_command(envelope, SECRET, replay_guard=guard, now=1_700_000_100)
    with pytest.raises(ValueError, match="replayed"):
        verify_command(envelope, SECRET, replay_guard=guard, now=1_700_000_100)


def test_replay_guard_expires_nonces():
    clock = [1000.0]
    guard = ReplayGuard(ttl_seconds=60, clock=lambda: clock[0])
    assert guard.claim("n1") is True
    assert guard.claim("n1") is False
    clock[0] += 61
    assert guard.claim("n1") is True


def test_make_command_field_validation():
    with pytest.raises(ValueError):
        make_command("", "click", {}, SECRET)
    with pytest.raises(ValueError):
        make_command("dev", "", {}, SECRET)
    with pytest.raises(ValueError):
        make_command("dev", "click", [], SECRET)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        make_command("dev", "click", {}, SECRET, issued_at="now")  # type: ignore[arg-type]


# ------------------------------------------------------------ webhook security

from app.modules.m21_claire.meemee_webhook_security import (
    compute_signature, validate_webhook_url, verify_signature,
)


def _signed(secret: str, timestamp: str, body: bytes) -> str:
    return compute_signature(secret, timestamp, body)


def test_webhook_signature_roundtrip_and_replay_window():
    body = b'{"event":"goal.done"}'
    signature = _signed("s3cret", "1700000000", body)
    assert verify_signature("s3cret", "1700000000", body, signature, now=1_700_000_100)
    assert not verify_signature("s3cret", "1700000000", body, signature, now=1_700_001_000)
    assert not verify_signature("wrong", "1700000000", body, signature, now=1_700_000_100)
    assert not verify_signature("s3cret", "1700000001", body, signature, now=1_700_000_100)
    assert not verify_signature("s3cret", "1700000000", b'{"event":"other"}', signature, now=1_700_000_100)


def test_webhook_signature_rejects_malformed_inputs():
    body = b"{}"
    assert not verify_signature("s", "not-a-number", body, "sha256=abc", now=1)
    assert not verify_signature("s", "1700000000", body, "md5=abc", now=1_700_000_100)
    assert not verify_signature("s", "1700000000", body, "sha256=é", now=1_700_000_100)
    assert not verify_signature("s", "1700000000", body, "sha256=abc", tolerance_seconds=-1, now=1_700_000_100)


def test_webhook_url_requires_https_without_credentials():
    resolver = lambda host, port: ["93.184.216.34"]
    assert validate_webhook_url("https://example.com/hook", resolver=resolver) == "https://example.com/hook"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_webhook_url("http://example.com/hook", resolver=resolver)
    with pytest.raises(ValueError, match="credentials"):
        validate_webhook_url("https://user:pw@example.com/hook", resolver=resolver)
    with pytest.raises(ValueError, match="HTTPS"):
        validate_webhook_url("ftp://example.com", resolver=resolver)


def test_webhook_url_refuses_private_resolution():
    for address in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1", "::1"):
        with pytest.raises(ValueError, match="private"):
            validate_webhook_url("https://example.com/hook", resolver=lambda h, p, a=address: [a])
    # One private address among many still refuses.
    with pytest.raises(ValueError, match="private"):
        validate_webhook_url("https://example.com/hook", resolver=lambda h, p: ["93.184.216.34", "10.1.1.1"])


# ------------------------------------------------------------- semantic memory

from app.modules.m21_claire.meemee_semantic_memory import (
    HashingEmbedder, SemanticMemory, cosine,
)


def test_hashing_embedder_is_deterministic_normalized_and_local():
    embedder = HashingEmbedder(128)
    first = embedder.embed("Claire plans a grant proposal")
    second = embedder.embed("Claire plans a grant proposal")
    assert first == second and len(first) == 128
    norm = sum(v * v for v in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9
    assert embedder.space_id == "lexical-hashing-blake2b-v1:128"
    with pytest.raises(ValueError):
        HashingEmbedder(8)


def test_cosine_similarity_bounds_and_validation():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
    with pytest.raises(ValueError):
        cosine([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        cosine([float("inf")], [1.0])


def test_semantic_memory_search_ranks_similar_first_and_scopes_owners():
    memory = SemanticMemory(HashingEmbedder(256))
    memory.add("udita", "grant proposal for ocean robotics", {"kind": "goal"})
    memory.add("udita", "pinterest board of pastel stationery", {"kind": "like"})
    memory.add("other", "grant proposal for ocean robotics", {"kind": "goal"})
    hits = memory.search("udita", "robotics grant", limit=5)
    assert hits and hits[0]["text"] == "grant proposal for ocean robotics"
    assert all(hit["owner"] == "udita" for hit in hits)
    assert 0 < hits[0]["score"] <= 1.0
    assert memory.search("udita", "", limit=5) == [] or memory.search("udita", "zzzz", limit=0) == []


def test_semantic_memory_binds_one_embedding_space():
    memory = SemanticMemory(HashingEmbedder(256))
    with pytest.raises(ValueError, match="space"):
        memory.add_with_vector("udita", "x", [0.1] * 128, space_id="other-space")


# -------------------------------------------------------------------- briefing

from app.modules.m21_claire.meemee_briefing import BriefingBuilder, DailyBriefing


def _timeline(owner_id, *, start, end, limit):
    return [
        {"id": 1, "source_id": "gmail", "kind": "email", "title": "Grant deadline",
         "occurred_at": "2026-10-11T08:00:00+00:00"},
        {"id": 2, "source_id": "whatsapp", "kind": "message", "title": "Ideas",
         "occurred_at": "2026-10-11T07:00:00+00:00"},
    ][:limit]


def test_briefing_builds_sections_with_sources_and_counts():
    builder = BriefingBuilder(_timeline, personal_model=lambda owner: [
        {"id": "p1", "kind": "goal", "title": "Atlas", "confidence": 0.9},
        {"id": "p2", "kind": "note", "title": "skip", "confidence": 0.1},
    ])
    briefing = builder.build("udita", at=datetime(2026, 10, 11, 9, 0, tzinfo=UTC))
    assert isinstance(briefing, DailyBriefing)
    data = briefing.to_dict()
    assert data["item_count"] == 3
    assert data["source_ids"] == ["gmail", "whatsapp"]
    keys = [section["key"] for section in data["sections"]]
    assert keys == ["timeline", "priorities"]
    assert data["sections"][1]["items"][0]["title"] == "Atlas"


def test_briefing_validates_inputs_and_handles_empty():
    builder = BriefingBuilder(_timeline)
    with pytest.raises(ValueError):
        builder.build("")
    with pytest.raises(ValueError):
        builder.build("udita", lookback_hours=0)
    with pytest.raises(ValueError):
        builder.build("udita", max_events=0)
    empty = BriefingBuilder(lambda owner_id, *, start, end, limit: []).build(
        "udita", at=datetime(2026, 10, 11, 9, 0, tzinfo=UTC))
    assert empty.sections == [] and empty.source_ids == []


# ----------------------------------------------------------------- cancellation

from app.modules.m21_claire.meemee_cancellation import CancellationRegistry, RunGate


def test_cancellation_registry_register_request_unregister():
    registry = CancellationRegistry()
    event = registry.register("job-1")
    assert not event.is_set()
    assert registry.request("job-1") is True and event.is_set()
    assert registry.request("missing") is False
    with pytest.raises(ValueError):
        registry.register("job-1")
    registry.unregister("job-1")
    assert registry.request("job-1") is False
    registry.unregister("job-1")  # idempotent


def test_run_gate_drains_and_refuses_new_work():
    async def scenario():
        gate = RunGate()
        await gate.enter()
        assert gate.active == 1 and gate.accepting
        drain = asyncio.create_task(gate.drain(timeout=1.0))
        await asyncio.sleep(0)
        assert not gate.accepting
        with pytest.raises(RuntimeError, match="draining"):
            await gate.enter()
        await gate.leave()
        assert await drain is True
        with pytest.raises(RuntimeError, match="underflow"):
            await gate.leave()
    asyncio.run(scenario())


def test_run_gate_drain_times_out_with_active_work():
    async def scenario():
        gate = RunGate()
        await gate.enter()
        assert await gate.drain(timeout=0.01) is False
    asyncio.run(scenario())


# --------------------------------------------------------------- secret scrub

from app.modules.m21_claire.meemee_secret_scrub import marker, scrub_text


def test_scrub_removes_tokens_and_passwords_with_stable_markers():
    text = "key sk-abcdefghij0123456789abcd and password: hunter2hunter ok"
    scrubbed = scrub_text(text)
    assert "sk-abcdefghij0123456789abcd" not in scrubbed
    assert "hunter2hunter" not in scrubbed
    assert "password=[REDACTED:" in scrubbed
    assert scrub_text("nothing secret here") == "nothing secret here"
    first = marker("same-secret")
    assert first == marker("same-secret") and first.startswith("[REDACTED:") and first.endswith(":11]")


# ------------------------------------------------------------- event identity

from app.modules.m21_claire.meemee_event_identity import EventIdentity, identify_event


def test_identify_event_new_replay_conflict():
    decision = identify_event("udita", "gmail", "evt-1", {"a": 1})
    assert decision.status == "new"
    replay = identify_event("udita", "gmail", "evt-1", {"a": 1}, prior=decision.identity)
    assert replay.status == "replay"
    conflict = identify_event("udita", "gmail", "evt-1", {"a": 2}, prior=decision.identity)
    assert conflict.status == "conflict"


def test_identify_event_validates_identities_and_payloads():
    with pytest.raises(ValueError):
        identify_event(" padded ", "src", "evt", {})
    with pytest.raises(ValueError):
        identify_event("udita", "src", "evt", {"big": "x" * 40000})
    with pytest.raises(TypeError):
        identify_event("udita", "src", "evt", [1, 2])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        identify_event("udita", "src", "evt", {"nan": float("nan")})
    decision = identify_event("udita", "gmail", "evt-1", {"a": 1})
    other = EventIdentity("udita", "gmail", "evt-2", decision.identity.payload_sha256)
    with pytest.raises(ValueError, match="mismatch"):
        identify_event("udita", "gmail", "evt-1", {"a": 1}, prior=other)


# ------------------------------------------------------------------ rate/quota

from app.modules.m21_claire.meemee_rate_quota import FixedWindowLimiter, QuotaExceeded, QuotaStore, quota_day


def test_fixed_window_limiter_counts_and_resets():
    clock = [1_000.0]
    limiter = FixedWindowLimiter(limit=3, window_seconds=60, clock=lambda: clock[0])
    assert limiter.hit("user") == (True, 2, 1020)
    assert limiter.hit("user")[0] is True
    allowed, remaining, reset = limiter.hit("user")
    assert (allowed, remaining) == (True, 0)
    assert limiter.hit("user")[0] is False
    assert limiter.hit("someone-else")[0] is True
    clock[0] += 60
    assert limiter.hit("user")[0] is True  # window rolled


def test_fixed_window_limiter_validates_config_and_cleans_up():
    with pytest.raises(ValueError):
        FixedWindowLimiter(limit=0, window_seconds=60)
    with pytest.raises(ValueError):
        FixedWindowLimiter(limit=5, window_seconds=0)
    clock = [1_000.0]
    limiter = FixedWindowLimiter(limit=5, window_seconds=60, clock=lambda: clock[0])
    limiter.hit("user")
    clock[0] += 300
    assert limiter.cleanup() == 1
    assert limiter.cleanup() == 0


def test_quota_store_daily_limits_and_rollover():
    day = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
    store = QuotaStore(default_daily_jobs=2)
    assert quota_day(day).isoformat() == "2026-10-11"
    with pytest.raises(ValueError):
        quota_day(datetime(2026, 10, 11, 9, 0))  # naive clock refused
    first = store.consume_job("udita", now=day)
    assert first["used"] == 1 and first["remaining"] == 1
    store.consume_job("udita", now=day)
    with pytest.raises(QuotaExceeded):
        store.consume_job("udita", now=day)
    status = store.status("udita", now=day)
    assert status == {"day": "2026-10-11", "used": 2, "limit": 2, "remaining": 0}
    tomorrow = day + timedelta(days=1)
    assert store.consume_job("udita", now=tomorrow)["used"] == 1
    store.set_limit("udita", 5)
    assert store.limit("udita") == 5
    with pytest.raises(ValueError):
        store.set_limit("udita", 0)


# -------------------------------------------------------------------- cursors

from app.modules.m21_claire.meemee_cursors import decode_cursor, encode_cursor


def test_cursor_roundtrip_and_rejection():
    cursor = encode_cursor("2026-10-11T00:00:00+00:00", "row-42")
    assert decode_cursor(cursor) == ("2026-10-11T00:00:00+00:00", "row-42")
    for bad in ("", "not-base64!!!", "e30", "WzEsMl0"):  # "", junk, "{}", "[1,2]"
        with pytest.raises(ValueError, match="invalid pagination cursor"):
            decode_cursor(bad)


# ------------------------------------------------------------ approval grants

from app.modules.m21_claire.meemee_approval_grants import (
    ApprovalGrantStore, constraints_match, normalize_expiry, validate_constraints,
)


def test_normalize_expiry_canonicalizes_and_rejects_garbage():
    assert normalize_expiry(None) is None
    assert normalize_expiry("2026-10-11T09:00:00Z") == "2026-10-11T09:00:00+00:00"
    assert normalize_expiry("2026-10-11T09:00:00") == "2026-10-11T09:00:00+00:00"
    with pytest.raises(ValueError, match="ISO 8601"):
        normalize_expiry("next tuesday")


def test_constraints_validation_and_matching():
    validate_constraints({"a": [1, "x", True, None], "b": {"c": 1.5}})
    with pytest.raises(ValueError):
        validate_constraints({"x": float("nan")})
    with pytest.raises(ValueError):
        validate_constraints({"x": {1: "bad key"}})
    assert constraints_match({"to": "a@b.c", "n": 1}, {"to": "a@b.c", "n": 1, "extra": 1})
    assert not constraints_match({"n": 1}, {"n": True})  # bool is not int
    assert not constraints_match({"ok": True}, {"ok": 1})
    assert not constraints_match({"n": 1}, {"n": 2})
    assert not constraints_match({"missing": 1}, {})
    assert constraints_match(None, {"anything": 1})


def test_approval_grant_store_expiry_revoke_and_constraints():
    store = ApprovalGrantStore()
    with pytest.raises(ValueError):
        store.grant("", "tool", "udita")
    store.grant("udita", "browser_navigate", "udita",
                expires_at="2026-10-12T00:00:00Z",
                argument_constraints={"domain": "example.com"})
    before = datetime(2026, 10, 11, tzinfo=UTC)
    after = datetime(2026, 10, 13, tzinfo=UTC)
    assert store.allows("udita", "browser_navigate", now=before, arguments={"domain": "example.com"})
    assert not store.allows("udita", "browser_navigate", now=before, arguments={"domain": "evil.com"})
    assert not store.allows("udita", "browser_navigate", now=after, arguments={"domain": "example.com"})
    assert store.active_count("udita", now=before) == 1
    assert store.active_count("udita", now=after) == 0
    assert store.revoke("udita", "browser_navigate") is True
    assert store.revoke("udita", "browser_navigate") is False
    assert not store.allows("udita", "browser_navigate", now=before, arguments={"domain": "example.com"})
    store.grant("udita", "read_file", "udita")
    # delete_principal removes every grant, active or revoked.
    assert store.delete_principal("udita") == 2
    assert store.list("udita") == []


# ------------------------------------------------------------------ delegation

from app.modules.m21_claire.meemee_delegation import AgentTeam


class _Child:
    owns_model = False

    def __init__(self, log=None, fail=False):
        self.log = log
        self.fail = fail
        self.closed = False

    async def run(self, goal, owner_id=None, **kwargs):
        if self.log is not None:
            self.log.append(("start", goal))
            await asyncio.sleep(0.01)
            self.log.append(("end", goal))
        if self.fail:
            raise RuntimeError("child exploded")
        return {"goal": goal, "done": True}

    async def aclose(self):
        self.closed = True


def test_agent_team_delegates_with_concurrency_cap_and_reports():
    log = []
    team = AgentTeam(lambda: _Child(log), max_concurrency=2)
    goals = [f"goal-{i}" for i in range(5)]
    reports = asyncio.run(team.delegate(goals, owner_id="udita"))
    assert [r["ok"] for r in reports] == [True] * 5
    assert [r["goal"] for r in reports] == goals
    # With a cap of 2, the third child cannot start before one of the first two ends.
    starts = [i for i, (event, _) in enumerate(log) if event == "start"]
    first_end = next(i for i, (event, _) in enumerate(log) if event == "end")
    assert starts[2] > first_end


def test_agent_team_bounds_goal_count_and_isolates_failures():
    team = AgentTeam(lambda: _Child())
    with pytest.raises(ValueError):
        asyncio.run(team.delegate([], owner_id="udita"))
    with pytest.raises(ValueError):
        asyncio.run(team.delegate([f"g{i}" for i in range(33)], owner_id="udita"))
    children = []

    def factory():
        child = _Child(fail=len(children) == 0)
        children.append(child)
        return child

    team = AgentTeam(factory, max_concurrency=2)
    reports = asyncio.run(team.delegate(["bad", "good"], owner_id="udita"))
    assert reports[0]["ok"] is False and "exploded" in reports[0]["error"]
    assert reports[1]["ok"] is True
    assert all(child.closed for child in children)


def test_agent_team_owner_isolation_check():
    class NoOwner:
        owns_model = False
        async def run(self, goal):
            return {"goal": goal}

    team = AgentTeam(lambda: NoOwner())
    reports = asyncio.run(team.delegate(["x"], owner_id="udita"))
    assert reports[0]["ok"] is False and "owner isolation" in reports[0]["error"]
    # Default owner needs no isolation support.
    reports = asyncio.run(team.delegate(["x"], owner_id="default"))
    assert reports[0]["ok"] is True
