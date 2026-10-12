"""Groups 67-76 tests. Hermetic, stdlib unittest."""
import json, os, pathlib, sys, tempfile, unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from app.modules.instinct_doc.g67_76 import (adapters, fleet, feed_ingest, interest_signals,
                                              ideation, application_engine as ae, history_audit, universal_creator)

RSS = b"""<rss><channel><item><title>Grant opens</title><link>http://x/1</link><description>bio grant</description></item>
<item><title>Prize</title><link>http://x/2</link><description>ai prize</description></item></channel></rss>"""


class T(unittest.TestCase):
    def test_cli_adapter_really_runs(self):
        r = adapters.trial({"name": "echo_tool", "kind": "cli", "command": ["echo"]}, {"args": ["hi"]})
        self.assertTrue(r["passed"]); self.assertEqual(r["result"]["stdout"], "hi\n")

    def test_http_adapter_with_transport(self):
        r = adapters.trial({"name": "api_tool", "kind": "http_json", "url": "https://e.x/a"}, {"q": 1},
                           transport=lambda u, d: (200, b'{"a": 1}'))
        self.assertTrue(r["passed"]); self.assertEqual(r["result"]["data"], {"a": 1})

    def test_failed_trial_reported(self):
        r = adapters.trial({"name": "bad_tool", "kind": "cli", "command": ["ls"]}, {"args": ["/nonexistent_zz"]})
        self.assertFalse(r["passed"]); self.assertIn("FAILED", r["owner_notification"])

    def test_refusals(self):
        for spec in ({"name": "x1", "kind": "cli", "command": ["rm"]},
                     {"name": "paid_t", "kind": "cli", "command": ["echo"], "paid": True},
                     {"name": "h_t", "kind": "http_json", "url": "http://insecure"},
                     {"name": "Bad Name", "kind": "cli", "command": ["echo"]}):
            with self.assertRaises(ValueError):
                adapters.generate(spec)

    def test_fleet_1000_measured(self):
        async def w(job):
            return job["id"]
        r = fleet.run([{"id": "j%d" % i} for i in range(1000)], w)
        self.assertEqual(r["ok"], 1000); self.assertEqual(r["peak_inflight_measured"], 1000)
        self.assertTrue(r["simultaneous_1000_achieved"])

    def test_fleet_capped_not_claimed(self):
        async def w(job):
            return 1
        r = fleet.run([{"id": "j%d" % i} for i in range(50)], w, concurrency=5)
        self.assertEqual(r["peak_inflight_measured"], 5); self.assertFalse(r["simultaneous_1000_achieved"])

    def test_fleet_budget(self):
        async def w(job):
            return 1
        r = fleet.run([{"id": "j%d" % i, "cost": 2} for i in range(10)], w, concurrency=10, budget=6)
        self.assertEqual(r["ok"], 3); self.assertEqual(r["skipped_budget"], 7)

    def test_ingest_dedupe_resume_export(self):
        s = feed_ingest.Store()
        f = lambda u: RSS if u.endswith("feed") else (_ for _ in ()).throw(OSError())
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

    def test_signals(self):
        sig = interest_signals.from_starred_gmail([
            {"labelIds": ["STARRED"], "subject": "Genomics scholarship", "snippet": "genomics deadline"},
            {"labelIds": ["INBOX"], "subject": "Sale", "snippet": "shoes"}])
        sig += interest_signals.from_linkedin_csv("Date,Link,Type\n1,http://l/genomics-lab,LIKE\n")
        sig += interest_signals.from_instagram_likes(json.dumps({"likes_media_likes": [{"title": "robotics", "string_list_data": [{"value": "robotics"}]}]}))
        top = interest_signals.rank(sig)
        self.assertEqual(top[0]["topic"], "genomics"); self.assertNotIn("shoes", [t["topic"] for t in top])
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
        self.assertTrue(m["eligible"]); self.assertEqual(m["needs_owner"], ["fee approval: 25.00"])
        self.assertFalse(ae.match(o, {"grade": 9}, today=date(2026, 10, 12))["eligible"])
        self.assertFalse(ae.match(o, {"grade": 12}, today=date(2027, 1, 1))["eligible"])
        ok = ae.prepare(o, {}, lambda q, l, f: "I studied biology.", ["I studied biology"])
        self.assertTrue(ok["ready_for_owner_review"])
        bad = ae.prepare(o, {}, lambda q, l, f: "I won 99 awards " + "x " * 60, ["I studied"])
        self.assertEqual(len(bad["issues"]), 2)

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
