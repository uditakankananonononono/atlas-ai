"""S2.0 / c32.ingest continuous-ingest pipeline tests. Hermetic, stdlib unittest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/ingest.py"
_spec = importlib.util.spec_from_file_location("c32_ingest", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_ingest"] = m
_spec.loader.exec_module(m)


def R(i, **kw):
    d = {"id": "r%d" % i, "text": "record %d" % i}
    d.update(kw)
    return d


class Ingest(unittest.TestCase):
    def test_basic_counts_and_scope(self):
        out = m.ingest([R(1), R(2), R(3)])
        self.assertEqual(out["ingested"], 3)
        self.assertEqual(out["duplicates"], 0)
        self.assertEqual(out["shards"], 1)
        self.assertEqual(out["resumed_from"], None)
        self.assertEqual(out["scope"]["data_source"], "supplied records")
        self.assertIn("real checkpointing (skip applied shard/offset, return next checkpoint)", out["scope"]["implemented"])

    def test_dedupe_by_id(self):
        out = m.ingest([R(1), R(2), R(1), R(2), R(2)])
        self.assertEqual(out["ingested"], 2)
        self.assertEqual(out["duplicates"], 3)

    def test_dedupe_across_calls_with_seen(self):
        first = m.ingest([R(1), R(2)])
        out = m.ingest([R(2), R(3)], seen=first["seen_ids"])
        self.assertEqual(out["ingested"], 1)
        self.assertEqual(out["duplicates"], 1)

    def test_sharding(self):
        out = m.ingest([R(i) for i in range(25)], shard_size=10)
        self.assertEqual(out["shards"], 3)

    def test_scrape_refused_via_guard(self):
        # Removing the guard import/call must fail this test.
        with self.assertRaises(ValueError) as cm:
            m.ingest([R(1, url="https://example.com/feed")])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_SCRAPE")
        with self.assertRaises(ValueError) as cm:
            m.ingest([R(1, fetch=True)])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_SCRAPE")

    def test_oversize_shard_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.ingest([R(1)], shard_size=m.MAX_SHARD + 1)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")
        out = m.ingest([R(1)], shard_size=m.MAX_SHARD)  # the limit itself passes
        self.assertEqual(out["ingested"], 1)

    def test_resume_requires_checkpoint(self):
        with self.assertRaises(ValueError) as cm:
            m.ingest([R(1)], resume=True)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_NOCHECKPOINT")
        out = m.ingest([R(9)], resume=True, checkpoint={"shard": 0, "offset": 0})
        self.assertEqual(out["resumed_from"], {"shard": 0, "offset": 0})

    def test_next_checkpoint_returned(self):
        out = m.ingest([R(i) for i in range(25)], shard_size=10)
        self.assertEqual(out["next_checkpoint"], {"shard": 2, "offset": 5})
        self.assertEqual(out["skipped"], 0)
        out = m.ingest([R(i) for i in range(3)], shard_size=10)
        self.assertEqual(out["next_checkpoint"], {"shard": 0, "offset": 3})
        out = m.ingest([], shard_size=10)
        self.assertEqual(out["next_checkpoint"], {"shard": 0, "offset": 0})

    def test_checkpoint_skips_applied_records(self):
        # checkpoint {shard: 2, offset: 5} at shard_size 10 = first 25 records applied
        out = m.ingest([R(i) for i in range(30)], shard_size=10, resume=True,
                       checkpoint={"shard": 2, "offset": 5})
        self.assertEqual(out["skipped"], 25)
        self.assertEqual(out["ingested"], 5)
        self.assertEqual(out["duplicates"], 0)
        self.assertEqual(out["next_checkpoint"], {"shard": 3, "offset": 0})
        # skipped records are not re-validated and do not touch the dedupe set
        out = m.ingest([{"junk": True}] * 5 + [R(1)], shard_size=10, resume=True,
                       checkpoint={"shard": 0, "offset": 5})
        self.assertEqual(out["skipped"], 5)
        self.assertEqual(out["ingested"], 1)

    def test_checkpoint_past_batch_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.ingest([R(i) for i in range(3)], shard_size=10, resume=True,
                     checkpoint={"shard": 1, "offset": 0})
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CHECKPOINT_RANGE")
        # boundary: skipping exactly the whole batch is valid
        out = m.ingest([R(i) for i in range(3)], shard_size=10, resume=True,
                       checkpoint={"shard": 0, "offset": 3})
        self.assertEqual(out["skipped"], 3)
        self.assertEqual(out["ingested"], 0)

    def test_bad_records_refused(self):
        for bad in (None, True, 1, "s"):
            with self.assertRaises(ValueError) as cm:
                m.ingest(bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:records")
        with self.assertRaises(ValueError) as cm:
            m.ingest([{"text": "no id"}])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_EMPTY:id")
        with self.assertRaises(ValueError) as cm:
            m.ingest([{"id": "a\nb"}])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:id")

    def test_checkpoint_shape_pins(self):
        # auditor survivors ingest-19/29/62: every malformed checkpoint refuses
        bads = (True, "x", ["a"], {"shard": 1}, {"offset": 0},
                {"shard": 1, "offset": 0, "extra": 2}, {"shard": True, "offset": 0},
                {"shard": 0, "offset": True}, {"shard": -1, "offset": 0},
                {"shard": 0, "offset": -1}, {"shard": 0.5, "offset": 0},
                {"shard": 0, "offset": "0"})
        for bad in bads:
            with self.assertRaises(ValueError) as cm:
                m.ingest([R(1)], resume=True, checkpoint=bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:checkpoint")

    def test_shard_size_type_pins(self):
        # auditor survivors ingest-20/31
        for bad in (True, "x", 0, -5, 2.5):
            with self.assertRaises(ValueError) as cm:
                m.ingest([R(1)], shard_size=bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:shard_size")

    def test_record_dict_pin(self):
        # auditor survivor ingest-36
        for bad in ("x", 5, None, True, ["id"]):
            with self.assertRaises(ValueError) as cm:
                m.ingest([bad])
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:record")

    def test_next_checkpoint_counts_all_consumed(self):
        # auditor survivor ingest-40: consumed = skipped + ingested + duplicates
        out = m.ingest([R(0), R(1), R(2), R(3), R(4), R(2)], shard_size=4,
                       resume=True, checkpoint={"shard": 0, "offset": 2}, seen={"r2"})
        # skip r0,r1; r2 dup (seen); r3,r4 ingested; r2 again dup -> consumed 6
        self.assertEqual(out["skipped"], 2)
        self.assertEqual(out["duplicates"], 2)
        self.assertEqual(out["ingested"], 2)
        self.assertEqual(out["next_checkpoint"], {"shard": 1, "offset": 2})

    def test_shards_count_duplicates(self):
        # auditor survivor ingest-41: shards over ingested + duplicates
        out = m.ingest([R(1), R(2), R(1), R(2), R(2)], shard_size=4)
        self.assertEqual(out["shards"], 2)  # total 5, not ingested-dups math

    def test_benchmark_records_count_pins(self):
        # auditor survivors ingest-24/42
        for bad in (True, "x", 0, -7, 2.5):
            with self.assertRaises(ValueError) as cm:
                m.benchmark(bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:records_count")

    def test_benchmark_throughput_deterministic_clock(self):
        # auditor survivor ingest-60: elapsed = perf_counter() - start
        real = m.time.perf_counter
        seq = iter([10.0, 10.25])
        m.time.perf_counter = lambda: next(seq)
        try:
            out = m.benchmark(100)
        finally:
            m.time.perf_counter = real
        self.assertEqual(out["records_per_second"], 400)  # 100 / 0.25s

    def test_benchmark_capacity_and_throughput(self):
        # U02/U38 fold: capacity and throughput benchmark over synthetic records.
        out = m.benchmark(200000, shard_size=50000)
        self.assertEqual(out["records"], 200000)
        self.assertEqual(out["ingested"], 200000)
        self.assertEqual(out["shards"], 4)
        self.assertGreater(out["records_per_second"], 0)
        self.assertEqual(out["scope"]["data_source"], "synthetic generated records")

    def test_benchmark_shard_size_refused(self):
        for bad in (0, -1, -50000, True, "x"):
            with self.assertRaises(ValueError) as cm:
                m.benchmark(100, shard_size=bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:shard_size")
        with self.assertRaises(ValueError) as cm:
            m.benchmark(100, shard_size=m.MAX_SHARD + 1)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")
        out = m.benchmark(3, shard_size=1)
        self.assertEqual(out["shards"], 3)

    def test_benchmark_count_upper_bound(self):
        with self.assertRaises(ValueError) as cm:
            m.benchmark(m.MAX_BENCH + 1)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")


if __name__ == "__main__":
    unittest.main()
