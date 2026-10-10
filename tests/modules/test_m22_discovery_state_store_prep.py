"""Integrator-executed isolated helper contracts; service tests are separate."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "backend/app/modules/m22_tools_hub/discovery_state_store.py"
spec = importlib.util.spec_from_file_location("m22_discovery_state_prep", MODULE)
store_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store_module)
Store = store_module.DiscoveryStateStore
StateError = store_module.StateError


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path, "tenant-a")
    result.provision()
    return result


def test_missing_state_is_not_silently_first_run(tmp_path):
    with pytest.raises(StateError, match="missing_state"):
        Store(tmp_path, "new").read()


def test_cooldown_stats_survive_restart(store):
    store.record_source("public-source", success=False, candidates=0, latency_ms=4.2, cooldown_until=300)
    restarted = Store(store.root, "tenant-a")
    assert restarted.is_cooling("public-source", now=299)
    assert not restarted.is_cooling("public-source", now=300)
    stats = restarted.read()["sources"][store_module.fingerprint("public-source", "source")]
    assert stats["runs"] == stats["failures"] == 1


def test_success_cannot_erase_unexpired_cooldown(store):
    store.record_source("s", success=False, candidates=0, latency_ms=1, cooldown_until=900)
    store.record_source("s", success=True, candidates=2, latency_ms=1)
    assert Store(store.root, "tenant-a").is_cooling("s", now=899)


def test_repeat_diff_survives_restart_including_empty_snapshot(store):
    assert store.record_query("q", [], at=100)["first_run"] is True
    restarted = Store(store.root, "tenant-a")
    assert restarted.record_query("q", [digest("a")], at=101) == {
        "first_run": False, "added": [digest("a")], "removed": []}
    assert restarted.record_query("q", [], at=102) == {
        "first_run": False, "added": [], "removed": [digest("a")]}


def test_history_is_bounded_without_evicting_query_identity(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_HISTORY", 2)
    for n in range(4):
        store.record_query("same", [], at=n)
    state = store.read()
    assert len(state["history"]) == 2
    assert next(iter(state["queries"].values()))["runs"] == 4


def test_query_capacity_refuses_without_changing_state(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_QUERIES", 1)
    store.record_query("one", [], at=1)
    before = store.path.read_bytes()
    with pytest.raises(StateError, match="query_capacity"):
        store.record_query("two", [], at=2)
    assert store.path.read_bytes() == before
    assert not store.record_query("one", [], at=3)["first_run"]


def test_source_capacity_never_evicts_cooling_source(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_SOURCES", 1)
    store.record_source("one", success=False, candidates=0, latency_ms=1, cooldown_until=1000)
    with pytest.raises(StateError, match="source_capacity"):
        store.record_source("two", success=True, candidates=0, latency_ms=1)
    assert store.is_cooling("one", now=900)


def test_tenant_files_are_isolated_and_swapped_file_refused(store):
    other = Store(store.root, "tenant-b")
    other.provision()
    assert other.path != store.path
    store.record_query("q", [], at=1)
    assert not other.read()["queries"]
    other.path.write_bytes(store.path.read_bytes())
    with pytest.raises(StateError, match="tenant_mismatch"):
        other.read()


@pytest.mark.parametrize("raw", [b"{", b'{"state":{},"state":{},"checksum":"bad"}', b'[]'])
def test_corrupt_state_is_refused_never_overwritten(store, raw):
    store.path.write_bytes(raw)
    with pytest.raises(StateError):
        store.record_query("q", [], at=1)
    assert store.path.read_bytes() == raw
    with pytest.raises(StateError, match="state_exists"):
        store.provision()


def test_checksum_and_unknown_version_refused(store):
    original = json.loads(store.path.read_bytes())
    original["state"]["revision"] += 1
    store.path.write_text(json.dumps(original))
    with pytest.raises(StateError, match="checksum_mismatch"):
        store.read()
    original["state"]["schema_version"] = 99
    store.path.write_text(json.dumps(original))
    with pytest.raises(StateError, match="unsupported_version"):
        store.read()


def test_arbitrary_query_source_text_not_serialized(store):
    marker = "sensitive-example-marker-not-a-credential"
    store.record_query(marker, [digest("candidate")], at=1)
    store.record_source(marker, success=False, candidates=0, latency_ms=1, cooldown_until=100)
    assert marker.encode() not in store.path.read_bytes()
    assert marker not in store.path.name


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_clock_numbers_refused_without_change(store, value):
    before = store.path.read_bytes()
    with pytest.raises(StateError):
        store.record_query("q", [], at=value)
    assert store.path.read_bytes() == before


def test_candidate_text_and_unknown_kind_refused(store):
    with pytest.raises(StateError):
        store.record_query("q", ["a display name"], at=1)
    with pytest.raises(StateError):
        store.record_query("q", [], at=1, kinds=["unexpected"])


def test_failed_replace_keeps_prior_state_and_sanitizes_error(store, monkeypatch):
    before = store.path.read_bytes()
    def refuse(*args):
        raise OSError("private-example-error-do-not-persist")
    monkeypatch.setattr(store_module.os, "replace", refuse)
    with pytest.raises(StateError, match="commit_unverified") as caught:
        store.record_query("q", [], at=1)
    assert str(caught.value) == "commit_unverified"
    assert store.path.read_bytes() == before
    assert not list(store.root.glob(".m22-discovery-*"))


def test_atomic_replace_and_readback_are_required(store, monkeypatch):
    actual = store_module.os.replace
    calls = []
    def replace(src, dest):
        calls.append((Path(src), Path(dest)))
        actual(src, dest)
        Path(dest).write_bytes(b"corrupt-after-replace")
    monkeypatch.setattr(store_module.os, "replace", replace)
    with pytest.raises(StateError):
        store.record_query("q", [], at=1)
    assert len(calls) == 1
    assert calls[0][0].parent == calls[0][1].parent


def test_stale_store_instances_merge_updates_under_lock(store):
    other = Store(store.root, "tenant-a")
    store.record_query("a", [], at=1)
    other.record_query("b", [], at=2)
    assert len(store.read()["queries"]) == 2


def test_state_byte_limit_refused_before_replace(store, monkeypatch):
    before = store.path.read_bytes()
    monkeypatch.setattr(store_module, "MAX_BYTES", len(before) + 20)
    with pytest.raises(StateError, match="state_too_large"):
        store.record_query("q", [digest("candidate")], at=1)
    assert store.path.read_bytes() == before


def test_symlink_state_is_not_followed(store, tmp_path):
    store.path.unlink()
    target = tmp_path / "target"
    target.write_bytes(b"private-example")
    store.path.symlink_to(target)
    with pytest.raises(StateError):
        store.read()
    assert target.read_bytes() == b"private-example"


def test_concurrent_writers_do_not_lose_counter_updates(store):
    from concurrent.futures import ThreadPoolExecutor
    def update(_):
        Store(store.root, "tenant-a").record_source(
            "s", success=True, candidates=1, latency_ms=1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(update, range(12)))
    stats = next(iter(store.read()["sources"].values()))
    assert stats["runs"] == stats["candidates"] == 12


def test_fifo_state_is_refused_without_blocking(store):
    import os
    store.path.unlink()
    os.mkfifo(store.path)
    with pytest.raises(StateError, match="unsafe_storage"):
        store.read()


def test_unknown_fields_refused_even_with_recomputed_checksum(store):
    envelope = json.loads(store.path.read_bytes())
    envelope["state"]["unapproved_field"] = "unapproved-text"
    envelope["checksum"] = hashlib.sha256(store_module._encode(envelope["state"])).hexdigest()
    store.path.write_text(json.dumps(envelope))
    with pytest.raises(StateError, match="invalid_state"):
        store.read()
