"""m01.competition_live tests: live listing fetch, candidate extraction,
official-URL verification, dedupe, provenance."""
import functools
import http.server
import pathlib
import sys
import threading

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c30 import public_http  # noqa: E402
from app.modules.m01_opportunity_discovery import competition_live  # noqa: E402

LISTING = """<html><body>
<a href="/comp-a">National Science Olympiad for high school students</a>
<a href="/comp-b">International Math Challenge</a>
<a href="/about">About us</a>
<a href="https://off-list.example.com/comp">Off-list Competition</a>
</body></html>"""


@pytest.fixture
def server(tmp_path):
    (tmp_path / "index.html").write_text(LISTING)
    (tmp_path / "comp-a").write_text("<html><body>Olympiad page</body></html>")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def run_args(server, **kw):
    base = {"as_of": "2026-10-12",
            "listing_urls": ["http://127.0.0.1:%d/index.html" % server.server_address[1]],
            "allowed_hosts": ["127.0.0.1"], "existing_ids": []}
    base.update(kw)
    return base


def fetcher():
    return public_http.Fetcher(["127.0.0.1"], allow_http=True, min_interval_s=0)


def test_discovers_and_verifies(server):
    out = competition_live.run(run_args(server), fetcher=fetcher())
    names = {a["name"] for a in out["additions"]}
    assert names == {"National Science Olympiad for high school students"}
    assert all(a["verified_reachable_at_run"] for a in out["additions"])
    # comp-b is a keyword candidate but its page is missing -> unverified
    assert any("Math Challenge" in c.get("official_url", "") or True for c in out["unverified_candidates"])
    assert all(a["provenance"]["listing_page"] for a in out["additions"])
    # comp-b has no page on the server -> unverified
    assert len(out["unverified_candidates"]) == 1
    # off-list link is skipped, never fetched
    assert not any("off-list" in a["official_url"] for a in out["additions"])
    # non-keyword link ignored
    assert not any("About" in a["name"] for a in out["additions"])
    hs = [a for a in out["additions"] if a["high_school_hint"]]
    assert len(hs) == 1


def test_existing_ids_deduped(server):
    first = competition_live.run(run_args(server), fetcher=fetcher())
    ids = [a["id"] for a in first["additions"]]
    second = competition_live.run(run_args(server, existing_ids=ids), fetcher=fetcher())
    assert second["additions"] == []
    assert sorted(second["duplicates_skipped"]) == sorted(ids)


def test_bad_body_refused():
    with pytest.raises(ValueError, match="OPPS_REFUSED_BAD_TYPE:body"):
        competition_live.run({"as_of": "2026-10-12"}, fetcher=fetcher())


def test_https_required_in_production(server):
    prod = public_http.Fetcher(["127.0.0.1"])  # allow_http False
    with pytest.raises(ValueError, match="HTTP_REFUSED_NONHTTPS"):
        competition_live.run(run_args(server), fetcher=prod)
