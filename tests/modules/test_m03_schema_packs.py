import copy
import json
from datetime import datetime, timezone

import pytest

from app.modules.m03_grant_writer.schema_packs import (
    PackInvalid, anchors, catalog, check, diff, get_pack, load_all, validate, verify_source,
)

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
GOOD_PS = "Intellectual Merit\nI built a microscope...\n\nBroader Impacts\nI tutor ...\nReferences: Smith, J Neurosci 2024"
GOOD_RP = "Intellectual Merit\nAim 1...\n\nBroader Impacts\nOpen tools...\n"


def grfp():
    return get_pack("NSF", "GRFP")


def test_shipped_pack_is_valid_sourced_and_listed():
    p = grfp()
    assert p["solicitation"] == "NSF 26-526" and p["source_url"].startswith("https://www.nsf.gov/")
    assert all(a.strip() for _, a in anchors(p)) and len(anchors(p)) == 12
    assert catalog()[0]["latest_version"] == "2026-09-24"


def test_clean_submission_is_ready_with_field_deadlines():
    out = check(grfp(), {"field": "Engineering", "documents": {
        "personal_statement": {"pages": 3, "text": GOOD_PS}, "research_plan": {"pages": 2, "text": GOOD_RP},
        "transcripts": {"attached": True}}, "counts": {"reference_writers": 3}}, now=NOW)
    assert out["ready"] is True and out["issues"] == []
    assert [d["id"] for d in out["deadlines"]] == ["reference_letters", "application_engineering"]
    eng = out["deadlines"][1]
    assert eng["at"] == "2026-10-22T20:00:00-04:00" and eng["passed"] is False


def test_rule_violations_cite_their_source_sentence():
    out = check(grfp(), {"field": "Life Sciences", "documents": {
        "personal_statement": {"pages": 4, "text": "Intellectual Merit and Broader Impacts\nSee https://doi.org/10.1000/x"},
        "research_plan": {"pages": 2, "text": GOOD_RP}}, "counts": {"reference_writers": 2}}, now=NOW)
    codes = sorted(i["code"] for i in out["issues"])
    assert codes == ["missing_document", "missing_heading", "missing_heading", "over_page_limit", "too_few", "url_or_doi_in_text"]
    over = next(i for i in out["issues"] if i["code"] == "over_page_limit")
    assert "three (3) pages" in over["rule_source"] and over["version"] == "2026-09-24"


def test_passed_deadline_and_unknown_field():
    late = datetime(2026, 10, 20, 1, tzinfo=timezone.utc)  # Oct 19 9pm ET: Life Sciences closed at 8pm
    out = check(grfp(), {"field": "Life Sciences", "documents": {}, "counts": {}}, now=late)
    assert {"deadline_passed"} <= {i["code"] for i in out["issues"]}
    assert all(d["passed"] for d in out["deadlines"])
    out = check(grfp(), {"field": "Astrology", "documents": {}, "counts": {}}, now=NOW)
    assert any(w["code"] == "unknown_field" for w in out["warnings"])


def test_amendment_diff_between_versions(tmp_path):
    old = grfp()
    new = copy.deepcopy(old)
    new["version"] = "2026-10-05"; new["supersedes"] = old["version"]
    new["deadlines"][1]["date"] = "2026-10-26"
    new["documents"][1]["max_pages"] = 3
    d = tmp_path / "nsf" / "grfp"; d.mkdir(parents=True)
    for p in (old, new):
        (d / f"{p['version']}.json").write_text(json.dumps(p))
    assert get_pack("nsf", "grfp", base=tmp_path)["version"] == "2026-10-05"
    out = diff(get_pack("nsf", "grfp", "2026-09-24", base=tmp_path), get_pack("nsf", "grfp", base=tmp_path))
    assert out["amended"] is True
    changed = {(c["group"], c["id"]): c["fields"] for c in out["changes"]}
    assert changed[("deadlines", "application_life_sciences")]["date"] == {"old": "2026-10-19", "new": "2026-10-26"}
    assert changed[("documents", "research_plan")]["max_pages"] == {"old": 2, "new": 3}


def test_verify_source_flags_changed_anchor_and_tolerates_markup():
    p = grfp()
    page = "<html>" + "".join(f"<p><strong>{a.split(':')[0]}</strong>{a[len(a.split(':')[0]):]}</p>" for _, a in anchors(p)) + "</html>"
    assert verify_source(p, lambda url: page)["possibly_amended"] is False
    amended = page.replace("October 16", "October 23")
    out = verify_source(p, lambda url: amended)
    assert out["possibly_amended"] and [m["rule"] for m in out["missing"]] == ["deadlines:reference_letters"]


def test_pack_without_anchor_is_rejected():
    p = copy.deepcopy(grfp()); p["documents"][0]["anchor"] = ""
    with pytest.raises(PackInvalid):
        validate(p)


def test_http_catalog_and_check(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m03_grant_writer import routes
    monkeypatch.setenv("ATLAS_ENV", "development")
    app = FastAPI(); app.include_router(routes.router)
    c = TestClient(app)
    assert c.get("/grant-writer/schema-packs").json()[0]["program"] == "GRFP"
    assert c.get("/grant-writer/schema-packs/nsf/nope").status_code == 404
    r = c.post("/grant-writer/schema-packs/nsf/grfp/check", json={"field": "Engineering", "documents": {
        "personal_statement": {"pages": 3, "text": GOOD_PS}}, "counts": {"reference_writers": 3}})
    assert r.status_code == 200 and {i["code"] for i in r.json()["issues"]} >= {"missing_document"}
