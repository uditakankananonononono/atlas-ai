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


# --- gate follow-up: tamper evidence, path confinement, store validation ---

def approved_store():
    pkt = rp.build_packet(REQ)
    store = {pkt["id"]: pkt}
    rp.review(store, pkt["id"], "approve", "Udita")
    return store, pkt["id"]


def test_export_refuses_post_review_mutation(tmp_path):
    store, pid = approved_store()
    store[pid]["checklist"]["injected"] = "mutated after approval"
    with pytest.raises(ValueError, match="APPLY_REFUSED_TAMPERED"):
        rp.export_handoff(store, pid, str(tmp_path))


def test_review_refuses_pre_review_mutation():
    pkt = rp.build_packet(REQ)
    store = {pkt["id"]: pkt}
    pkt["checklist"]["injected"] = "mutated before approval"
    with pytest.raises(ValueError, match="APPLY_REFUSED_TAMPERED"):
        rp.review(store, pkt["id"], "approve", "Udita")


def test_review_refuses_forged_artifact_hash():
    pkt = rp.build_packet(REQ)
    store = {pkt["id"]: pkt}
    pkt["artifact_hash"] = "0" * 64  # forged: does not match current content
    with pytest.raises(ValueError, match="APPLY_REFUSED_TAMPERED"):
        rp.review(store, pkt["id"], "approve", "Udita")


def test_export_refuses_traversal_packet_id(tmp_path):
    store, pid = approved_store()
    pkt = store[pid]
    evil = dict(pkt)
    evil["id"] = "pkt-../../etc/evil"
    store["pkt-../../etc/evil"] = evil
    with pytest.raises(ValueError, match="APPLY_REFUSED_STORE:packet-id"):
        rp.export_handoff(store, "pkt-../../etc/evil", str(tmp_path))
    assert not (tmp_path.parent / "etc").exists()


def test_export_never_overwrites(tmp_path):
    store, pid = approved_store()
    out = rp.export_handoff(store, pid, str(tmp_path))
    # attacker/operator resets state and tries to re-export over the bundle
    store[pid]["state"] = "owner_approved"
    with pytest.raises(ValueError, match="APPLY_REFUSED_OVERWRITE"):
        rp.export_handoff(store, pid, str(tmp_path))
    for f in out["files"]:  # originals intact
        assert pathlib.Path(f).exists()


def test_store_entry_shape_validated(tmp_path):
    store, pid = approved_store()
    store[pid]["unexpected_key"] = True
    with pytest.raises(ValueError, match="APPLY_REFUSED_STORE"):
        rp.export_handoff(store, pid, str(tmp_path))
    store2, pid2 = approved_store()
    store2[pid2]["state"] = "handoff_exported; rm -rf"
    with pytest.raises(ValueError, match="APPLY_REFUSED_STORE"):
        rp.export_handoff(store2, pid2, str(tmp_path))


def test_export_outside_symlink_confined(tmp_path):
    # output dir itself is fine, but a pre-existing symlinked file name must
    # not redirect the write outside root
    store, pid = approved_store()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    target = tmp_path / "out"
    target.mkdir()
    link = target / (pid + ".packet.json")
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="APPLY_REFUSED_(OVERWRITE|PATH)"):
        rp.export_handoff(store, pid, str(target))
    assert outside.read_text() == "secret"


def test_export_dangling_symlink_refused(tmp_path):
    store, pid = approved_store()
    target = tmp_path / "out"
    target.mkdir()
    link = target / (pid + ".packet.json")
    try:
        link.symlink_to(tmp_path / "does-not-exist-yet.txt")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="APPLY_REFUSED_(OVERWRITE|PATH)"):
        rp.export_handoff(store, pid, str(target))
    assert not (tmp_path / "does-not-exist-yet.txt").exists()
