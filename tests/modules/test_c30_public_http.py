"""c30.public_http tests: hermetic local-server fetches, fail-closed robots,
manual redirect validation, public-IP checks, conditional GET."""
import functools
import http.server
import pathlib
import sys
import threading

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c30 import public_http  # noqa: E402


class Server:
    def __init__(self, directory):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(directory))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.host = "127.0.0.1"
        self.port = self.httpd.server_address[1]

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class AdversarialHandler(http.server.BaseHTTPRequestHandler):
    """Configurable handler for redirect/robots/304 attacks."""
    routes = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404)
            return
        kind = route[0]
        if kind == "ok":
            body = route[1].encode()
            self.send_response(200)
            if len(route) > 2 and route[2]:
                self.send_header("ETag", route[2])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif kind == "redirect":
            self.send_response(302)
            self.send_header("Location", route[1])
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif kind == "status":
            self.send_error(route[1])
        elif kind == "etag-check":
            if self.headers.get("If-None-Match") == route[1]:
                self.send_response(304)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                body = b"fresh"
                self.send_response(200)
                self.send_header("ETag", route[1])
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)


@pytest.fixture
def adv_server():
    AdversarialHandler.routes = {}
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), AdversarialHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd, AdversarialHandler.routes
    httpd.shutdown()
    httpd.server_close()


def adv_url(httpd, path):
    return "http://127.0.0.1:%d%s" % (httpd.server_address[1], path)


@pytest.fixture
def server(tmp_path):
    (tmp_path / "page.html").write_text("<html>hello</html>")
    srv = Server(tmp_path)
    yield srv
    srv.stop()


def fetcher(**kw):
    kw.setdefault("allow_http", True)
    kw.setdefault("min_interval_s", 0)
    return public_http.Fetcher(["127.0.0.1"], **kw)


# --- baseline behavior ----------------------------------------------------

def test_fetch_ok(server):
    out = fetcher().fetch(server.url("/page.html"))
    assert out["status"] == 200 and b"hello" in out["body"] and not out["not_modified"]


def test_host_not_allowed(server):
    with pytest.raises(ValueError, match="HTTP_REFUSED_HOST_NOT_ALLOWED"):
        public_http.Fetcher(["example.com"], allow_http=True).fetch(server.url("/page.html"))


def test_nonhttps_refused(server):
    with pytest.raises(ValueError, match="HTTP_REFUSED_NONHTTPS"):
        public_http.Fetcher(["127.0.0.1"]).fetch(server.url("/page.html"))


def test_userinfo_refused():
    with pytest.raises(ValueError, match="HTTP_REFUSED_CREDENTIALS_IN_URL"):
        fetcher().fetch("http://user:pw@127.0.0.1/x")


def test_404_surfaces_status(server):
    with pytest.raises(ValueError, match="HTTP_REFUSED_STATUS:404"):
        fetcher().fetch(server.url("/missing"))


def test_too_large(server, tmp_path):
    (tmp_path / "big.bin").write_bytes(b"x" * 3000)
    with pytest.raises(ValueError, match="HTTP_REFUSED_TOO_LARGE"):
        fetcher(max_bytes=100).fetch(server.url("/big.bin"))


def test_throttle_sleeps(server):
    sleeps = []
    fake_clock = [100.0]

    def clock():
        return fake_clock[0]

    def sleeper(s):
        sleeps.append(s)
        fake_clock[0] += s

    f = fetcher(min_interval_s=5.0, clock=clock, sleeper=sleeper)
    f._throttle("127.0.0.1")
    f._throttle("127.0.0.1")
    assert sleeps == [5.0]


def test_conditional_get_304(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/feed"] = ("etag-check", '"v1"')
    f = fetcher()
    first = f.fetch(adv_url(httpd, "/feed"))
    assert first["status"] == 200 and first["etag"] == '"v1"'
    second = f.fetch(adv_url(httpd, "/feed"))
    assert second["status"] == 304 and second["not_modified"] is True
    assert second["body"] == b""


# --- robots: fail CLOSED ---------------------------------------------------

def test_robots_disallow_denies(server, tmp_path):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /page.html\n")
    with pytest.raises(ValueError, match="HTTP_REFUSED_ROBOTS"):
        fetcher().fetch(server.url("/page.html"))


def test_robots_404_means_no_restriction(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/page"] = ("ok", "hi")
    out = fetcher().fetch(adv_url(httpd, "/page"))
    assert out["status"] == 200


def test_robots_410_means_no_restriction(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 410)
    routes["/page"] = ("ok", "hi")
    assert fetcher().fetch(adv_url(httpd, "/page"))["status"] == 200


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_robots_error_denies_fail_closed(adv_server, code):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", code)
    routes["/page"] = ("ok", "hi")
    with pytest.raises(ValueError, match="HTTP_REFUSED_ROBOTS"):
        fetcher().fetch(adv_url(httpd, "/page"))


def test_robots_dns_failure_denies():
    f = public_http.Fetcher(["nonexistent.invalid"], allow_http=True,
                            min_interval_s=0, timeout_s=3)
    with pytest.raises(ValueError):
        f.fetch("http://nonexistent.invalid/page")


# --- redirects: validated before contact, capped ---------------------------

def test_same_host_redirect_followed(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/old"] = ("redirect", "/new")
    routes["/new"] = ("ok", "landed")
    out = fetcher().fetch(adv_url(httpd, "/old"))
    assert out["status"] == 200 and b"landed" in out["body"]


def test_off_list_redirect_refused_before_contact(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/bait"] = ("redirect", "http://169.254.169.254/latest/meta-data")
    f = fetcher()
    with pytest.raises(ValueError, match="HTTP_REFUSED_HOST_NOT_ALLOWED"):
        f.fetch(adv_url(httpd, "/bait"))
    # the metadata endpoint was never contacted: only robots+bait hits happened
    assert f.fetches == 0


def test_redirect_loop_capped(adv_server):
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/loop"] = ("redirect", "/loop")
    with pytest.raises(ValueError, match="HTTP_REFUSED_REDIRECTS"):
        fetcher(max_redirects=3).fetch(adv_url(httpd, "/loop"))


def test_https_redirect_target_required(adv_server):
    # production fetcher: redirect to http:// target is refused (non-https)
    httpd, routes = adv_server
    routes["/robots.txt"] = ("status", 404)
    routes["/downgrade"] = ("redirect", "http://127.0.0.1/weak")
    prod = public_http.Fetcher(["127.0.0.1"], min_interval_s=0)
    with pytest.raises(ValueError):  # NONHTTPS or NONPUBLIC_IP, both refused
        prod.fetch("https://127.0.0.1/downgrade")


# --- public-IP validation ---------------------------------------------------

def test_loopback_refused_in_production():
    prod = public_http.Fetcher(["127.0.0.1"], min_interval_s=0)
    with pytest.raises(ValueError, match="HTTP_REFUSED_NONPUBLIC_IP"):
        prod.fetch("https://127.0.0.1/")


def test_private_ip_literal_refused_in_production():
    prod = public_http.Fetcher(["192.168.1.1"], min_interval_s=0)
    with pytest.raises(ValueError, match="HTTP_REFUSED_NONPUBLIC_IP"):
        prod.fetch("https://192.168.1.1/")


def test_allow_http_seam_permits_localhost(server):
    # the hermetic-test seam explicitly relaxes the public-IP check
    out = fetcher().fetch(server.url("/page.html"))
    assert out["status"] == 200
