"""Independent minimized-diagnostic audit. All markers are invented test data."""
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qsl, urlsplit

import pytest

from app.modules.m18_side_hustle_scraper.lane_models import CollectionError, FetchPolicy
from app.modules.m18_side_hustle_scraper.lane_http import HttpError, UrllibHttpClient
from app.modules.m18_side_hustle_scraper.lane_sources import BaseCollector

MARKER = "INVENTED-NONSECRET-M18-CANARY"


@pytest.mark.parametrize("key", ["key", "api_key", "apikey", "token", "access_token", "KEY", "Api_Key", "ToKeN", "api%5fkey", "%61ccess_token"])
def test_url_enumerated_names_and_single_decode(key):
    err = CollectionError("audit", f"https://h.test/p?{key}={MARKER}&q=a%20b&q=c", "r", 403)
    assert MARKER not in err.url
    pairs = parse_qsl(urlsplit(err.url).query)
    assert pairs == []  # no query values or keys retained
    assert err.status == 403


@pytest.mark.parametrize("authority", ["user:pass@h.test:8443", "user@h.test", "user:pass@[2001:db8::1]:8080", "user:pass@h.test:notaport"])
def test_url_authority_preserved_without_userinfo(authority):
    err = CollectionError("audit", f"https://{authority}/p?key={MARKER}", "r")
    assert err.url == "[REDACTED]" if authority.endswith("notaport") else urlsplit(err.url).netloc == authority.rsplit("@", 1)[-1]
    assert MARKER not in err.url


def test_duplicate_sensitive_keys_blank_values_and_idempotence():
    err = CollectionError("audit", f"https://h.test/?key={MARKER}&key=&KEY={MARKER}&x=1", f"token={MARKER}&x=1")
    assert err.url == "https://h.test/"
    again = CollectionError("audit", err.url, err.reason)
    assert (again.url, again.reason) == (err.url, err.reason)


@pytest.mark.parametrize("reason", [f"key={MARKER}", f"API_KEY={MARKER}&q=a", f"failed https://u:{MARKER}@h.test/p", f"token={MARKER} trailing"])
def test_reason_enumerated_shapes(reason):
    err = CollectionError("audit", "https://h.test", reason)
    assert MARKER not in err.reason


@pytest.mark.parametrize("reason", [f"key = {MARKER}", f"Authorization: Bearer {MARKER}", f"api%5fkey={MARKER}", f"https://{MARKER}@h.test", f'{{"token": "{MARKER}"}}', f"token=first {MARKER}"])
def test_former_reason_residual_is_removed(reason):
    err = CollectionError("audit", "https://h.test", reason)
    assert MARKER not in err.reason


@pytest.mark.parametrize("url", [f"https://h.test/#token={MARKER}", f"https://h.test/?api%255fkey={MARKER}", f"https://h.test/?password={MARKER}", f"https://h.test/path/{MARKER}"])
def test_former_url_residual_is_removed(url):
    assert MARKER not in CollectionError("audit", url, "r").url


def test_url_origin_minimization_and_serialization():
    url = "https://h.test/p?q=hello%20world&&empty=&flag#section"
    err = CollectionError("audit", url, "not found", 404)
    assert err.url == "https://h.test/"
    encoded = json.dumps(asdict(err), default=str)
    assert json.loads(encoded)["url"] == "https://h.test/"


def test_malformed_ipv6_records_redacted_instead_of_raising():
    assert CollectionError("audit", "https://[broken/?key=" + MARKER, "r").url == "[REDACTED]"


def test_http_error_itself_is_minimized():
    exc = HttpError(f"https://h.test/?key={MARKER}", 403, f"token={MARKER}")
    assert MARKER not in str(exc) + exc.url + exc.reason
    recorded = CollectionError("audit", exc.url, exc.reason, exc.status)
    assert MARKER not in recorded.url and MARKER not in recorded.reason


def test_arbitrary_source_field_is_removed():
    assert MARKER not in CollectionError(MARKER, "https://h.test", "r").source


def test_real_loopback_transport_fetches_original_url_then_scrubs_record():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(403, f"denied token={MARKER}")
            self.end_headers()
            self.wfile.write(b"denied")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/failure?key={MARKER}&q=a"
        collector = BaseCollector(UrllibHttpClient(), policy=FetchPolicy(max_retries=0))
        response, error = collector._get(url)
        assert response is None and error.status == 403
        assert requests == [f"/failure?key={MARKER}&q=a"]
        serialized = json.dumps(asdict(error), default=str)
        assert MARKER not in serialized
        assert "REDACTED" in serialized
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()


@pytest.mark.parametrize("code", ["circuit_open", "retries_exhausted", "domain_not_allowed", "robots_disallows", "robots_unreachable_denied_fail_closed"])
def test_fixed_reason_codes_are_retained(code):
    assert CollectionError("public_web", "https://h.test/a", code).reason == code


@pytest.mark.parametrize("url", ["https://[broken", "https://h.test:bad/", "not-a-url", "file:///tmp/secret", "https://h.test:999999/"])
def test_malformed_or_non_http_url_is_safe(url):
    assert CollectionError("audit", url, "r").url == "[REDACTED]"


def test_transport_error_has_no_raw_exception_chain():
    import traceback
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(403, f"Bearer {MARKER}")
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/failure?password={MARKER}"
        with pytest.raises(HttpError) as captured:
            UrllibHttpClient().fetch(url, policy=FetchPolicy())
        exc = captured.value
        assert exc.__context__ is None and exc.__cause__ is None
        assert MARKER not in "".join(traceback.format_exception_only(type(exc), exc))
        assert MARKER not in repr(vars(exc))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_record_size_bounds_preserved_on_new_main_base():
    from app.modules.m18_side_hustle_scraper.lane_models import FAILURE_RECORD_MAX_CHARS
    err = CollectionError(MARKER * 10000, "https://h.test/" + MARKER * 10000, MARKER * 10000)
    assert err.source == err.url == err.reason == "[REDACTED]"
    assert max(map(len, (err.source, err.url, err.reason))) <= FAILURE_RECORD_MAX_CHARS
