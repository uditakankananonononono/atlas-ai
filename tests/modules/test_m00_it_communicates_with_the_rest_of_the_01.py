"""AUTHORED-NOT-RUN: real SQLite M00 rows, hermetic stateful stream transport."""
import copy
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.context import TenantContext, require_tenant
from app.modules.m00_approval_center import service as m00
from app.modules.m00_approval_center.it_communicates_with_the_rest_of_the_01 import (
    StreamsSubmissions, TrustedStreamBinding, Submission, create_status_router,
    MAX_ATTEMPTS, MAX_STREAM_ENTRIES, MAX_DLQ_ENTRIES, MAX_ENVELOPE_BYTES,
    RECOVERY_IDLE_MS, RETENTION_POLICY, ReplayConflict, EnvelopeError,
)


class MemoryStreams:
    """Stateful test transport: pending delivery, failure and atomic DLQ semantics.

    Not Redis runtime evidence; audit separately against actual Redis semantics.
    """
    def __init__(self):
        self.entries = {}
        self.pending = {}
        self.acks = []
        self.delivered = set()
        self.calls = []
        self.fail_ack = False
        self.fail_deadletter = False

    async def xadd(self, name, fields, **kwargs):
        rows = self.entries.setdefault(name, [])
        message_id = f"{len(rows)+1}-0"
        rows.append((message_id, dict(fields)))
        self.calls.append(("xadd", name, kwargs))
        return message_id

    async def xreadgroup(self, groupname, consumername, streams, count, block):
        name, cursor = next(iter(streams.items()))
        assert cursor == ">" and block > 0
        delivered = [(mid, fields) for mid, fields in self.entries.get(name, [])
                     if (name, mid) not in self.delivered][:count]
        for mid, fields in delivered:
            self.delivered.add((name, mid))
            self.pending[(name, mid)] = {"times_delivered": 1, "fields": fields}
        return [(name, delivered)] if delivered else []

    async def xpending_range(self, name, groupname, min, max, count):
        item = self.pending.get((name, min))
        return [] if item is None else [{"message_id": min, "times_delivered": item["times_delivered"]}]

    async def xautoclaim(self, name, groupname, consumername, min_idle_time, start_id, count):
        assert min_idle_time == RECOVERY_IDLE_MS
        rows = []
        for (stream, mid), item in self.pending.items():
            if stream == name:
                item["times_delivered"] += 1
                rows.append((mid, item["fields"]))
        return ["0-0", rows[:count], []]

    async def xack(self, name, groupname, *ids):
        if self.fail_ack:
            raise OSError("synthetic ACK failure")
        for mid in ids:
            self.acks.append((name, mid))
            self.pending.pop((name, mid), None)
        return len(ids)

    async def eval(self, script, numkeys, *args):
        assert numkeys == 2 and "XADD" in script and "XACK" in script
        if self.fail_deadletter:
            raise OSError("synthetic DLQ failure")
        stream, dlq, group, message_id, reason, maximum = args
        pending = self.pending.get((stream, message_id))
        if pending is None:
            return 0
        await self.xadd(dlq, {"message_id": message_id, "reason": reason}, maxlen=int(maximum))
        await self.xack(stream, group, message_id)
        return 1


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "stream-submissions.sqlite3"}',
                           connect_args={"check_same_thread": False})
    for row in (m00.ApprovalRequestRow, m00.ApprovalEventRow, m00.ApprovalIdempotencyRow):
        row.__table__.create(engine)
    service = m00.Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False),
                          clock=lambda: datetime(2026, 10, 10, tzinfo=timezone.utc))
    transport = MemoryStreams()
    bindings = [TrustedStreamBinding("tenant-a", "producer-a"), TrustedStreamBinding("tenant-b", "producer-b")]
    channel = StreamsSubmissions(transport, service, bindings)
    yield channel, transport, service, engine
    engine.dispose()


def request(key="same-request", payload=None):
    return Submission(request_id=key, module_id=6, action_type="schedule_post",
                      payload={"copy": "review me"} if payload is None else payload, ttl_seconds=60)


def rows(engine):
    with Session(engine) as db:
        return (db.scalars(select(m00.ApprovalRequestRow)).all(),
                db.scalars(select(m00.ApprovalEventRow)).all(),
                db.scalars(select(m00.ApprovalIdempotencyRow)).all())


@pytest.mark.asyncio
async def test_producer_only_queues_consumer_atomically_persists_before_ack(setup):
    channel, redis, service, engine = setup
    mid = await channel.submit("producer-a", request())
    assert rows(engine) == ([], [], [])
    assert redis.calls[-1][2] == {}  # pending-safe default: NEVER trim active input.
    result = await channel.poll("tenant-a", "worker-a")
    assert result[0]["outcome"] == "persisted"
    stored, events, idem = rows(engine)
    assert len(stored) == len(events) == len(idem) == 1
    row = stored[0]
    assert row.user_id == "tenant-a" and row.module_id == 6
    assert row.action_type == "schedule_post" and row.payload == {"copy": "review me"}
    assert row.status == "pending" and row.approved_by is None
    assert (row.expires_at - row.created_at).total_seconds() == 60
    assert events[0].approval_id == row.id and events[0].event == "created"
    assert idem[0].approval_id == row.id
    assert redis.acks == [(channel.binding("tenant-a").stream, mid)]


@pytest.mark.asyncio
async def test_unknown_principal_and_message_tenant_are_not_authority(setup):
    channel, redis, _, engine = setup
    with pytest.raises(ValueError):
        await channel.submit("untrusted", request())
    binding = channel.binding("tenant-a")
    envelope = request().as_envelope()
    envelope["tenant_id"] = "tenant-b"
    await redis.xadd(binding.stream, {"envelope": json.dumps(envelope)})
    result = await channel.poll("tenant-a", "worker")
    assert result[0]["outcome"] == "retry"
    assert rows(engine) == ([], [], [])
    assert not redis.acks


@pytest.mark.asyncio
async def test_crash_after_commit_ack_failure_recovery_has_one_request_event(setup):
    channel, redis, _, engine = setup
    await channel.submit("producer-a", request())
    redis.fail_ack = True
    with pytest.raises(OSError):
        await channel.poll("tenant-a", "worker")
    assert len(rows(engine)[0]) == 1 and not redis.acks
    redis.fail_ack = False
    recovered = await channel.recover("tenant-a", "replacement", start_id="0-0")
    assert recovered["next_id"] == "0-0"
    assert recovered["results"][0]["outcome"] == "persisted"
    assert [len(items) for items in rows(engine)] == [1, 1, 1]


@pytest.mark.asyncio
async def test_same_request_id_is_isolated_by_trusted_tenant(setup):
    channel, _, _, engine = setup
    for principal, tenant in (("producer-a", "tenant-a"), ("producer-b", "tenant-b")):
        await channel.submit(principal, request())
        await channel.poll(tenant, "worker")
    requests, _, idem = rows(engine)
    assert {r.user_id for r in requests} == {"tenant-a", "tenant-b"}
    assert len({i.key for i in idem}) == 2


@pytest.mark.asyncio
async def test_changed_payload_replay_does_not_create_second_request(setup):
    channel, redis, _, engine = setup
    await channel.submit("producer-a", request())
    await channel.poll("tenant-a", "worker")
    await channel.submit("producer-a", request(payload={"copy": "changed"}))
    result = await channel.poll("tenant-a", "worker")
    assert result[0]["outcome"] == "retry" and result[0]["reason"] == "replay_conflict"
    assert len(rows(engine)[0]) == 1


@pytest.mark.asyncio
async def test_poison_retries_then_deadletters_metadata_only_and_acks(setup):
    channel, redis, _, engine = setup
    binding = channel.binding("tenant-a")
    mid = await redis.xadd(binding.stream, {"envelope": "private malformed text"})
    assert (await channel.poll("tenant-a", "worker"))[0]["outcome"] == "retry"
    for _ in range(MAX_ATTEMPTS-1):
        await channel.recover("tenant-a", "recovery")
    dead, = redis.entries[binding.dlq]
    assert dead[1] == {"message_id": mid, "reason": "invalid_envelope"}
    assert (binding.stream, mid) in redis.acks
    assert rows(engine) == ([], [], [])


@pytest.mark.asyncio
async def test_dlq_failure_never_acknowledges_poison(setup):
    channel, redis, _, _ = setup
    binding = channel.binding("tenant-a")
    mid = await redis.xadd(binding.stream, {"envelope": "{"})
    await channel.poll("tenant-a", "worker")
    redis.pending[(binding.stream, mid)]["times_delivered"] = MAX_ATTEMPTS
    redis.fail_deadletter = True
    with pytest.raises(OSError):
        await channel.recover("tenant-a", "recovery")
    assert not redis.acks and (binding.stream, mid) in redis.pending


@pytest.mark.asyncio
async def test_deleted_pending_entry_is_reported_not_claimed_persisted(setup):
    channel, redis, _, _ = setup
    async def deleted(**kwargs):
        return ["0-0", [], ["19-0"]]
    redis.xautoclaim = deleted
    result = await channel.recover("tenant-a", "worker")
    assert result["deleted_ids"] == ["19-0"] and result["results"] == []


@pytest.mark.parametrize("change", [
    {"module_id": True}, {"module_id": 999}, {"ttl_seconds": True},
    {"payload": {"nested": {1: "not-json-key"}}}, {"payload": {"x": float("nan")}},
    {"action_type": ""}, {"request_id": " "},
])
def test_invalid_submission_fails_without_serialization(change):
    values = dict(request().__dict__)
    values.update(change)
    with pytest.raises(EnvelopeError):
        Submission(**values).as_envelope()


def test_limits_and_retention_are_explicit_without_pending_loss():
    assert MAX_ATTEMPTS == 3 and RECOVERY_IDLE_MS == 60000
    assert MAX_ENVELOPE_BYTES == 65536 and MAX_DLQ_ENTRIES == 1000
    assert MAX_STREAM_ENTRIES is None
    assert "never automatically trimmed" in RETENTION_POLICY


def test_sync_rest_status_missing_and_cross_tenant_same_404_no_payload(setup):
    _, _, service, _ = setup
    stored = service.submit(module_id=6, action_type="schedule_post",
                            payload={"private": "tenant-b-only"}, user_id="tenant-b")
    app = FastAPI()
    app.include_router(create_status_router(service))
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant-a", "reader")
    with TestClient(app) as client:
        missing = client.get("/approval-stream-status/requests/absent")
        foreign = client.get("/approval-stream-status/requests/" + stored["id"])
        assert missing.status_code == foreign.status_code == 404
        assert missing.json() == foreign.json() == {"detail": "approval not found"}
        assert "tenant-b-only" not in foreign.text
        app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant-b", "reader")
        own = client.get("/approval-stream-status/requests/" + stored["id"])
        assert own.status_code == 200 and own.json()["status"] == "pending"
        assert own.json()["id"] == stored["id"]
        assert client.post("/approval-stream-status/requests", json={}).status_code == 404


def test_router_is_unmounted_in_existing_module_source():
    from pathlib import Path
    module = Path(__file__).resolve().parents[2] / "backend/app/modules/m00_approval_center/__init__.py"
    assert "it_communicates_with_the_rest_of_the_01" not in module.read_text()


@pytest.mark.asyncio
async def test_ack_observes_committed_request_and_event_on_separate_session(setup):
    channel, redis, _, engine = setup
    original_ack = redis.xack
    async def checked_ack(*args):
        requests, events, idem = rows(engine)
        assert len(requests) == len(events) == len(idem) == 1
        assert events[0].approval_id == requests[0].id
        return await original_ack(*args)
    redis.xack = checked_ack
    await channel.submit("producer-a", request())
    assert (await channel.poll("tenant-a", "worker"))[0]["outcome"] == "persisted"


@pytest.mark.asyncio
async def test_event_write_failure_rolls_back_all_rows_and_never_acks(setup):
    from sqlalchemy import event
    channel, redis, _, engine = setup
    def reject_event(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO m00_approval_events" in statement:
            raise RuntimeError("synthetic event write failure")
    event.listen(engine, "before_cursor_execute", reject_event)
    try:
        await channel.submit("producer-a", request())
        with pytest.raises(RuntimeError, match="synthetic event write failure"):
            await channel.poll("tenant-a", "worker")
        assert rows(engine) == ([], [], [])
        assert not redis.acks
    finally:
        event.remove(engine, "before_cursor_execute", reject_event)


@pytest.mark.asyncio
async def test_explicit_group_setup_uses_beginning_and_does_not_swallow_errors(setup):
    channel, redis, _, _ = setup
    calls = []
    async def create(**kwargs):
        calls.append(kwargs)
        return True
    redis.xgroup_create = create
    assert await channel.create_group("tenant-a") is True
    assert calls == [{"name": channel.binding("tenant-a").stream,
                      "groupname": channel.GROUP, "id": "0-0", "mkstream": True}]
    async def reject(**kwargs):
        raise OSError("synthetic group configuration failure")
    redis.xgroup_create = reject
    with pytest.raises(OSError):
        await channel.create_group("tenant-a")


def test_duplicate_json_key_and_oversize_envelope_refused():
    for raw in ('{"version":1,"version":1}', 'x' * (MAX_ENVELOPE_BYTES+1)):
        with pytest.raises(EnvelopeError):
            Submission.decode({"envelope": raw})


@pytest.mark.asyncio
async def test_no_new_messages_after_ack_and_replay_payload_isolated(setup):
    channel, redis, _, engine = setup
    submission = request()
    await channel.submit("producer-a", submission)
    submission.payload["copy"] = "mutated after queueing"
    await channel.poll("tenant-a", "worker")
    assert await channel.poll("tenant-a", "worker") == []
    assert rows(engine)[0][0].payload == {"copy": "review me"}


# Named guard pins: source literals were read before authoring these tests.
# Source checks complement behavior tests; they do not execute Lua/Redis ACLs.
def test_exact_hash_tag_names_and_same_slot_deadletter_keys(setup):
    import hashlib
    channel, _, _, _ = setup
    binding = channel.binding("tenant-a")
    slot = hashlib.sha256(b"tenant-a").hexdigest()
    assert binding.stream == "atlas:m00:{" + slot + "}:submissions"
    assert binding.dlq == "atlas:m00:{" + slot + "}:deadletters"
    assert binding.stream.split("{")[1].split("}")[0] == binding.dlq.split("{")[1].split("}")[0]


def test_duplicate_principal_and_unbound_tenant_guards(setup):
    channel, redis, service, _ = setup
    with pytest.raises(ValueError, match="unique trusted bindings"):
        StreamsSubmissions(redis, service, [TrustedStreamBinding("a", "same"), TrustedStreamBinding("b", "same")])
    with pytest.raises(ValueError, match="unbound trusted tenant"):
        channel.binding("not-configured")


def test_content_digest_binds_trusted_tenant_and_replay_checks_row_owner(setup):
    import hashlib
    from app.modules.m00_approval_center.it_communicates_with_the_rest_of_the_01 import _encode
    channel, _, _, engine = setup
    envelope = request().as_envelope()
    approval_id = channel._persist("tenant-a", envelope)
    with Session(engine) as db:
        idem, = db.scalars(select(m00.ApprovalIdempotencyRow)).all()
        expected = hashlib.sha256(_encode({"tenant_id": "tenant-a", "submission": envelope}).encode()).hexdigest()
        assert idem.request_hash == expected
        row = db.get(m00.ApprovalRequestRow, approval_id)
        row.user_id = "tenant-b"
        db.commit()
    with pytest.raises(ReplayConflict):
        channel._persist("tenant-a", envelope)


@pytest.mark.parametrize("count", [0, 2])
def test_replay_refuses_any_created_event_count_other_than_one(setup, count):
    channel, _, _, engine = setup
    envelope = request().as_envelope()
    approval_id = channel._persist("tenant-a", envelope)
    with Session(engine) as db:
        event, = db.scalars(select(m00.ApprovalEventRow)).all()
        if count == 0:
            db.delete(event)
        else:
            db.add(m00.ApprovalEventRow(approval_id=approval_id, event="created", actor=None, at=event.at))
        db.commit()
    with pytest.raises(RuntimeError, match="creation evidence unavailable"):
        channel._persist("tenant-a", envelope)


def test_precommit_evidence_recheck_is_inside_real_transaction_literal():
    import inspect
    source = inspect.getsource(StreamsSubmissions._persist)
    assert 'with self.service._sessions.begin() as db:' in source
    assert 'db.flush()' in source
    assert 'if existing(db) != row.id:' in source
    assert source.index('db.flush()') < source.index('if existing(db) != row.id:') < source.index('approval_id = row.id')
    assert source.index('if existing(db) != row.id:') < source.index('except IntegrityError:')


def test_rest_ownership_query_guard_runs_before_payload_get(setup):
    channel, _, service, engine = setup
    from sqlalchemy import event
    foreign = service.submit(module_id=6, action_type="schedule_post", payload={"private": "foreign"}, user_id="tenant-b")
    calls = []
    original = service.get
    def observed(approval_id):
        calls.append(approval_id)
        return original(approval_id)
    service.get = observed
    statements = []
    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    app = FastAPI()
    app.include_router(create_status_router(service))
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant-a", "reader")
    try:
        with TestClient(app) as client:
            missing = client.get("/approval-stream-status/requests/missing")
            other = client.get("/approval-stream-status/requests/"+foreign["id"])
        assert missing.status_code == other.status_code == 404
        assert missing.json() == other.json()
        assert calls == []
        selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
        assert len(selects) == 2
        assert all("m00_approval_requests.payload" not in s for s in selects)
        assert all("m00_approval_requests.user_id =" in s for s in selects)
    finally:
        event.remove(engine, "before_cursor_execute", observe)


@pytest.mark.parametrize("mode", ["missing-after-check", "foreign-after-check"])
def test_rest_each_postcheck_guard_refuses_missing_or_changed_owner(setup, mode):
    _, _, service, _ = setup
    own = service.submit(module_id=6, action_type="schedule_post", payload={"private": "must-not-leak"}, user_id="tenant-a")
    def changed(approval_id):
        if mode == "missing-after-check":
            raise m00.ApprovalNotFoundError(approval_id)
        return {**own, "user_id": "tenant-b"}
    service.get = changed
    app = FastAPI()
    app.include_router(create_status_router(service))
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant-a", "reader")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/approval-stream-status/requests/"+own["id"])
    assert response.status_code == 404
    assert response.json() == {"detail": "approval not found"}
    assert "must-not-leak" not in response.text


def test_deadletter_lua_exact_text_and_no_payload_field():
    from app.modules.m00_approval_center.it_communicates_with_the_rest_of_the_01 import _DEADLETTER
    assert _DEADLETTER == """
local pending = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[2], ARGV[2], 1)
if #pending == 0 then return 0 end
redis.call('XADD', KEYS[2], 'MAXLEN', '=', ARGV[4], '*',
           'message_id', ARGV[2], 'reason', ARGV[3])
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
return 1
"""
    assert "payload" not in _DEADLETTER
    assert _DEADLETTER.index("XADD") < _DEADLETTER.index("XACK")


@pytest.mark.parametrize("ttl", [0, -1, 31536001])
def test_ttl_outside_exact_bounds_refused(ttl):
    with pytest.raises(EnvelopeError):
        Submission("r", 6, "schedule_post", {}, ttl).as_envelope()


@pytest.mark.parametrize("ttl", [1, 31536000])
def test_ttl_exact_boundaries_accepted(ttl):
    assert Submission("r", 6, "schedule_post", {}, ttl).as_envelope()["ttl_seconds"] == ttl


@pytest.mark.parametrize("payload", [[], None, "text"])
def test_payload_must_be_dict(payload):
    with pytest.raises(EnvelopeError):
        Submission("r", 6, "schedule_post", payload).as_envelope()


def test_duplicate_key_unique_and_depth_limit():
    from app.modules.m00_approval_center.it_communicates_with_the_rest_of_the_01 import _unique, _json_value
    with pytest.raises(EnvelopeError):
        _unique([("same", 1), ("same", 2)])
    _json_value({}, depth=32)
    with pytest.raises(EnvelopeError):
        _json_value({}, depth=33)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, -1, 101, True])
async def test_batch_boundaries_invalid_never_read_transport(setup, count):
    channel, redis, _, _ = setup
    async def forbidden(**kwargs):
        pytest.fail("invalid batch must not reach Redis")
    redis.xreadgroup = forbidden
    with pytest.raises(ValueError, match="invalid batch count"):
        await channel.poll("tenant-a", "worker", count=count)


@pytest.mark.asyncio
async def test_batch_maximum_100_is_forwarded(setup):
    channel, redis, _, _ = setup
    from app.modules.m00_approval_center.it_communicates_with_the_rest_of_the_01 import MAX_BATCH
    assert MAX_BATCH == 100
    calls = []
    async def observe(**kwargs):
        calls.append(kwargs)
        return []
    redis.xreadgroup = observe
    assert await channel.poll("tenant-a", "worker", count=100) == []
    assert calls[0]["count"] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("message_id", ["bad", "1", "-1-0", "1-0x"])
async def test_redis_entry_id_regex_precedes_pending_read(setup, message_id):
    channel, redis, _, _ = setup
    async def forbidden(**kwargs):
        pytest.fail("invalid entry ID reached Redis")
    redis.xpending_range = forbidden
    with pytest.raises(ValueError, match="invalid Redis entry id"):
        await channel._handle(channel.binding("tenant-a"), message_id, {})


@pytest.mark.asyncio
async def test_stream_name_bytes_decoded_and_unexpected_name_rejected(setup):
    channel, redis, _, _ = setup
    async def bytes_name(**kwargs):
        return [(channel.binding("tenant-a").stream.encode(), [])]
    redis.xreadgroup = bytes_name
    assert await channel.poll("tenant-a", "worker") == []
    async def wrong_name(**kwargs):
        return [(b"foreign-stream", [])]
    redis.xreadgroup = wrong_name
    with pytest.raises(RuntimeError, match="unexpected stream"):
        await channel.poll("tenant-a", "worker")


@pytest.mark.asyncio
@pytest.mark.parametrize("pending", [[], [{}, {}]])
async def test_pending_must_be_exactly_one(setup, pending):
    channel, redis, _, engine = setup
    async def result(**kwargs):
        return pending
    redis.xpending_range = result
    value = await channel._handle(channel.binding("tenant-a"), "1-0", {})
    assert value["outcome"] == "pending_unavailable"
    assert rows(engine) == ([], [], []) and not redis.acks


@pytest.mark.asyncio
@pytest.mark.parametrize("attempts", [True, "3", 0, None])
async def test_pending_attempts_must_be_positive_exact_integer(setup, attempts):
    channel, redis, _, engine = setup
    async def result(**kwargs):
        return [{"times_delivered": attempts}]
    redis.xpending_range = result
    with pytest.raises(RuntimeError, match="pending delivery count unavailable"):
        await channel._handle(channel.binding("tenant-a"), "1-0", {})
    assert rows(engine) == ([], [], []) and not redis.acks


@pytest.mark.asyncio
@pytest.mark.parametrize("result_value", [0, 2])
async def test_deadletter_result_only_one_is_success(setup, result_value):
    channel, redis, _, _ = setup
    async def pending(**kwargs):
        return [{"times_delivered": MAX_ATTEMPTS}]
    async def result(*args):
        return result_value
    redis.xpending_range = pending
    redis.eval = result
    value = await channel._handle(channel.binding("tenant-a"), "1-0", {})
    assert value["outcome"] == "pending_unavailable" and not redis.acks


def test_integrity_error_with_no_replay_winner_is_reraised(setup, monkeypatch):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    channel, _, _, engine = setup
    def inject(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO m00_approval_requests" in statement:
            raise IntegrityError(statement, parameters, RuntimeError("synthetic no-winner constraint"))
    event.listen(engine, "before_cursor_execute", inject)
    try:
        with pytest.raises(IntegrityError):
            channel._persist("tenant-a", request().as_envelope())
        assert rows(engine) == ([], [], [])
    finally:
        event.remove(engine, "before_cursor_execute", inject)


def test_missing_created_event_inside_transaction_prevents_commit(setup):
    from sqlalchemy import event
    channel, _, _, engine = setup
    def remove_creation(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO m00_approval_events" in statement:
            connection.exec_driver_sql("DELETE FROM m00_approval_events")
    event.listen(engine, "after_cursor_execute", remove_creation)
    try:
        with pytest.raises(RuntimeError, match="creation evidence unavailable"):
            channel._persist("tenant-a", request().as_envelope())
        assert rows(engine) == ([], [], [])
    finally:
        event.remove(engine, "after_cursor_execute", remove_creation)


@pytest.mark.parametrize("version", [0, 2, -1, True, "1", None])
def test_envelope_non_one_version_is_refused_before_submission(version):
    envelope = request().as_envelope()
    envelope["version"] = version
    with pytest.raises(EnvelopeError):
        Submission.decode({"envelope": json.dumps(envelope)})


@pytest.mark.asyncio
async def test_bad_version_retries_then_deadletters_without_request_or_event(setup):
    channel, redis, _, engine = setup
    binding = channel.binding("tenant-a")
    envelope = request().as_envelope()
    envelope["version"] = 2
    mid = await redis.xadd(binding.stream, {"envelope": json.dumps(envelope)})
    first = await channel.poll("tenant-a", "worker")
    assert first == [{"message_id": mid, "outcome": "retry", "reason": "invalid_envelope"}]
    assert rows(engine) == ([], [], []) and not redis.acks
    second = await channel.recover("tenant-a", "replacement")
    assert second["results"][0]["outcome"] == "retry"
    assert rows(engine) == ([], [], []) and not redis.acks
    third = await channel.recover("tenant-a", "replacement")
    assert third["results"] == [{"message_id": mid, "outcome": "deadlettered", "reason": "invalid_envelope"}]
    assert rows(engine) == ([], [], [])
    dead, = redis.entries[binding.dlq]
    assert dead[1] == {"message_id": mid, "reason": "invalid_envelope"}
    assert redis.acks == [(binding.stream, mid)]


def test_duplicate_tenant_is_refused_with_distinct_principals(setup):
    _, redis, service, _ = setup
    with pytest.raises(ValueError, match="unique trusted bindings"):
        StreamsSubmissions(redis, service, [
            TrustedStreamBinding("same-tenant", "different-producer-a"),
            TrustedStreamBinding("same-tenant", "different-producer-b"),
        ])
