"""Tests for reproducible run manifests."""

import json

from app.modules.m12_ai_research_lab.lane_models import StepRecord, sha256_hex, canonical_json
from app.modules.m12_ai_research_lab.lane_runs import (
    build_manifest, read_manifest, verify_manifest, write_manifest_atomic,
)


def sample_manifest():
    return build_manifest(
        run_id="run-1",
        workflow_name="wf",
        config={"b": 2, "a": 1},
        run_input={"q": "what is 2+2?"},
        code_version="abc123",
        seed=42,
        steps=(StepRecord(step_id="s1", kind="llm", status="completed",
                          model_id="m1", cost_micro=100),),
        status="completed",
        total_cost_micro=100,
        created_at_utc="2026-09-20T12:00:00+00:00",
    )


def test_roundtrip_write_read_verify(tmp_path):
    m = sample_manifest()
    path = write_manifest_atomic(tmp_path / "run-1.manifest.json", m)
    back = read_manifest(path)
    assert back == m
    v = verify_manifest(path)
    assert v.ok, v.problems
    assert v.manifest == m


def test_verify_detects_tampering(tmp_path):
    path = write_manifest_atomic(tmp_path / "m.json", sample_manifest())
    payload = json.loads(path.read_text())
    payload["manifest"]["total_cost_micro"] = 999999
    path.write_text(json.dumps(payload))
    v = verify_manifest(path)
    assert not v.ok
    assert any("digest mismatch" in p for p in v.problems)


def test_verify_detects_config_hash_tampering(tmp_path):
    path = write_manifest_atomic(tmp_path / "m.json", sample_manifest())
    payload = json.loads(path.read_text())
    payload["manifest"]["config"]["a"] = 999
    # Recompute only the top-level digest so config_hash must catch it.
    path.write_text(json.dumps(payload))
    v = verify_manifest(path)
    assert not v.ok
    assert any("config_hash" in p or "digest mismatch" in p for p in v.problems)


def test_config_hash_is_canonical():
    m1 = build_manifest("r", "w", {"a": 1, "b": 2}, "in", created_at_utc="t")
    m2 = build_manifest("r", "w", {"b": 2, "a": 1}, "in", created_at_utc="t")
    assert m1.config_hash == m2.config_hash
    assert m1.config_hash == sha256_hex(canonical_json({"a": 1, "b": 2}))
    assert m1.input_hash == m2.input_hash


def test_digest_stable_for_same_content():
    m1 = sample_manifest()
    m2 = sample_manifest()
    assert m1.digest() == m2.digest()


def test_write_is_atomic_and_creates_parents(tmp_path):
    target = tmp_path / "nested" / "deep" / "m.json"
    write_manifest_atomic(target, sample_manifest())
    assert target.exists()
    leftovers = list(target.parent.glob("*.tmp"))
    assert leftovers == []


def test_unreadable_manifest_reports_problem(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    v = verify_manifest(bad)
    assert not v.ok
    assert any("unreadable" in p for p in v.problems)


def test_manifest_captures_environment():
    m = build_manifest("r", "w", {}, None)
    assert m.python_version.count(".") == 2
    assert m.platform
