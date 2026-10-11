"""S6.3 / c37.public_record tests. Hermetic, stdlib unittest, no network."""
import importlib.util, json, pathlib, socket, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/c37/public_record.py"
DOC = ROOT / "docs/C37_PUBLIC_RECORD_CONTRACT.md"


def load(source=None, name="c37_pr"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


def good(i="a1", **kw):
    d = {"id": i, "title": "Quantum sensing program", "url": "https://www.darpa.mil/program/q1",
         "summary": "Public program page.", "published": "2026-10-01"}
    d.update(kw)
    return d


def body(sources, date="2026-10-11"):
    return {"fetch_date": date, "sources": sources}


def refusal(m, b):
    try:
        m.Watcher().run(b)
    except ValueError as e:
        return str(e)
    return None


def item_codes(m, items, src="darpa"):
    r = m.Watcher().run(body({src: items}))
    return [x["code"] for x in r["refused"]], r


class Core(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def test_report_has_source_url_fetch_date_and_plain_limits(self):
        r = self.m.Watcher().run(body({"darpa": [good()]}))
        it = r["items"][0]
        self.assertEqual((it["source_url"], it["fetch_date"]), ("https://www.darpa.mil/program/q1", "2026-10-11"))
        self.assertIn("cannot see top secret", r["statement"])
        self.assertIn("Public records only", r["limits"][0])
        self.assertIn("not all of government", r["limits"][1])

    def test_planted_classified_marker_is_refused(self):
        codes, r = item_codes(self.m, [good("ok"), good("bad", title="TOP SECRET//NOFORN program"),
                                       good("bad2", summary="marked TS//SCI", url="https://www.darpa.mil/x"),
                                       good("bad3", classification="SECRET")])
        self.assertEqual(codes, ["INTEL_REFUSED_CLASSIFIED"] * 3)
        self.assertEqual([i["id"] for i in r["items"]], ["ok"])
        self.assertNotIn("NOFORN", str(r["refused"]))  # content is never echoed

    def test_nosource(self):
        for bad in (good(url=None), good(url="http://www.darpa.mil/x"), good(url="https://evil.example/x"),
                    good(url="https://user:pw@www.darpa.mil/x")):
            codes, _ = item_codes(self.m, [bad])
            self.assertEqual(codes, ["INTEL_REFUSED_NOSOURCE"], bad)
        r = self.m.Watcher().run(body({"darpa": [good()], "not-a-source": [good()]}))
        self.assertEqual(r["refused"][0]["code"], "INTEL_REFUSED_NOSOURCE")

    def test_private(self):
        for bad in (good(ssn="123-45-6789"), good(summary="call 555-123-4567"), good(summary="mail a.b@example.com"),
                    good(home_address="1 Main St")):
            codes, _ = item_codes(self.m, [bad])
            self.assertEqual(codes, ["INTEL_REFUSED_PRIVATE"], bad)

    def test_request_level_classified_for_auth_and_probing(self):
        for key in ("password", "token", "cookie", "login", "probe", "authorization", "Password"):
            for where in ("item", "nested"):
                it = good()
                if where == "item":
                    it[key] = "x"
                    b = body({"darpa": [it]})
                else:
                    b = body({"darpa": [it]})
                    b["sources"]["darpa"][0]["summary"] = "ok"
                    b["sources"]["darpa"].append({"id": "n", key: {"k": 1}})
                self.assertEqual(refusal(self.m, b), "INTEL_REFUSED_CLASSIFIED", (key, where))


    def _dump(self, w, r):
        return json.dumps(r) + repr(w.seen) + repr(w.topic_counts)

    def test_private_id_refused_and_not_leaked(self):
        w = self.m.Watcher()
        r = w.run(body({"cia-crest": [{"id": "person@example.com", "title": "public research",
                                       "url": "https://www.cia.gov/x"}]}))
        self.assertEqual([x["code"] for x in r["refused"]], ["INTEL_REFUSED_PRIVATE"])
        self.assertEqual(r["items"], [])
        self.assertNotIn("person@example.com", self._dump(w, r))
        self.assertNotIn("example.com", self._dump(w, r))

    def test_private_in_url_published_refused(self):
        for bad in (good(url="https://www.darpa.mil/u/a@b.com"), good(published="ssn 123-45-6789")):
            codes, r = item_codes(self.m, [bad])
            self.assertEqual(codes, ["INTEL_REFUSED_PRIVATE"])

    def test_classified_id_not_echoed(self):
        w = self.m.Watcher()
        r = w.run(body({"darpa": [good(i="TOP SECRET//NOFORN payload")]}))
        self.assertEqual([x["code"] for x in r["refused"]], ["INTEL_REFUSED_CLASSIFIED"])
        d = self._dump(w, r)
        for leak in ("TOP SECRET", "NOFORN", "payload"):
            self.assertNotIn(leak, d)
        self.assertEqual(r["refused"][0]["item_ref"], "darpa#0")
        self.assertNotIn("item_id", r["refused"][0])

    def test_unknown_source_key_not_echoed(self):
        w = self.m.Watcher()
        r = w.run(body({"darpa": [good()], "TOP SECRET a@b.com": [good()]}))
        self.assertNotIn("TOP SECRET", self._dump(w, r))
        self.assertNotIn("a@b.com", self._dump(w, r))
        self.assertEqual(r["refused"][0]["code"], "INTEL_REFUSED_NOSOURCE")

    def test_classified_in_url_refused(self):
        codes, r = item_codes(self.m, [good(url="https://www.darpa.mil/top-secret"),
                                       good("j", url="https://www.darpa.mil/TOP%20SECRET//x"),
                                       good("k", url="https://www.darpa.mil/NOFORN")])
        self.assertEqual(codes, ["INTEL_REFUSED_CLASSIFIED"] * 3)

    def test_fetch_date_must_be_real_calendar_date(self):
        for d in ("2026-99-99", "2026-02-30", "2026-13-01", "0000-01-01", "2026-1-1"):
            self.assertEqual(refusal(self.m, body({"darpa": [good()]}, date=d)), "INTEL_REFUSED_BAD_TYPE:fetch_date", d)
        self.assertIsNone(refusal(self.m, body({"darpa": [good()]}, date="2028-02-29")))

    def test_malformed_urls_are_nosource_not_raw_valueerror(self):
        for u in ("https://[", "https://[::1", "https://a b/", "https://www.darpa.mil:99999/x", "https://www.darpa.mil:8443/x", "https://", "//", ""):
            codes, _ = item_codes(self.m, [good(url=u)])
            self.assertEqual(codes, ["INTEL_REFUSED_NOSOURCE"], u)

    def test_diff_new_changed_unchanged(self):
        w = self.m.Watcher()
        self.assertEqual([i["status"] for i in w.run(body({"darpa": [good("a"), good("b", title="Fusion reactor")]}))["items"]],
                         ["new", "new"])
        r2 = w.run(body({"darpa": [good("a"), good("b", title="Fusion reactor", summary="updated")]}))
        self.assertEqual([(i["id"], i["status"]) for i in r2["items"]], [("b", "changed")])
        self.assertEqual(w.run(body({"darpa": [good("a")]}))["items"], [])
        self.assertIs(w.report(), w.last_report)

    def test_refused_item_does_not_enter_diff_state(self):
        w = self.m.Watcher()
        w.run(body({"darpa": [good("x", title="top secret thing")]}))
        self.assertEqual(w.seen, {})

    def test_novelty_rank_rarer_topic_first(self):
        w = self.m.Watcher()
        w.run(body({"darpa": [good("q%d" % i, title="Quantum %d" % i) for i in range(3)]}))
        r = w.run(body({"darpa": [good("q9", title="Quantum again"), good("e1", title="Fusion reactor study")]}))
        self.assertEqual([i["id"] for i in r["items"]], ["e1", "q9"])
        self.assertGreater(r["items"][0]["novelty"], r["items"][1]["novelty"])

    def test_registry_coverage_count_and_no_all_government(self):
        r = self.m.Watcher().run(body({"darpa": [good()], "arpa-e": []}))
        c = r["coverage"]
        self.assertEqual((c["registry_sources"], c["sources_in_run"], c["sources_with_items"]), (10, 2, 1))
        self.assertEqual(len(self.m.REGISTRY_IDS), 10)
        self.assertNotIn("all government", (r["statement"] + " ".join(r["limits"])).replace("not all of government", "").lower())

    def test_report_before_run_refuses_and_routes(self):
        with self.assertRaises(ValueError):
            self.m.Watcher().report()
        self.assertEqual(self.m.ROUTES, (("POST", "/api/v1/c37/public-record/run"),
                                         ("GET", "/api/v1/c37/public-record/report")))
        self.assertTrue(callable(self.m.policy.scope) and callable(self.m.policy.clean_text))

    def test_bad_inputs(self):
        for b in (None, {}, body({}), body({"darpa": [good()]}, date="10/11/2026"), body({"darpa": "x"}),
                  body({"darpa": [{"id": "a", "extra": 1}]})):
            self.assertIsNotNone(refusal(self.m, b), b)

    def test_doc_pins(self):
        t = DOC.read_text()
        self.assertIn('HER-WORDS (15:01:13, verbatim): "keep an eye out for top secret projects, governement stuff too, super elite stuff"', t)
        self.assertIn("## LIMITS", t)
        self.assertIn("Never \"all government\"", t)
        self.assertIn(self.m.HER_WORDS, t)

    def test_no_network(self):
        real = socket.socket
        def boom(*a, **k): raise AssertionError("network used")
        socket.socket = boom
        try:
            self.m.Watcher().run(body({"darpa": [good()]}))
        finally:
            socket.socket = real
        src = SRC.read_text()
        for bad in ("import requests", "import httpx", "urllib.request", "import socket", "subprocess"):
            self.assertNotIn(bad, src)


# ---------------- mutation battery: each refusal must be killed ----------------
def probe_classified_item(m):
    return item_codes(m, [good("b", title="TOP SECRET program")])[0] == ["INTEL_REFUSED_CLASSIFIED"]

def probe_classified_field(m):
    return item_codes(m, [good("b", classification="SECRET")])[0] == ["INTEL_REFUSED_CLASSIFIED"]

def probe_classified_request(m):
    try:
        m._scan_request({"a": [{"password": "x"}]})
    except ValueError as e:
        return str(e) == "INTEL_REFUSED_CLASSIFIED"
    return False

def probe_nosource_http(m):
    return item_codes(m, [good(url="http://www.darpa.mil/x")])[0] == ["INTEL_REFUSED_NOSOURCE"]

def probe_nosource_host(m):
    return item_codes(m, [good(url="https://evil.example/x")])[0] == ["INTEL_REFUSED_NOSOURCE"]

def probe_nosource_missing(m):
    return item_codes(m, [good(url=None)])[0] == ["INTEL_REFUSED_NOSOURCE"]

def probe_nosource_registry(m):
    return m.Watcher().run(body({"darpa": [good()], "zzz": [good()]}))["refused"][0]["code"] == "INTEL_REFUSED_NOSOURCE"

def probe_private_field(m):
    return item_codes(m, [good(ssn="123-45-6789")])[0] == ["INTEL_REFUSED_PRIVATE"]

def probe_private_pattern(m):
    return item_codes(m, [good(summary="x a@b.com")])[0] == ["INTEL_REFUSED_PRIVATE"]

def probe_diff(m):
    w = m.Watcher(); w.run(body({"darpa": [good()]}))
    return w.run(body({"darpa": [good()]}))["items"] == []

def probe_refused_not_stored(m):
    w = m.Watcher(); w.run(body({"darpa": [good("x", title="top secret")]}))
    return w.seen == {}

def probe_no_content_echo(m):
    return "NOFORN" not in str(m.Watcher().run(body({"darpa": [good("x", title="NOFORN")]}))["refused"])

def probe_private_id(m):
    w = m.Watcher()
    r = w.run(body({"cia-crest": [{"id": "person@example.com", "title": "t", "url": "https://www.cia.gov/x"}]}))
    return r["items"] == [] and "person@example.com" not in json.dumps(r) + repr(w.seen)

def probe_classified_id(m):
    r = m.Watcher().run(body({"darpa": [good(i="TOP SECRET//NOFORN payload")]}))
    return "NOFORN" not in json.dumps(r) and r["items"] == []

def probe_unknown_source_echo(m):
    return "SECRETKEY" not in json.dumps(m.Watcher().run(body({"darpa": [good()], "SECRETKEY": [good()]})))

def probe_date(m):
    return refusal(m, body({"darpa": [good()]}, date="2026-99-99")) == "INTEL_REFUSED_BAD_TYPE:fetch_date"

def probe_port(m):
    return item_codes(m, [good(url="https://www.darpa.mil:8443/x")])[0] == ["INTEL_REFUSED_NOSOURCE"]

def probe_malformed_url(m):
    return item_codes(m, [good(url="https://[")])[0] == ["INTEL_REFUSED_NOSOURCE"]

def probe_url_scanned(m):
    return item_codes(m, [good(url="https://www.darpa.mil/u/a@b.com")])[0] == ["INTEL_REFUSED_PRIVATE"]

def probe_statement(m):
    return "cannot see top secret" in m.Watcher().run(body({"darpa": [good()]}))["statement"]

MUTANTS = [
    ("classified regex off", 'r"top[\\s_-]*secret|', 'r"zzzz|', probe_classified_item),
    ("classification field ignored", 'if item.get("classification") not in (None, "", "UNCLASSIFIED", "public"):', 'if False:', probe_classified_field),
    ("request key scan off", "k.strip().lower() in _REQUEST_FORBIDDEN_KEYS", "False", probe_classified_request),
    ("http allowed", 'parts.scheme != "https" or', "False or", probe_nosource_http),
    ("host unchecked", "or host not in _BY_ID[source_id][3]", "", probe_nosource_host),
    ("missing url allowed", "if not isinstance(url, str):\n        return \"NOSOURCE\"", "if not isinstance(url, str):\n        return None", probe_nosource_missing),
    ("unknown source allowed", "if sid not in _BY_ID:", "if False:", probe_nosource_registry),
    ("private fields off", "if any(item.get(f) for f in _PRIVATE_FIELDS):", "if False:", probe_private_field),
    ("private regex off", "if any(isinstance(t, str) and _PRIVATE_RE.search(t) for t in texts):", "if False:", probe_private_pattern),
    ("diff off", "if prev == digest:", "if False:", probe_diff),
    ("refused stored", "iid = policy.clean_text(item.get(\"id\"), PREFIX, \"id\", 256)",
     "iid = policy.clean_text(item.get(\"id\"), PREFIX, \"id\", 256); self.seen[(sid, iid)] = 'x'", probe_refused_not_stored),
    ("content echoed", '"item_ref": "%s#%d" % (sid, pos),',
     '"item_ref": iid, "title": item.get("title"),', probe_no_content_echo),
    ("id echoed as ref", '"item_ref": "%s#%d" % (sid, pos),', '"item_ref": iid,', probe_classified_id),
    ("id not scanned", 'for k in ("id", "title", "summary", "published", "url", "classification")]', 'for k in ("title", "summary")]', probe_private_id),
    ("url not scanned", '"published", "url", "classification")]', '"published", "classification")]', probe_url_scanned),
    ("unknown source echoed", '"unknown-source#%d" % sn', 'str(sid)', probe_unknown_source_echo),
    ("port unchecked", "\\\n            or port not in (None, 443):", ":", probe_port),
    ("calendar date unchecked", "datetime.date.fromisoformat(fetch_date)", "pass", probe_date),
    ("malformed url raw", "except ValueError:  # malformed URL such as \"https://[\"\n        return \"NOSOURCE\"", "except KeyError:\n        return \"NOSOURCE\"", probe_malformed_url),
    ("statement dropped", "cannot see top secret", "can see top secret", probe_statement),
]


class MutationBattery(unittest.TestCase):
    def test_baseline_probes_pass(self):
        m = load()
        for _, _, _, probe in MUTANTS:
            self.assertTrue(probe(m), probe.__name__)

    def test_every_mutant_is_killed(self):
        src = SRC.read_text()
        for n, (label, old, new, probe) in enumerate(MUTANTS):
            self.assertEqual(src.count(old), 1, "mutation anchor not unique: " + label)
            try:
                mutated = load(src.replace(old, new), "c37_mut%d" % n)
                killed = not probe(mutated)
            except Exception:
                killed = True
            self.assertTrue(killed, "SURVIVED: " + label)


if __name__ == "__main__":
    unittest.main()
