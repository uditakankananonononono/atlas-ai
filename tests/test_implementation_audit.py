import json
from pathlib import Path
from app.modules.registry import IMPLEMENTED_SPECS

AUDIT = json.loads(Path("audits/ledger-140.json").read_text())

def test_all_140_rows_are_audited_once():
    rows = AUDIT["rows"]
    assert len(rows) == 140
    assert [row["row"] for row in rows] == list(range(1, 141))
    assert {row["status"] for row in rows} <= {"verified-pushed", "thin", "missing"}

def test_verified_rows_have_real_code_commit_and_test_evidence():
    for row in AUDIT["rows"]:
        if row["status"] != "verified-pushed":
            continue
        assert row["mounted_route"] is True
        assert len(row["implementation_commit"]) == 40
        assert Path(row["implementation_path"]).exists()
        assert Path(row["test_evidence"]).exists()

def test_all_product_modules_are_live_registered():
    assert {spec.id for spec in IMPLEMENTED_SPECS} == set(range(25))


def test_narrative_checkpoint_counts_match_machine_ledger():
    from collections import Counter
    counts=Counter(row["status"] for row in AUDIT["rows"])
    assert counts == {"verified-pushed":140}
