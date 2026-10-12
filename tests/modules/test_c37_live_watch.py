"""c37.live_watch tests: live fetch of RSS/Atom through a hermetic local
server, items fed into the real public_record diff."""
import functools
import http.server
import pathlib
import sys
import threading

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c30 import public_http  # noqa: E402
from app.modules.c37 import live_watch, public_record  # noqa: E402

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<title>DARPA News</title>
<item><title>Quantum Sensors Program</title>
<link>https://www.darpa.mil/program/quantum-sensors</link>
<guid>darpa-1</guid><pubDate>Mon, 12 Oct 2026 00:00:00 GMT</pubDate>
<description>New public quantum sensing program.</description></item>
<item><title>Fusion Energy Initiative</title>
<link>https://www.darpa.mil/program/fusion</link>
<guid>darpa-2</guid><pubDate>Sun, 11 Oct 2026 00:00:00 GMT</pubDate>
<description>Public fusion energy research.</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>ARPA-E</title>
<entry><title>Grid Storage</title><id>arpae-1</id>
<link rel="alternate" href="https://arpa-e.energy.gov/grid-storage"/>
<updated>2026-10-12T00:00:00Z</updated><summary>Public grid storage program.</summary></entry>
</feed>"""


@pytest.fixture
def server(tmp_path):
    (tmp_path / "feed.rss").write_text(RSS)
    (tmp_path / "feed.atom").write_text(ATOM)
    (tmp_path / "bad.xml").write_text("<html>not a feed</html>")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def fetcher():
    return public_http.Fetcher(["127.0.0.1"], allow_http=True, min_interval_s=0)


def test_rss_live_fetch_and_diff(server):
    url = "http://127.0.0.1:%d/feed.rss" % server.server_address[1]
    report = live_watch.run({"fetch_date": "2026-10-12", "feeds": {"darpa": url}},
                            fetcher=fetcher(),
                            feed_hosts={"darpa": ("127.0.0.1",)})
    ids = {i["id"] for i in report["items"]}
    assert ids == {"darpa-1", "darpa-2"}
    assert all(i["source_url"].startswith("https://www.darpa.mil/") for i in report["items"])
    assert report["live_fetch"]["feeds"][0]["status"] == 200
    assert report["items"][0]["novelty"] >= report["items"][-1]["novelty"]


def test_atom_feed(server):
    url = "http://127.0.0.1:%d/feed.atom" % server.server_address[1]
    report = live_watch.run({"fetch_date": "2026-10-12", "feeds": {"arpa-e": url}},
                            fetcher=fetcher(), feed_hosts={"arpa-e": ("127.0.0.1",)})
    assert [i["id"] for i in report["items"]] == ["arpae-1"]


def test_second_run_diffs_against_seen(server):
    url = "http://127.0.0.1:%d/feed.rss" % server.server_address[1]
    watcher = public_record.Watcher()
    f = fetcher()
    kw = dict(fetcher=f, watcher=watcher, feed_hosts={"darpa": ("127.0.0.1",)})
    first = live_watch.run({"fetch_date": "2026-10-12", "feeds": {"darpa": url}}, **kw)
    second = live_watch.run({"fetch_date": "2026-10-13", "feeds": {"darpa": url}}, **kw)
    assert len(first["items"]) == 2
    assert second["items"] == [] or all(i["status"] == "changed" for i in second["items"])


def test_unknown_source_refused(server):
    with pytest.raises(ValueError, match="INTEL_REFUSED_NOSOURCE"):
        live_watch.run({"fetch_date": "2026-10-12",
                        "feeds": {"cia-crest-x": "http://127.0.0.1/x"}}, fetcher=fetcher())


def test_feed_host_off_registry_refused(server):
    with pytest.raises(ValueError, match="INTEL_REFUSED_NOSOURCE:feed-host"):
        live_watch.run({"fetch_date": "2026-10-12",
                        "feeds": {"darpa": "https://evil.example.com/feed"}},
                       fetcher=fetcher())


def test_unparsable_feed_refused(server):
    url = "http://127.0.0.1:%d/bad.xml" % server.server_address[1]
    with pytest.raises(ValueError, match="INTEL_REFUSED_FETCH_PARSE"):
        live_watch.run({"fetch_date": "2026-10-12", "feeds": {"darpa": url}},
                       fetcher=fetcher(), feed_hosts={"darpa": ("127.0.0.1",)})


def test_classified_items_still_refused_by_diff(server, tmp_path):
    poisoned = RSS.replace("Quantum Sensors Program", "TOP SECRET Quantum Program")
    (tmp_path / "poison.rss").write_text(poisoned)
    url = "http://127.0.0.1:%d/poison.rss" % server.server_address[1]
    report = live_watch.run({"fetch_date": "2026-10-12", "feeds": {"darpa": url}},
                            fetcher=fetcher(), feed_hosts={"darpa": ("127.0.0.1",)})
    assert any(r["code"] == "INTEL_REFUSED_CLASSIFIED" for r in report["refused"])
    assert {i["id"] for i in report["items"]} == {"darpa-2"}

def test_empty_rss_refuses_not_empty_success():
    from app.modules.c37.live_watch import parse_feed
    with pytest.raises(ValueError):parse_feed(b'<rss><channel></channel></rss>')
