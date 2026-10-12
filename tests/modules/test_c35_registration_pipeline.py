"""c35.registration_pipeline tests (row 99): packet build with waiver,
review-gated state machine, local handoff export, hard refusals."""
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c35 import registration_pipeline as rp  # noqa: E402

REQ = {"as_of": "2026-10-12",
       "olympiad": {"name": "Synthetic Physics Cup", "deadline": "2026-11-01",
                    "requirements": ["Full Name", "school"],
                    "fee": "USD 50", "contact_email": "org@example.org",
                    "contact_name": "Dr X"},
       "profile": {"full_name": "Test Student", "school": "Test School"}}


def test_packet_includes_checklist_and_waiver():
    pkt = rp.build_packet(REQ)
    assert pkt["state"] == "pending_review"
    assert pkt["waiver_draft"] is not None
    assert pkt["artifact_hash"]


def test_free_olympiad_skips_waiver():
    req = dict(REQ, olympiad=dict(REQ["olympiad"], fee="free"))
    pkt = rp.build_packet(req)
    assert pkt["waiver_draft"] is None


def test_full_review_handoff_flow(tmp_path):
    pkt = rp.build_packet(REQ)
    store = {pkt["id"]: pkt}
    with pytest.raises(ValueError, match="APPLY_REFUSED_STATE"):
        rp.export_handoff(store, pkt["id"], str(tmp_path))
    rp.review(store, pkt["id"], "approve", "Udita")
    assert store[pkt["id"]]["state"] == "owner_approved"
    assert store[pkt["id"]]["review"]["exact_artifact_hash"] == pkt["artifact_hash"]
    out = rp.export_handoff(store, pkt["id"], str(tmp_path))
    assert out["state"] == "handoff_exported"
    files = out["files"]
    assert len(files) == 3  # packet.json + waiver.txt + README.txt
    for f in files:
        assert pathlib.Path(f).exists()
    saved = json.loads(pathlib.Path(files[0]).read_text())
    assert saved["olympiad"]["name"] == "Synthetic Physics Cup"
    readme = pathlib.Path(files[2]).read_text()
    assert "did not register" in readme


def test_reject_returns_to_draft():
    pkt = rp.build_packet(REQ)
    store = {pkt["id"]: pkt}
    rp.review(store, pkt["id"], "reject", "Udita")
    assert store[pkt["id"]]["state"] == "draft"


@pytest.mark.parametrize("key,code", [
    ("send", "SEND"), ("register", "REGISTER"), ("pay", "SPEND"),
    ("password", "NOCREDS"), ("attempt", "ATTEMPT")])
def test_forbidden_keys_refuse(key, code):
    req = dict(REQ)
    req[key] = True
    with pytest.raises(ValueError, match="APPLY_REFUSED_%s" % code):
        rp.build_packet(req)


def test_nested_forbidden_key_refused():
    req = dict(REQ, olympiad=dict(REQ["olympiad"], extra={"smtp_host": "x"}))
    with pytest.raises(ValueError, match="APPLY_REFUSED_SEND"):
        rp.build_packet(req)
