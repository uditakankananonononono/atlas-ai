"""m23.common_app_preview tests (row 101): real ZIP parsing, Common App
constraint validation, full preview rendering, path-traversal refusal."""
import io
import json
import pathlib
import sys
import zipfile

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.m23_study_abroad import common_app_preview as cp  # noqa: E402

PROFILE = {"legal_name": "Test Student", "birth_date": "2008-04-02",
           "email": "t@example.com", "school": "Test School", "graduation_year": 2027}
ACT = {"position": "Founder", "organization": "Robotics Club",
       "description": "Built and competed robots regionally", "hours_per_week": 4,
       "weeks_per_year": 36, "grades": "9-12"}
ESSAY = ("I learned to weld at my grandfather's shop. " * 40).strip()


def make_zip(profile=PROFILE, activities=(ACT,), essay=ESSAY, extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        if profile is not None:
            z.writestr("profile.json", json.dumps(profile))
        for i, a in enumerate(activities):
            z.writestr("activities/a%d.json" % i, json.dumps(a))
        if essay is not None:
            z.writestr("essays/personal.md", essay)
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return buf.getvalue()


def test_full_preview_complete():
    p = cp.read_portfolio(make_zip())
    r = cp.render_preview(p)
    assert r["complete"] is True and r["violations"] == []
    md = r["markdown"]
    assert "## Profile" in md and "## Activities" in md and "## Essays" in md
    assert "Robotics Club" in md and ESSAY[:40] in md
    assert r["submitted"] is False


def test_missing_profile_field_flagged():
    prof = dict(PROFILE)
    del prof["birth_date"]
    r = cp.render_preview(cp.read_portfolio(make_zip(profile=prof)))
    assert r["complete"] is False
    assert any(v["field"] == "birth_date" and v["issue"] == "missing"
               for v in r["violations"])


def test_activity_limits_enforced():
    acts = [dict(ACT, description="x" * 200)] * 11
    r = cp.render_preview(cp.read_portfolio(make_zip(activities=acts)))
    issues = {(v["section"], v["issue"]) for v in r["violations"]}
    assert ("activities", "exceeds-10") in issues
    assert ("activities", "over-150-chars") in issues


def test_essay_word_limit_enforced():
    r = cp.render_preview(cp.read_portfolio(make_zip(essay="word " * 700)))
    assert any(v["issue"] == "over-650-words" for v in r["violations"])


def test_missing_profile_json_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("essays/e.md", "hi there")
    with pytest.raises(ValueError, match="COMMONAPP_REFUSED_MISSING:profile.json"):
        cp.read_portfolio(buf.getvalue())


def test_path_traversal_refused():
    with pytest.raises(ValueError, match="COMMONAPP_REFUSED_PATH"):
        cp.read_portfolio(make_zip(extra={"../evil.txt": "x"}))


def test_bad_zip_refused():
    with pytest.raises(ValueError, match="COMMONAPP_REFUSED_BAD_ZIP"):
        cp.read_portfolio(b"not a zip at all")


def test_unknown_members_reported_not_executed():
    p = cp.read_portfolio(make_zip(extra={"notes/readme.txt": "hello"}))
    assert "notes/readme.txt" in p["unknown_members"]

def test_six_honors_exceed_published_local_constraint():
    p=cp.read_portfolio(make_zip());p['honors']=[{'title':'Honor'}]*6
    assert any(v['section']=='honors' and v['issue']=='exceeds-5' for v in cp.validate(p))
