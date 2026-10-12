"""Groups 67-76 tests. Hermetic, stdlib unittest."""
import asyncio, json, os, pathlib, sys, tempfile, unittest, urllib.error
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from app.modules.instinct_doc.g67_76 import (adapters, fleet, feed_ingest, interest_signals,
                                              ideation, application_engine as ae, history_audit, universal_creator)

RSS = b"""<rss><channel><item><title>Grant opens</title><link>http://x/1</link><description>bio grant</description></item>
<item><title>Prize</title><link>http://x/2</link><description>ai prize</description></item></channel></rss>"""


class T(unittest.TestCase):
    def test_cli_adapter_really_runs(self):
        r = adapters.trial({"name": "echo_tool", "kind": "cli", "command": ["/bin/echo"]}, {"args": ["hi"]})
        self.assertTrue(r["passed"]); self.assertEqual(r["result"]["stdout"], "hi\n")

    def test_http_adapter_with_transport(self):
        r = adapters.trial({"name": "api_tool", "kind": "http_json", "url": "https://e.x/a"}, {"q": 1},
                           stub_response={"status": 200, "body": {"a": 1}}, allowed_hosts={"e.x"})
        self.assertTrue(r["passed"]); self.assertEqual(r["result"]["data"], {"a": 1})

    def test_failed_trial_reported(self):
        r = adapters.trial({"name": "bad_tool", "kind": "cli", "command": ["/bin/ls"]}, {"args": ["/nonexistent_zz"]})
        self.assertFalse(r["passed"]); self.assertIn("FAILED", r["owner_notification"])

    def test_refusals(self):
        for spec in ({"name": "x1", "kind": "cli", "command": ["rm"]},
                     {"name": "x2", "kind": "cli", "command": ["/tmp/echo"]},
                     {"name": "x3", "kind": "cli", "command": ["echo"]},
                     {"name": "x4", "kind": "cli", "command": ["python3", "-c", "1"]},
                     {"name": "x5", "kind": "cli", "command": ["/usr/bin/python3", "-c", "1"]},
                     {"name": "paid_t", "kind": "cli", "command": ["/bin/echo"], "paid": True},
                     {"name": "h_t", "kind": "http_json", "url": "http://insecure"},
                     {"name": "h_u", "kind": "http_json", "url": "https://evil.example/x"},
                     {"name": "Bad Name", "kind": "cli", "command": ["/bin/echo"]}):
            with self.assertRaises(ValueError):
                adapters.generate(spec)

    def test_trial_is_out_of_process(self):
        r = adapters.trial({"name": "pid_tool", "kind": "cli", "command": ["/bin/echo"]}, {"args": ["x"]})
        self.assertNotIn("adapter", sys.modules)
        self.assertIn("child process", r["isolation"])

    def test_fleet_1000_measured(self):
        async def w(job):
            await asyncio.sleep(0.05)
            return job["id"]
        r = fleet.run([{"id": "j%d" % i} for i in range(1000)], w)
        self.assertEqual(r["ok"], 1000); self.assertEqual(r["peak_inflight_measured"], 1000)
        self.assertTrue(r["simultaneous_1000_achieved"])

    def test_fleet_non_overlapping_workers_not_claimed(self):
        async def w(job):
            return 1  # never awaits, so workers never overlap
        r = fleet.run([{"id": "j%d" % i} for i in range(1000)], w)
        self.assertEqual(r["peak_inflight_measured"], 1)
        self.assertFalse(r["simultaneous_1000_achieved"])

    def test_fleet_negative_cost_refused(self):
        async def w(job):
            return 1
        for bad in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                fleet.run([{"id": "a", "cost": bad}], w)

    def test_fleet_capped_not_claimed(self):
        async def w(job):
            await asyncio.sleep(0.01)
            return 1
        r = fleet.run([{"id": "j%d" % i} for i in range(50)], w, concurrency=5)
        self.assertEqual(r["peak_inflight_measured"], 5); self.assertFalse(r["simultaneous_1000_achieved"])

    def test_fleet_budget(self):
        async def w(job):
            await asyncio.sleep(0.01)
            return 1
        r = fleet.run([{"id": "j%d" % i, "cost": 2} for i in range(10)], w, concurrency=10, budget=6)
        self.assertEqual(r["ok"], 3); self.assertEqual(r["skipped_budget"], 7)

    def test_ingest_dedupe_resume_export(self):
        s = feed_ingest.Store()
        def f(u):
            if u.endswith("feed"):
                return RSS
            raise urllib.error.HTTPError(u, 404, "nf", {}, None)
        a = feed_ingest.ingest(["http://h/feed"], s, f)
        self.assertEqual(a["new"], 2)
        b = feed_ingest.ingest(["http://h/feed"], s, f)
        self.assertEqual(b["feeds"]["http://h/feed"], "already_done")
        c = feed_ingest.ingest(["http://h/feed"], s, f, skip_done=False)
        self.assertEqual((c["new"], c["dup"]), (0, 2))
        p = os.path.join(tempfile.mkdtemp(), "o.jsonl")
        self.assertEqual(s.export_jsonl(p), 2)
        self.assertIn("text", json.loads(open(p).readline()))

    def test_ingest_robots(self):
        s = feed_ingest.Store()
        f = lambda u: b"User-agent: *\nDisallow: /" if u.endswith("robots.txt") else RSS
        self.assertEqual(feed_ingest.ingest(["http://h/feed"], s, f)["feeds"]["http://h/feed"], "blocked_by_robots")

    def test_robots_status_codes(self):
        for code, blocked in ((404, False), (410, False), (401, True), (403, True), (429, True), (500, True)):
            def f(u, code=code):
                if u.endswith("robots.txt"):
                    raise urllib.error.HTTPError(u, code, "x", {}, None)
                return RSS
            r = feed_ingest.ingest(["http://h/feed"], feed_ingest.Store(), f)["feeds"]["http://h/feed"]
            self.assertEqual(r == "blocked_by_robots", blocked, code)

    def test_default_fetch_url_boundary(self):
        for u in ("http://example.com/f", "https://127.0.0.1/f", "https://localhost/f",
                  "https://10.0.0.5/f", "https://169.254.169.254/latest", "https://[::1]/f",
                  "ftp://example.com/f", "file:///etc/passwd"):
            with self.assertRaises(ValueError, msg=u):
                feed_ingest.default_fetch(u)

    def test_redirect_handler_refuses_other_host_and_private(self):
        import urllib.request
        h = feed_ingest._SameHostRedirect("example.com")
        req = urllib.request.Request("https://example.com/a")
        for target in ("https://127.0.0.1/x", "http://example.com/x", "https://169.254.169.254/x"):
            with self.assertRaises(ValueError):
                h.redirect_request(req, None, 302, "Found", {}, target)

    def test_robots_fetch_error_denies(self):
        s = feed_ingest.Store()
        def f(u):
            if u.endswith("robots.txt"):
                raise OSError("down")
            return RSS
        self.assertEqual(feed_ingest.ingest(["http://h/feed"], s, f)["feeds"]["http://h/feed"], "blocked_by_robots")
        def g(u):
            if u.endswith("robots.txt"):
                raise urllib.error.HTTPError(u, 503, "x", {}, None)
            return RSS
        self.assertEqual(feed_ingest.ingest(["http://h/feed"], s, g)["feeds"]["http://h/feed"], "blocked_by_robots")

    def test_instagram_empty_and_list(self):
        self.assertEqual(interest_signals.from_instagram_likes("[]"), [])
        self.assertEqual(interest_signals.from_instagram_likes("{}"), [])
        self.assertEqual(len(interest_signals.from_instagram_likes('[{"title": "x"}, 5]')), 1)

    def test_signals(self):
        sig = interest_signals.from_starred_gmail([
            {"labelIds": ["STARRED"], "subject": "Genomics scholarship", "snippet": "genomics deadline"},
            {"labelIds": ["INBOX"], "subject": "Sale", "snippet": "shoes"}])
        sig += interest_signals.from_linkedin_csv("Date,Link,Type\n1,http://l/genomics-lab,LIKE\n")
        sig += interest_signals.from_instagram_likes(json.dumps({"likes_media_likes": [{"title": "robotics", "string_list_data": [{"value": "robotics"}]}]}))
        top = interest_signals.rank(sig)
        self.assertEqual(top[0]["topic"], "genomics")
        self.assertEqual(top, interest_signals.rank(list(reversed(sig))))  # order independent
        self.assertNotIn("shoes", [t["topic"] for t in top])
        self.assertIn("robotics", [t["topic"] for t in top])

    def test_ideation_prefers_rare_pairs(self):
        docs = ["genomics protein"] * 5 + ["robotics arm"] * 5 + ["genomics robotics"] * 1 + ["protein arm"]
        ideas = ideation.generate(docs, ["genomics", "robotics", "protein", "arm"], k=3)
        self.assertTrue(all("ticket" in i for i in ideas))
        self.assertLessEqual(ideas[0]["cooccurrence"], 1)

    def test_application_flow(self):
        txt = "Deadline: 2026-12-20\nApplication fee: $25\nOpen to grades 11-12\nEssay 1: Why science? (50 words)\n"
        o = ae.parse_opportunity(txt)
        self.assertEqual(o["deadline"], date(2026, 12, 20)); self.assertEqual(o["fee"], 25.0)
        m = ae.match(o, {"grade": 12}, today=date(2026, 10, 12))
        self.assertTrue(m["eligible"]); self.assertEqual(m["needs_owner"], ["fee approval: 25.00 $"])
        self.assertFalse(ae.match(o, {"grade": 9}, today=date(2026, 10, 12))["eligible"])
        self.assertFalse(ae.match(o, {"grade": 12}, today=date(2027, 1, 1))["eligible"])
        miss = ae.match(o, {}, today=date(2026, 10, 12))
        self.assertFalse(miss["eligible"]); self.assertIn("grade", miss["needs_owner"])
        for txt2, amt, cur in (("Entry fee: EUR 100", 100.0, "EUR"), ("The fee is 50 GBP", 50.0, "GBP"),
                               ("Application cost INR 1,500", 1500.0, "INR"), ("No fee. Deadline: 2026-12-20", 0.0, None),
                               ("Free to enter", 0.0, None)):
            p = ae.parse_opportunity(txt2)
            self.assertEqual((p["fee"], p["fee_currency"]), (amt, cur))
        for txt3, status in (("Entry fee: 500 ZAR", "unknown_currency"), ("Fee: ZAR 500", "unknown_currency"),
                             ("fee is 500", "unknown_currency"), ("Open to everyone", "not_stated"),
                             ("fee waiver available. Deadline 2026-12-20", "not_stated")):
            p = ae.parse_opportunity(txt3)
            self.assertIsNone(p["fee"]); self.assertEqual(p["fee_status"], status)
            self.assertTrue(ae.match(p, {}, today=date(2026, 10, 12))["needs_owner"])
        ok = ae.prepare(o, {}, lambda q, l, f: "I studied biology.", ["I studied biology"])
        self.assertTrue(ok["ready_for_owner_review"])
        bad = ae.prepare(o, {}, lambda q, l, f: "I won 99 awards " + "x " * 60, ["I studied"])
        self.assertGreaterEqual(len(bad["issues"]), 2)
        nobel = ae.prepare(o, {}, lambda q, l, f: "I won the Nobel Prize.", ["I studied biology"])
        self.assertFalse(nobel["ready_for_owner_review"])
        self.assertTrue(any("nobel" in i for i in nobel["issues"]))
        neg = ae.prepare(o, {}, lambda q, l, f: "I won the Nobel Prize.", ["I never won the Nobel Prize."])
        self.assertFalse(neg["ready_for_owner_review"])
        self.assertTrue(any("polarity conflict" in i for i in neg["issues"]))
        rev = ae.prepare(o, {}, lambda q, l, f: "I never studied biology.", ["I studied biology."])
        self.assertFalse(rev["ready_for_owner_review"])
        same = ae.prepare(o, {}, lambda q, l, f: "I never won the Nobel Prize.", ["I never won the Nobel Prize."])
        self.assertTrue(same["ready_for_owner_review"])

    def test_fee_conflicts(self):
        p = ae.parse_opportunity("No application fee. Mandatory registration fee EUR 100.")
        self.assertEqual((p["fee"], p["fee_currency"], p["fee_status"]), (100.0, "EUR", "conflict"))
        n = ae.match(p, {}, today=date(2026, 10, 12))["needs_owner"]
        self.assertTrue(any("conflicting fee statements" in x and "100.00 EUR" in x for x in n))
        p = ae.parse_opportunity("Free to enter. Finalist fee: 500 ZAR.")
        self.assertEqual((p["fee"], p["fee_status"]), (None, "conflict"))
        p = ae.parse_opportunity("Entry fee $10. Late fee $20.")
        self.assertEqual(p["fee_status"], "conflict")
        p = ae.parse_opportunity("No fee, deadline 2026-12-20")
        self.assertEqual((p["fee"], p["fee_status"]), (0.0, "free"))
        p = ae.parse_opportunity("Entry fee $10. Fee $10 payable online.")
        self.assertEqual(p["fee_status"], "stated")

    def test_history_audit(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a.py"), "w").write("def zebrafish_hatchery_tracker(): pass\n")
        open(os.path.join(d, "b.py"), "w").write("x = 1\n")
        chat = ("[12/10/26, 1:00:00 PM] Udita: please build a zebrafish hatchery tracker\n"
                "[12/10/26, 1:01:00 PM] Udita: build a quantum teleporter\n"
                "[12/10/26, 1:02:00 PM] Other: build zebrafish hatchery tracker\n")
        reqs = history_audit.parse(chat, "Udita")
        self.assertEqual(len(reqs), 2)
        r = history_audit.audit(reqs, d)
        self.assertEqual([x["verdict"] for x in r["rows"]], ["FOUND", "NO_EVIDENCE"])

    def test_creator_unsupported_is_explicit(self):
        self.assertEqual(universal_creator.route("build a landing page")["kind"], "web_app")
        r = universal_creator.route("cure all diseases")
        self.assertFalse(r["supported"]); self.assertEqual(r["verdict"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
