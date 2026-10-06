import json
from pathlib import Path
from app.modules.registry import IMPLEMENTED_SPECS

AUDIT = json.loads(Path("audits/ledger-140.json").read_text())

def test_all_140_rows_are_audited_once():
    rows = AUDIT["rows"]
    assert len(rows) == 140
    assert [row["row"] for row in rows] == list(range(1, 141))
    assert {row["status"] for row in rows} <= {"verified-pushed", "thin", "missing", "UNSUPPORTED"}

def test_verified_rows_have_real_code_commit_and_test_evidence():
    for row in AUDIT["rows"]:
        if row["status"] != "verified-pushed":
            continue
        assert row["mounted_route"] is True
        assert len(row["implementation_commit"]) == 40
        assert Path(row["implementation_path"]).exists()
        assert Path(row["test_evidence"]).exists()

def test_all_product_modules_are_live_registered():
    assert {spec.id for spec in IMPLEMENTED_SPECS} == set(range(26))


def test_narrative_checkpoint_counts_match_machine_ledger():
    from collections import Counter
    counts=Counter(row["status"] for row in AUDIT["rows"])
    assert counts == {"verified-pushed":139, "UNSUPPORTED":1}
    assert [r["row"] for r in AUDIT["rows"] if r["status"]=="UNSUPPORTED"] == [43]


def test_row_43_unsupported_verdict_is_explicit_and_unmounted():
    row = next(r for r in AUDIT["rows"] if r["row"] == 43)
    assert row["status"] == "UNSUPPORTED" and row["mounted_route"] is False
    assert "UNSUPPORTED" in row["audit_note"] and "unmounted" in row["audit_note"]
    assert Path(row["implementation_path"]).exists() and Path(row["test_evidence"]).exists()


def test_row_127_unsupported_verdict_names_deterministic_interface():
    import json as _json
    rows = _json.loads(Path("audits/expanded-owner-spec.json").read_text())["rows"]
    row = next(r for r in rows if r["id"] == 127)
    assert row["status"] == "UNSUPPORTED"
    assert "deterministic interface" in row["claim_audit"] and "UNSUPPORTED" in row["claim_audit"]
