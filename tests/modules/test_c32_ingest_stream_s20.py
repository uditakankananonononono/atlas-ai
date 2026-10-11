"""S2.0 c32.ingest ingest_stream() tests (in-memory path). Hermetic, stdlib unittest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/ingest.py"
_spec = importlib.util.spec_from_file_location("c32_ingest_stream_mod", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_ingest_stream_mod"] = m
_spec.loader.exec_module(m)


def R(i, **kw):
    d = {"id": "r%d" % i, "text": "record %d" % i}
    d.update(kw)
    return d


def err(fn, *a, **k):
    try:
        fn(*a, **k)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("no ValueError")


class Streaming(unittest.TestCase):
    def test_accepts_generator_and_matches_list_ingest_counts(self):
        data = [R(1), R(2), R(1), R(3), R(2)]
        out = m.ingest_stream(r for r in data)
        ref = m.ingest(data)
        for k in ("ingested", "duplicates", "skipped", "shards", "next_checkpoint", "resumed_from"):
            self.assertEqual(out[k], ref[k], k)
        self.assertEqual(out["seen_ids"], ref["seen_ids"])

    def test_pulls_at_most_one_batch_ahead(self):
        pulled = []

        def gen():
            for i in range(50):
                pulled.append(i)
                yield R(i)

        out = m.ingest_stream(gen(), shard_size=7)
        self.assertEqual(len(pulled), 50)
        self.assertEqual(out["max_in_flight"], 7)
        self.assertEqual(out["batches"], 8)   # 7 full + 1 of 1

    def test_lazy_pull_is_bounded_before_a_later_failure(self):
        pulled = []

        def gen():
            for i in range(100):
                pulled.append(i)
                if i == 30:
                    raise RuntimeError("source died")
                yield R(i)

        with self.assertRaises(RuntimeError):
            m.ingest_stream(gen(), shard_size=10)
        self.assertEqual(max(pulled), 30)    # never read past the failing item; nothing pre-read the whole input

    def test_no_read_beyond_a_raising_record_batch(self):
        pulled = []

        def gen():
            for i in range(100):
                pulled.append(i)
                yield R(i) if i != 12 else {"text": "no id"}

        self.assertEqual(err(m.ingest_stream, gen(), shard_size=10), "TREND_REFUSED_EMPTY:id")
        self.assertEqual(len(pulled), 20)   # the failing record sits in batch 2; nothing past that batch is pulled

    def test_records_container_types(self):
        for bad in (None, True, 5, "abc", b"abc", {"id": "x"}):
            self.assertEqual(err(m.ingest_stream, bad), "TREND_REFUSED_BAD_TYPE:records")
        self.assertEqual(m.ingest_stream(iter([]))["ingested"], 0)
        self.assertEqual(m.ingest_stream((R(1),))["ingested"], 1)

    def test_checkpoint_resume_matches_canonical_shape(self):
        out = m.ingest_stream((R(i) for i in range(25)), shard_size=10)
        self.assertEqual(out["next_checkpoint"], {"shard": 2, "offset": 5})
        out = m.ingest_stream((R(i) for i in range(30)), shard_size=10, resume=True,
                              checkpoint={"shard": 2, "offset": 5})
        self.assertEqual((out["skipped"], out["ingested"]), (25, 5))
        self.assertEqual(out["next_checkpoint"], {"shard": 3, "offset": 0})
        out = m.ingest_stream(iter([{"junk": True}] * 5 + [R(1)]), shard_size=10, resume=True,
                              checkpoint={"shard": 0, "offset": 5})
        self.assertEqual((out["skipped"], out["ingested"]), (5, 1))   # skipped records not re-validated

    def test_resume_refusals(self):
        self.assertEqual(err(m.ingest_stream, iter([R(1)]), resume=True), "TREND_REFUSED_NOCHECKPOINT")
        self.assertEqual(err(m.ingest_stream, iter([R(i) for i in range(3)]), shard_size=10, resume=True,
                             checkpoint={"shard": 1, "offset": 0}), "TREND_REFUSED_CHECKPOINT_RANGE")
        out = m.ingest_stream(iter([R(i) for i in range(3)]), shard_size=10, resume=True,
                              checkpoint={"shard": 0, "offset": 3})
        self.assertEqual((out["skipped"], out["ingested"]), (3, 0))      # skipping exactly all is valid
        for bad in (True, "x", {"shard": 1}, {"shard": -1, "offset": 0}, {"shard": 0, "offset": True}):
            self.assertEqual(err(m.ingest_stream, iter([R(1)]), resume=True, checkpoint=bad),
                             "TREND_REFUSED_BAD_TYPE:checkpoint")

    def test_shard_size_refusals_and_limit(self):
        for bad in (True, "x", 0, -5, 2.5):
            self.assertEqual(err(m.ingest_stream, iter([R(1)]), shard_size=bad), "TREND_REFUSED_BAD_TYPE:shard_size")
        self.assertEqual(err(m.ingest_stream, iter([R(1)]), shard_size=m.MAX_SHARD + 1), "TREND_REFUSED_OVERSIZE")
        self.assertEqual(m.ingest_stream(iter([R(1)]), shard_size=m.MAX_SHARD)["ingested"], 1)

    def test_dedupe_with_seen_does_not_mutate_callers_set(self):
        seen = {"r1"}
        out = m.ingest_stream(iter([R(1), R(2)]), seen=seen)
        self.assertEqual((out["ingested"], out["duplicates"]), (1, 1))
        self.assertEqual(seen, {"r1"})
        self.assertEqual(out["seen_ids"], {"r1", "r2"})

    def test_pins_default_shard_size_one_and_resumed_shards(self):
        out = m.ingest_stream(R(i) for i in range(10001))
        self.assertEqual((out["batches"], out["max_in_flight"], out["shards"]), (2, 10000, 2))
        self.assertEqual(out["next_checkpoint"], {"shard": 1, "offset": 1})
        out = m.ingest_stream((R(i) for i in range(3)), shard_size=1)
        self.assertEqual((out["batches"], out["shards"]), (3, 3))
        out = m.ingest_stream((R(i) for i in range(25)), shard_size=10, resume=True,
                              checkpoint={"shard": 0, "offset": 5})
        self.assertEqual((out["skipped"], out["ingested"], out["shards"]), (5, 20, 2))


class MalformedPolicy(unittest.TestCase):
    BAD = [5, None, "s", {"text": "no id"}, {"id": "a\nb"}, {"id": ""}, {"id": 7}, {"id": "ok", "text": 3}]

    def test_default_is_raise_with_canonical_codes(self):
        cases = ((5, "TREND_REFUSED_BAD_TYPE:record"), (None, "TREND_REFUSED_BAD_TYPE:record"),
                 ({"text": "no id"}, "TREND_REFUSED_EMPTY:id"), ({"id": "a\nb"}, "TREND_REFUSED_CONTROL_CHARS:id"),
                 ({"id": ""}, "TREND_REFUSED_EMPTY:id"), ({"id": 7}, "TREND_REFUSED_BAD_TYPE:id"),
                 ({"id": "ok", "text": 3}, "TREND_REFUSED_BAD_TYPE:text"))
        for bad, code in cases:
            self.assertEqual(err(m.ingest_stream, iter([bad])), code, bad)
            self.assertEqual(err(m.ingest_stream, iter([bad]), malformed="raise"), code, bad)

    def test_count_mode_skips_and_counts_every_bad_shape(self):
        out = m.ingest_stream(iter(self.BAD + [R(1)]), malformed="count")
        self.assertEqual(out["rejected_malformed"], len(self.BAD))
        self.assertEqual((out["ingested"], out["rejected_oversize"]), (1, 0))

    def test_counted_records_advance_the_checkpoint(self):
        out = m.ingest_stream(iter(self.BAD + [R(1)]), shard_size=4, malformed="count")
        consumed = len(self.BAD) + 1
        self.assertEqual(out["next_checkpoint"], {"shard": consumed // 4, "offset": consumed % 4})
        self.assertEqual(out["shards"], -(-consumed // 4))

    def test_scrape_always_refuses_even_in_count_mode(self):
        for rec in (R(1, url="https://example.com/x"), R(1, fetch=True)):
            for mode in ("raise", "count"):
                self.assertEqual(err(m.ingest_stream, iter([rec]), malformed=mode), "TREND_REFUSED_SCRAPE")

    def test_bad_malformed_argument(self):
        for bad in ("skip", None, True, 1, ""):
            self.assertEqual(err(m.ingest_stream, iter([R(1)]), malformed=bad), "TREND_REFUSED_BAD_TYPE:malformed")


class ByteLimit(unittest.TestCase):
    def test_constant(self):
        self.assertEqual(m.MAX_RECORD_BYTES, 65536)

    def _rec(self, size, ch="a"):
        rid = "id"
        return {"id": rid, "text": ch * (size - len(rid.encode()))}

    def test_exact_limit_passes_and_one_over_refuses(self):
        self.assertEqual(m.ingest_stream(iter([self._rec(65536)]))["ingested"], 1)
        self.assertEqual(err(m.ingest_stream, iter([self._rec(65537)])), "TREND_REFUSED_OVERSIZE")

    def test_size_is_utf8_bytes_of_id_plus_text(self):
        two_byte = {"id": "i", "text": "é" * 32767}          # 1 + 65534 = 65535 bytes, 32768 chars
        self.assertEqual(m.ingest_stream(iter([two_byte]))["ingested"], 1)
        over = {"id": "i", "text": "é" * 32768}              # 1 + 65536 = 65537 bytes
        self.assertEqual(err(m.ingest_stream, iter([over])), "TREND_REFUSED_OVERSIZE")
        edge = {"id": "i", "text": "é" * 32767 + "a"}        # 1 + 65534 + 1 = 65536 exactly
        self.assertEqual(m.ingest_stream(iter([edge]))["ingested"], 1)

    def test_id_counts_toward_size(self):
        rec = {"id": "x" * 256, "text": "a" * (65536 - 256)}
        self.assertEqual(m.ingest_stream(iter([rec]))["ingested"], 1)
        rec["text"] += "a"
        self.assertEqual(err(m.ingest_stream, iter([rec])), "TREND_REFUSED_OVERSIZE")

    def test_missing_text_counts_as_empty(self):
        self.assertEqual(m.ingest_stream(iter([{"id": "a"}]))["ingested"], 1)

    def test_count_mode_counts_oversize_separately(self):
        out = m.ingest_stream(iter([self._rec(65537), R(1), self._rec(65537), {"x": 1}]), malformed="count")
        self.assertEqual((out["rejected_oversize"], out["rejected_malformed"], out["ingested"]), (2, 1, 1))
        self.assertEqual(out["next_checkpoint"], {"shard": 0, "offset": 4})


class LedgerAndHonesty(unittest.TestCase):
    def test_scope_and_mode_and_keys(self):
        out = m.ingest_stream(iter([R(1)]))
        self.assertEqual(out["mode"], "in-memory")
        self.assertEqual(set(out["scope"]), {"implemented", "not_implemented", "data_source", "as_of"})
        self.assertEqual(out["scope"]["data_source"], "supplied records")
        self.assertIn("continuous unattended operation", out["scope"]["not_implemented"])
        self.assertIn("persistence (checkpoint and seen set live in the caller)", out["scope"]["not_implemented"])
        self.assertEqual((out["rejected_malformed"], out["rejected_oversize"], out["batches"]), (0, 0, 1))

    def test_empty_input(self):
        out = m.ingest_stream(iter([]), shard_size=10)
        self.assertEqual((out["batches"], out["shards"], out["max_in_flight"]), (0, 0, 0))
        self.assertEqual(out["next_checkpoint"], {"shard": 0, "offset": 0})

    def test_canonical_ingest_untouched_by_the_new_function(self):
        out = m.ingest([R(1), R(1)])
        self.assertEqual((out["ingested"], out["duplicates"]), (1, 1))
        self.assertNotIn("mode", out)
        self.assertEqual(m.MAX_BENCH, 2000000)


class StoreWiring(unittest.TestCase):
    def setUp(self):
        import json as _j, tempfile, os
        from app.ingest.store import IngestStore
        self.j = _j
        self.dir = tempfile.mkdtemp(prefix="s20store-")
        self.path = os.path.join(self.dir, "t.db")
        self.store = IngestStore(self.path)
        self.IngestStore = IngestStore

    def tearDown(self):
        import shutil
        self.store.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_(self, recs, **kw):
        kw.setdefault("shard_size", 10)
        return m.ingest_stream(iter(recs), store=self.store, job_key="job", source="src", **kw)

    def test_commits_items_and_json_text_cursor(self):
        out = self.run_([R(i) for i in range(25)])
        self.assertEqual((out["mode"], out["ingested"], out["batches"]), ("store", 25, 3))
        self.assertIsNone(out["seen_ids"])
        self.assertEqual(self.store.count_items("src"), 25)
        cp = self.store.load_checkpoint("job")
        self.assertEqual(cp["cursor"], '{"offset": 5, "shard": 2}')
        self.assertEqual((cp["batches_committed"], cp["items_new"], cp["items_duplicate"]), (3, 25, 0))
        item = self.store.get_item("src", "r3")
        self.assertEqual(item["payload"], {"id": "r3", "text": "record 3"})
        self.assertEqual(item["canonical_url"], "")

    def test_first_write_wins_across_runs_and_in_batch(self):
        self.run_([{"id": "a", "text": "FIRST"}])
        out = self.run_([{"id": "a", "text": "SECOND"}, {"id": "b", "text": "x"}, {"id": "b", "text": "y"}])
        self.assertEqual((out["ingested"], out["duplicates"], out["duplicates_skipped"]), (1, 2, 2))
        a = self.store.get_item("src", "a")
        self.assertEqual((a["payload"]["text"], a["seen_count"]), ("FIRST", 1))
        b = self.store.get_item("src", "b")
        self.assertEqual((b["payload"]["text"], b["seen_count"]), ("x", 1))
        cp = self.store.load_checkpoint("job")
        self.assertEqual(cp["items_duplicate"], 0)     # prefiltered dups never reach the store

    def test_dedupe_is_per_source(self):
        self.run_([R(1)])
        out = m.ingest_stream(iter([R(1)]), store=self.store, job_key="job2", source="other")
        self.assertEqual(out["ingested"], 1)
        self.assertEqual(self.store.count_items(), 2)

    def test_resume_reads_cursor_from_store_and_reopen(self):
        data = [R(i) for i in range(25)]
        self.run_(data[:13])
        self.store.close()
        self.store = self.IngestStore(self.path)
        out = self.run_(data, resume=True)
        self.assertEqual((out["skipped"], out["ingested"]), (13, 12))
        self.assertEqual(out["resumed_from"], {"shard": 1, "offset": 3})
        self.assertEqual(self.store.count_items("src"), 25)
        self.assertEqual(self.store.load_checkpoint("job")["cursor"], '{"offset": 5, "shard": 2}')

    def test_resume_without_any_checkpoint_refuses(self):
        self.assertEqual(err(self.run_, [R(1)], resume=True), "TREND_REFUSED_NOCHECKPOINT")

    def test_explicit_checkpoint_beats_store(self):
        self.run_([R(i) for i in range(5)])
        out = self.run_([R(i) for i in range(5)], resume=True, checkpoint={"shard": 0, "offset": 2})
        self.assertEqual((out["skipped"], out["duplicates"]), (2, 3))

    def test_corrupt_stored_cursor_refuses(self):
        self.store.commit_batch("job", "src", [], "not json")
        self.assertEqual(err(self.run_, [R(1)], resume=True), "TREND_REFUSED_BAD_TYPE:checkpoint")

    def test_raise_mid_stream_keeps_prior_batches_only(self):
        recs = [R(i) for i in range(15)] + [{"text": "no id"}] + [R(i) for i in range(16, 20)]
        self.assertEqual(err(self.run_, recs), "TREND_REFUSED_EMPTY:id")
        self.assertEqual(self.store.count_items("src"), 10)      # batch 2 not committed
        self.assertEqual(self.store.load_checkpoint("job")["cursor"], '{"offset": 0, "shard": 1}')

    def test_count_mode_with_store_advances_cursor_and_skips_bad(self):
        out = self.run_([R(1), 5, R(2), {"id": "big", "text": "a" * 70000}], malformed="count")
        self.assertEqual((out["ingested"], out["rejected_malformed"], out["rejected_oversize"]), (2, 1, 1))
        self.assertEqual(self.store.count_items("src"), 2)
        self.assertEqual(self.store.load_checkpoint("job")["cursor"], '{"offset": 4, "shard": 0}')

    def test_empty_accepted_batch_still_advances_checkpoint(self):
        self.run_([R(1)])
        out = self.run_([R(1)])
        self.assertEqual(out["ingested"], 0)
        self.assertEqual(self.store.load_checkpoint("job")["batches_committed"], 2)

    def test_scrape_refuses_and_commits_nothing(self):
        self.assertEqual(err(self.run_, [R(1), R(2, url="http://x")], malformed="count"), "TREND_REFUSED_SCRAPE")
        self.assertEqual(self.store.count_items(), 0)
        self.assertIsNone(self.store.load_checkpoint("job"))

    def test_argument_pairing(self):
        for kw in ({"job_key": "j", "source": "s"}, {"job_key": "j"}, {"source": "s"}):
            self.assertEqual(err(m.ingest_stream, iter([R(1)]), **kw), "TREND_REFUSED_BAD_TYPE:store")
        for jk, sc in ((None, "s"), ("j", None), ("", "s"), ("j", " "), (5, "s")):
            self.assertEqual(err(m.ingest_stream, iter([R(1)]), store=self.store, job_key=jk, source=sc),
                             "TREND_REFUSED_BAD_TYPE:store_key")

    def test_scope_states_single_writer_only(self):
        out = self.run_([R(1)])
        ni = " ".join(out["scope"]["not_implemented"])
        self.assertIn("single-writer offline batch only", ni)
        self.assertNotIn("persistence", ni)


if __name__ == "__main__":
    unittest.main()
