"""C4 meemee-merge: inventory ledger integrity tests."""
from __future__ import annotations

import pytest

from app.modules.m21_claire.meemee_merge_inventory import (
    CLAIRE_MODULE, MEEMEE_CAPABILITIES, MEEMEE_PIN, MEEMEE_REPO,
    inventory_report, inventory_rows, validate_ported_targets,
)


def test_every_row_is_well_formed():
    for row in MEEMEE_CAPABILITIES:
        assert row["id"] and row["meemee_source"] and row["category"]
        assert row["disposition"] in {"PORTED", "ALREADY_PRESENT", "REJECTED", "DEFERRED"}
        assert row["reason"], row["id"]
        if row["disposition"] == "PORTED":
            assert row["target"].startswith("app.modules.m21_claire.meemee_"), row["id"]
            assert ":" in row["target"], row["id"]
        if row["disposition"] == "ALREADY_PRESENT":
            assert row["target"], row["id"]


def test_capability_ids_are_unique():
    ids = [row["id"] for row in MEEMEE_CAPABILITIES]
    assert len(ids) == len(set(ids))


def test_counts_are_computed_not_asserted():
    report = inventory_report()
    rows = inventory_rows()
    assert report["total_capabilities"] == len(rows)
    assert sum(report["by_disposition"].values()) == len(rows)
    assert sum(report["by_category"].values()) == len(rows)
    assert report["ported_ids"] == [r["id"] for r in rows if r["disposition"] == "PORTED"]
    assert report["meemee_pin"] == MEEMEE_PIN and report["meemee_repo"] == MEEMEE_REPO
    assert report["claire_module"] == CLAIRE_MODULE
    scope = report["scope"]
    assert set(scope) == {"implemented", "not_implemented", "data_source", "as_of"}


def test_every_ported_target_resolves():
    failures = validate_ported_targets()
    assert failures == [], failures


def test_ported_count_matches_actual_modules():
    report = inventory_report()
    assert report["by_disposition"]["PORTED"] == 15
    assert report["by_disposition"]["PORTED"] + report["by_disposition"]["ALREADY_PRESENT"] \
        + report["by_disposition"]["REJECTED"] + report["by_disposition"]["DEFERRED"] \
        == report["total_capabilities"]
