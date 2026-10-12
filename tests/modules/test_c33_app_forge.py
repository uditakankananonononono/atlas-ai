"""c33.app_forge tests (row 105): real app generation with virality
mechanics, content calendar, batch forging, autopost refusals."""
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c33 import app_forge  # noqa: E402

NICHE = {"taxonomy": "urban gardening", "audience": "students", "format": "tracker"}
BRAND = {"name": "SproutLab", "tagline": "Grow something real"}


def test_forge_writes_complete_runnable_app(tmp_path):
    out = app_forge.forge(NICHE, BRAND, str(tmp_path))
    page = pathlib.Path(out["files"]["index"]).read_text()
    assert "<!doctype html>" in page.lower()
    for mech in ("navigator.share", "clipboard", "referral", "localStorage",
                 "exportBtn", "ref="):
        assert mech in page
    manifest = json.loads(pathlib.Path(out["files"]["manifest"]).read_text())
    assert manifest["name"].startswith("SproutLab")
    assert pathlib.Path(out["files"]["readme"]).exists()
    assert out["deployed"] is False
    assert set(out["virality_features"]) >= {"web-share-api", "referral-counter",
                                             "interest-capture"}


def test_deterministic_output(tmp_path):
    a = app_forge.forge(NICHE, BRAND, str(tmp_path / "x"))
    b = app_forge.forge(NICHE, BRAND, str(tmp_path / "y"))
    assert a["content_sha"] == b["content_sha"] and a["slug"] == b["slug"]


def test_content_calendar_hook_scored():
    cal = app_forge.content_calendar(NICHE, days=10)
    assert len(cal["days"]) == 10
    assert all(0 < d["hook_score"] <= 1 for d in cal["days"])
    assert {d["hook_type"] for d in cal["days"]}
    assert cal["posted"] is False
    assert "urban gardening" in cal["days"][0]["title"]


def test_batch_cap_and_report(tmp_path):
    niches = [{"taxonomy": "niche%d" % i, "audience": "all", "format": "quiz"}
              for i in range(30)]
    out = app_forge.batch(niches, BRAND, str(tmp_path), cap=12)
    assert out["apps_built"] == 12 and out["requested"] == 30
    dirs = {a["slug"] for a in out["apps"]}
    assert len(dirs) == 12
    for a in out["apps"]:
        assert (pathlib.Path(a["dir"]) / "index.html").exists()


def test_autopost_keys_refused(tmp_path):
    with pytest.raises(ValueError, match="SOCIAL_REFUSED_AUTOPOST"):
        app_forge.forge(NICHE, {"name": "X", "publish": True}, str(tmp_path))


def test_niche_validation():
    with pytest.raises(ValueError, match="SOCIAL_REFUSED"):
        app_forge.forge({"taxonomy": "", "audience": "a", "format": "f"}, BRAND, "/tmp/x")

def test_exact_page_hash_html_escape_and_day_bound(tmp_path):
    import hashlib
    out=app_forge.forge(NICHE,dict(BRAND,tagline='<b>unsafe</b>'),str(tmp_path))
    raw=pathlib.Path(out['files']['index']).read_bytes()
    assert out['content_sha']==hashlib.sha256(raw).hexdigest()[:12]
    assert b'&lt;b&gt;unsafe&lt;/b&gt;' in raw
    with pytest.raises(ValueError):app_forge.content_calendar(NICHE,days=61)
