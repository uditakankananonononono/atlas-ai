"""Offline contract tests, AUTHORED NOT RUN. No app imports or services.

Loads only the new helper by file path to avoid package initialization wiring.
These contracts do not prove existing HostRateLimiter integration.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SOURCE = (Path(__file__).resolve().parents[2] / "backend/app/modules/"
          "m18_side_hustle_scraper/lane_rate_limit_state.py")
SPEC = importlib.util.spec_from_file_location("m18_pacing_state_contract", SOURCE)
state = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = state
SPEC.loader.exec_module(state)
T0 = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)


class PacingDurabilityContract(unittest.TestCase):
    def setUp(self):
        self.row = state.PacingState(T0, 8.0, 3, T0 + timedelta(seconds=120), 7, 3)
        self.rows = {"example.test:443": self.row}

    def encode(self, rows=None):
        return state.encode_snapshot("tenant-a", self.rows if rows is None else rows,
                                     now=T0, expires_at=T0 + timedelta(hours=1))

    def decode(self, raw, **kwargs):
        options = {"tenant_id": "tenant-a", "now": T0 + timedelta(seconds=20)}
        options.update(kwargs)
        return state.decode_snapshot(raw, **options)

    def altered(self, update):
        document = json.loads(self.encode())
        update(document["payload"])
        document["sha256"] = hashlib.sha256(state._canonical(document["payload"])).hexdigest()
        return state._canonical(document)

    def test_roundtrip_retains_backoff_circuit_and_all_counters(self):
        restored = self.decode(self.encode())
        self.assertEqual(restored.states, self.rows)
        self.assertEqual(restored.saved_at, T0)
        with self.assertRaises(TypeError):
            restored.states["new.test"] = self.row

    def test_retry_after_deadline_preserved_across_restart(self):
        # Existing honor_retry_after stores its deadline in circuit_open_until.
        restored = self.decode(self.encode()).states["example.test:443"]
        self.assertEqual((restored.circuit_open_until - (T0 + timedelta(seconds=20))).total_seconds(), 100)
        self.assertEqual(restored.interval, 8.0)

    def test_pacing_deadline_preserved_with_no_circuit(self):
        row = replace(self.row, circuit_open_until=None)
        restored = self.decode(self.encode({"host": row}), now=T0 + timedelta(seconds=3))
        remaining = restored.states["host"].interval - 3
        self.assertEqual(remaining, 5)

    def test_offset_normalized_and_naive_timestamps_rejected(self):
        offset = timezone(timedelta(hours=5, minutes=30))
        row = replace(self.row, last_request_at=T0.astimezone(offset))
        self.assertEqual(self.decode(self.encode({"host": row})).states["host"].last_request_at, T0)
        with self.assertRaises(state.StateRejected):
            self.encode({"host": replace(self.row, last_request_at=T0.replace(tzinfo=None))})
        with self.assertRaises(state.StateRejected):
            self.decode(self.encode(), now=T0.replace(tzinfo=None))
        with self.assertRaises(state.StateRejected):
            self.decode(self.altered(lambda p: p.update(saved_at="2026-10-10T00:00:00")))

    def test_tenant_mismatch_expiry_and_clock_rollback_deny(self):
        for options in ({"tenant_id": "tenant-b"}, {"now": T0 + timedelta(hours=1)},
                        {"now": T0 - timedelta(microseconds=1)}):
            with self.subTest(options=options), self.assertRaises(state.StateRejected):
                self.decode(self.encode(), **options)

    def test_missing_truncated_corrupt_and_checksum_changes_deny(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(state.StateRejected):
                state.read_snapshot(Path(directory) / "missing", tenant_id="tenant-a", now=T0)
        raw = self.encode()
        for bad in (b"", b"{}", raw[:-1], raw.replace(b'"interval":8.0', b'"interval":9.0'), b"\xff"):
            with self.subTest(raw=bad[:20]), self.assertRaises(state.StateRejected):
                self.decode(bad)

    def test_duplicate_keys_unknown_version_and_unknown_fields_deny(self):
        raw = self.encode().replace(b'"version":1', b'"version":1,"version":1')
        variants = [raw, self.altered(lambda p: p.update(version=2)),
                    self.altered(lambda p: p.update(version=True)),
                    self.altered(lambda p: p.update(extra=1)),
                    self.altered(lambda p: p["states"]["example.test:443"].update(extra=1))]
        for bad in variants:
            with self.subTest(raw=bad[:20]), self.assertRaises(state.StateRejected):
                self.decode(bad)

    def test_nonfinite_negative_bool_and_oversized_numbers_deny(self):
        for interval in (float("nan"), float("inf"), -1, True, 10 ** 1000):
            with self.subTest(interval_type=type(interval)), self.assertRaises(state.StateRejected):
                self.encode({"host": replace(self.row, interval=interval)})
        for value in (-1, True, state.MAX_COUNTER + 1, 1.5):
            with self.subTest(counter=value), self.assertRaises(state.StateRejected):
                self.encode({"host": replace(self.row, total_requests=value)})
        with self.assertRaises(state.StateRejected):
            self.encode({"host": replace(self.row, consecutive_failures=4)})
        with self.assertRaises(state.StateRejected):
            self.decode(self.encode().replace(b'"interval":8.0', b'"interval":NaN'))

    def test_limits_never_silently_evict_hosts(self):
        with self.assertRaises(state.StateRejected):
            self.encode({f"host-{i}": self.row for i in range(state.MAX_HOSTS + 1)})
        with self.assertRaises(state.StateRejected):
            self.encode({"x" * 254: self.row})
        with self.assertRaises(state.StateRejected):
            self.decode(b" " * (state.MAX_BYTES + 1))
        with patch.object(state, "MAX_BYTES", 128):
            with self.assertRaises(state.StateRejected):
                self.encode()

    def test_future_request_and_wait_beyond_ttl_deny(self):
        for row in (replace(self.row, last_request_at=T0 + timedelta(seconds=1)),
                    replace(self.row, circuit_open_until=T0 + timedelta(hours=2)),
                    replace(self.row, interval=4000)):
            with self.subTest(row=row), self.assertRaises(state.StateRejected):
                self.encode({"host": row})
        with self.assertRaises(state.StateRejected):
            state.encode_snapshot("tenant-a", {}, now=T0,
                                  expires_at=T0 + timedelta(seconds=state.MAX_RETENTION_SECONDS + 1))

    def test_disk_atomic_write_readback_private_mode_and_integer_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pacing.json"
            rows = {"host": replace(self.row, interval=8)}
            result = state.write_snapshot(path, "tenant-a", rows, now=T0,
                                          expires_at=T0 + timedelta(hours=1))
            self.assertEqual(result.states, rows)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(state.read_snapshot(path, tenant_id="tenant-a", now=T0).states, rows)
            self.assertEqual(list(Path(directory).glob(".pacing-*")), [])

    def test_write_failure_does_not_return_success_or_leave_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pacing.json"
            with patch.object(state.os, "replace", side_effect=OSError("offline failure")):
                with self.assertRaises(state.StateRejected):
                    state.write_snapshot(path, "tenant-a", self.rows, now=T0,
                                         expires_at=T0 + timedelta(hours=1))
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_post_replace_fsync_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pacing.json"
            with patch.object(state.os, "fsync", side_effect=[None, OSError("offline directory failure")]):
                with self.assertRaises(state.StateRejected):
                    state.write_snapshot(path, "tenant-a", self.rows, now=T0,
                                         expires_at=T0 + timedelta(hours=1))
            self.assertTrue(path.exists())

    def test_symlink_and_nonregular_reads_deny(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_bytes(self.encode())
            link = Path(directory) / "link"
            link.symlink_to(target)
            for path in (link, Path(directory)):
                with self.subTest(path=path), self.assertRaises(state.StateRejected):
                    state.read_snapshot(path, tenant_id="tenant-a", now=T0)

    def test_readback_mismatch_denies(self):
        with tempfile.TemporaryDirectory() as directory:
            altered = state.RestoredSnapshot("tenant-a", T0, T0 + timedelta(hours=1), {})
            with patch.object(state, "read_snapshot", return_value=altered):
                with self.assertRaises(state.StateRejected):
                    state.write_snapshot(Path(directory) / "pacing", "tenant-a", self.rows,
                                         now=T0, expires_at=T0 + timedelta(hours=1))
