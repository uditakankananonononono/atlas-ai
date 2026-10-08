"""Stdlib-only executable tests, independent of eager app package imports."""
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/app/modules/m11_calendar_intelligence/calendar_occupancy.py"
spec = importlib.util.spec_from_file_location("occupancy_lane", MODULE)
occupancy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = occupancy
spec.loader.exec_module(occupancy)
E = occupancy.OccupancyEvent
calculate = occupancy.calendar_occupancy
UTC = timezone.utc


def dt(s):
    return datetime.fromisoformat(s)


class OccupancyTests(unittest.TestCase):
    def test_overlapping_nested_and_adjacent(self):
        rows = [E("a", dt("2026-10-08T09:00+00:00"), dt("2026-10-08T11:00+00:00")),
                E("b", dt("2026-10-08T09:30+00:00"), dt("2026-10-08T10:30+00:00")),
                E("c", dt("2026-10-08T10:00+00:00"), dt("2026-10-08T12:00+00:00")),
                E("d", dt("2026-10-08T12:00+00:00"), dt("2026-10-08T12:30+00:00"))]
        d = calculate(rows, date(2026, 10, 8), day_count=1).days[0]
        self.assertEqual((d.occupied_seconds, d.event_seconds, d.overlapping_seconds,
                          d.peak_concurrency, d.event_count), (12600, 19800, 5400, 3, 4))

    def test_clip_week_and_midnight(self):
        r = calculate([E("a", dt("2026-10-07T23:30+00:00"), dt("2026-10-09T00:30+00:00")),
                       E("b", dt("2026-10-14T23:30+00:00"), dt("2026-10-15T01:00+00:00"))], date(2026, 10, 8))
        self.assertEqual([d.occupied_seconds for d in r.days], [86400, 1800, 0, 0, 0, 0, 1800])
        self.assertEqual(r.occupied_seconds, 90000)

    def test_india_day_assignment(self):
        r = calculate([E("a", dt("2026-10-08T18:00+00:00"), dt("2026-10-08T19:00+00:00"))],
                      date(2026, 10, 8), "Asia/Kolkata", 2)
        self.assertEqual([d.occupied_seconds for d in r.days], [1800, 1800])

    def test_spring_forward_elapsed(self):
        z = ZoneInfo("America/New_York")
        e = E("a", datetime(2026, 3, 8, 1, 30, tzinfo=z), datetime(2026, 3, 8, 3, 30, tzinfo=z))
        d = calculate([e], date(2026, 3, 8), z.key, 1).days[0]
        self.assertEqual((d.day_seconds, d.occupied_seconds), (82800, 3600))

    def test_fall_back_fold_elapsed(self):
        z = ZoneInfo("America/New_York")
        e = E("a", datetime(2026, 11, 1, 1, 15, tzinfo=z, fold=0), datetime(2026, 11, 1, 1, 45, tzinfo=z, fold=1))
        d = calculate([e], date(2026, 11, 1), z.key, 1).days[0]
        self.assertEqual((d.day_seconds, d.occupied_seconds), (90000, 5400))

    def test_midnight_gap(self):
        r = calculate([], date(2018, 11, 4), "America/Sao_Paulo", 1)
        self.assertEqual(r.days[0].day_seconds, 82800)

    def test_ambiguous_midnight(self):
        r = calculate([], date(2020, 11, 1), "America/Havana", 1)
        self.assertEqual(r.days[0].day_seconds, 90000)

    def test_skipped_date(self):
        r = calculate([], date(2011, 12, 29), "Pacific/Apia", 3)
        self.assertEqual([d.day_seconds for d in r.days], [86400, 0, 86400])

    def test_fractional_seconds_preserved(self):
        e = E("a", dt("2026-10-08T00:00:00.100000+00:00"), dt("2026-10-08T00:00:00.900000+00:00"))
        d = calculate([e], date(2026, 10, 8), day_count=1).days[0]
        self.assertEqual(d.occupied_seconds, 0.8)

    def test_cancelled_and_transparent(self):
        a, b = dt("2026-10-08T00:00+00:00"), dt("2026-10-09T00:00+00:00")
        d = calculate([E("a", a, b, busy=False), E("b", a, b, cancelled=True)], date(2026, 10, 8), day_count=1).days[0]
        self.assertEqual((d.occupied_seconds, d.event_count, d.free_seconds), (0, 0, 86400))

    def test_invalid_and_duplicate_inputs(self):
        a, b = dt("2026-10-08T00:00+00:00"), dt("2026-10-08T01:00+00:00")
        bad = [[E("a", a, a)], [E("a", b, a)], [E("", a, b)],
               [E("a", a.replace(tzinfo=None), b)], [E("a", a, b), E("a", a, b)], [E("a", a, b, busy="false")]]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                calculate(rows, date(2026, 10, 8))
        for n in (0, 367, True):
            with self.assertRaises(ValueError):
                calculate([], date(2026, 10, 8), day_count=n)
        with self.assertRaises(KeyError):
            calculate([], date(2026, 10, 8), "not/a-zone")

    def test_nonexistent_event_walltime(self):
        z = ZoneInfo("America/New_York")
        with self.assertRaises(ValueError):
            calculate([E("a", datetime(2026, 3, 8, 2, 30, tzinfo=z), datetime(2026, 3, 8, 4, tzinfo=z))], date(2026, 3, 8))

    def test_seeded_discrete_oracle_200_cases(self):
        rng = random.Random(94111)
        origin = dt("2026-10-08T00:00+00:00")
        for trial in range(200):
            counts = [0] * 300
            rows = []
            for i in range(rng.randrange(1, 40)):
                start = rng.randrange(300)
                end = rng.randrange(start + 1, 301)
                rows.append(E(str(i), origin + timedelta(seconds=start), origin + timedelta(seconds=end)))
                for second in range(start, end):
                    counts[second] += 1
            d = calculate(rows, origin.date(), day_count=1).days[0]
            with self.subTest(trial=trial):
                self.assertEqual(d.occupied_seconds, sum(n > 0 for n in counts))
                self.assertEqual(d.event_seconds, sum(counts))
                self.assertEqual(d.overlapping_seconds, sum(n > 1 for n in counts))
                self.assertEqual(d.peak_concurrency, max(counts))
                self.assertEqual(calculate(reversed(rows), origin.date(), day_count=1).days[0], d)

    def test_empty_horizon_and_exact_end_exclusion(self):
        start = dt("2026-10-08T00:00+00:00")
        rows = [E("before", start - timedelta(hours=1), start),
                E("after", start + timedelta(days=1), start + timedelta(days=1, hours=1))]
        d = calculate(rows, start.date(), day_count=1).days[0]
        self.assertEqual((d.event_count, d.occupied_seconds, d.peak_concurrency), (0, 0, 0))

    def test_ten_thousand_events(self):
        start = dt("2026-10-08T00:00+00:00")
        rows = [E(str(i), start + timedelta(seconds=i), start + timedelta(seconds=i+60)) for i in range(10000)]
        d = calculate(rows, start.date(), day_count=1).days[0]
        self.assertEqual((d.occupied_seconds, d.event_seconds, d.overlapping_seconds, d.peak_concurrency),
                         (10059, 600000, 10057, 60))

    def test_cli_real_process(self):
        payload = [{"event_id": "a", "start": "2026-10-08T09:00+00:00", "end": "2026-10-08T10:00+00:00"}]
        proc = subprocess.run([sys.executable, str(MODULE), "--start-date", "2026-10-08", "--days", "1"],
                              input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["occupied_seconds"], 3600)

    def test_cli_errors_have_no_payload_echo(self):
        for payload, zone in (("[]", "not/a-zone"), ('[{"secret":"do-not-echo"}]', "UTC"), ("no-json", "UTC")):
            proc = subprocess.run([sys.executable, str(MODULE), "--start-date", "2026-10-08", "--timezone", zone],
                                  input=payload, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
            self.assertNotIn("do-not-echo", proc.stderr)
            self.assertEqual(json.loads(proc.stderr)["error"], "invalid_calendar_input")


if __name__ == "__main__":
    unittest.main(verbosity=2)
