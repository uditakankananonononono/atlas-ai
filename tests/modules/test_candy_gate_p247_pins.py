"""P247 candy gate pins (test-only; core frozen).

Loads the module by file path (instinct_doc has no __init__.py). Pins:
(1) checked_at length 40 accepted / 41 INVALID, lowercase 'z' and uppercase 'Z' suffix GREEN;
(2) max_age_days 1 and 3650 accepted, 0 and 3651 refused with the exact message;
(3) now that is not a datetime raises the exact ValueError;
(4) naive now / now with utcoffset() None refuse, naive checked_at is INVALID.
The 40/41 pins use fractional seconds longer than 6 digits, which datetime.fromisoformat
accepts only on Python >= 3.11, so they skip below 3.11 rather than guess.
"""
import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / "backend/app/modules/instinct_doc/candy_gate_p247.py"
_spec = importlib.util.spec_from_file_location("candy_gate_p247_pins_under_test", MOD_PATH)
g = importlib.util.module_from_spec(_spec)
sys.modules["candy_gate_p247_pins_under_test"] = g
_spec.loader.exec_module(g)

NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
FRESH = {"id": "f", "kind": "fresh_within", "max_age_days": 7}


def run(ts, now=NOW):
    r = g.evaluate({"gates": [FRESH]}, {"f": {"checked_at": ts}}, now=now)
    return r, r["gates"][0]


needs311 = pytest.mark.skipif(sys.version_info < (3, 11), reason="long fractional seconds parse only on >= 3.11")


# ---- group 1: checked_at 40 / 41 characters, z / Z ----

@needs311
def test_checked_at_exactly_40_chars_parses():
    ts = "2026-10-11T11:00:00." + "0" * 14 + "+00:00"
    assert len(ts) == 40
    r, st = run(ts)
    assert (st["state"], st["reason"]) == ("GREEN", "declared_condition_met") and r["release"] is True


@needs311
def test_checked_at_41_chars_is_invalid_even_though_it_parses():
    ts = "2026-10-11T11:00:00." + "0" * 15 + "+00:00"
    assert len(ts) == 41
    assert datetime.fromisoformat(ts).utcoffset() is not None  # parseable, so only the length rule refuses it
    r, st = run(ts)
    assert (st["state"], st["reason"]) == ("INVALID", "invalid_observation:checked_at") and r["release"] is False
    assert g.MAX_DATE_TEXT == 40


@needs311
def test_checked_at_40_and_41_with_z_suffix():
    ok = "2026-10-11T11:00:00." + "0" * 19 + "Z"
    bad = "2026-10-11T11:00:00." + "0" * 20 + "Z"
    assert (len(ok), len(bad)) == (40, 41)
    assert run(ok)[1]["state"] == "GREEN"
    st = run(bad)[1]
    assert (st["state"], st["reason"]) == ("INVALID", "invalid_observation:checked_at")


@pytest.mark.parametrize("suffix", ["Z", "z"])
def test_z_suffix_either_case_is_green(suffix):
    r, st = run("2026-10-11T11:00:00" + suffix)
    assert (st["state"], st["reason"]) == ("GREEN", "declared_condition_met") and r["release"] is True


def test_z_suffix_means_utc_exactly():
    # one second inside / outside the 7 day window proves 'z' is read as +00:00, not shifted
    edge = NOW - timedelta(days=7)
    assert run(edge.strftime("%Y-%m-%dT%H:%M:%S") + "z")[1]["state"] == "GREEN"
    st = run((edge - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S") + "z")[1]
    assert (st["state"], st["reason"]) == ("RED", "stale")


# ---- group 2: max_age_days 1 and 3650 accepted, 0 and 3651 refused ----

@pytest.mark.parametrize("n", [1, 3650])
def test_max_age_days_edges_accepted(n):
    assert g.MAX_AGE_DAYS_CEILING == 3650
    r = g.evaluate({"gates": [{"id": "a", "kind": "fresh_within", "max_age_days": n}]},
                   {"a": {"checked_at": NOW.isoformat()}}, now=NOW)
    assert r["release"] is True


def test_max_age_days_edges_change_the_window():
    one = {"id": "a", "kind": "fresh_within", "max_age_days": 1}
    top = {"id": "a", "kind": "fresh_within", "max_age_days": 3650}
    day = (NOW - timedelta(days=1)).isoformat()
    over = (NOW - timedelta(days=1, seconds=1)).isoformat()
    assert g.evaluate({"gates": [one]}, {"a": {"checked_at": day}}, now=NOW)["release"] is True
    assert g.evaluate({"gates": [one]}, {"a": {"checked_at": over}}, now=NOW)["gates"][0]["reason"] == "stale"
    assert g.evaluate({"gates": [top]}, {"a": {"checked_at": (NOW - timedelta(days=3650)).isoformat()}}, now=NOW)["release"] is True


@pytest.mark.parametrize("n", [0, 3651, -1])
def test_max_age_days_outside_range_refused_exact(n):
    with pytest.raises(ValueError) as e:
        g.evaluate({"gates": [{"id": "a", "kind": "fresh_within", "max_age_days": n}]}, {}, now=NOW)
    assert str(e.value) == "gate a max_age_days must be an integer from 1 to 3650"


# ---- group 3: now that is not a datetime ----

@pytest.mark.parametrize("bad", ["2026-10-11T12:00:00+00:00", 1760184000, 1.5, 0, "", [], {}, True])
def test_now_must_be_a_datetime_exact(bad):
    with pytest.raises(ValueError) as e:
        g.evaluate({"gates": [FRESH]}, {}, now=bad)
    assert str(e.value) == "now must be a timezone-aware datetime"


def test_now_checked_even_without_fresh_gates():
    with pytest.raises(ValueError) as e:
        g.evaluate({"gates": [{"id": "n", "kind": "count_equals", "expected": 1}]}, {}, now="x")
    assert str(e.value) == "now must be a timezone-aware datetime"
    assert g.evaluate({"gates": [{"id": "n", "kind": "count_equals", "expected": 1}]}, {"n": {"count": 1}}, now=None)["release"] is True


# ---- group 4: naive / utcoffset-none now refuses; naive checked_at is INVALID ----

class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None

    def tzname(self, dt):
        return None


def test_naive_now_refused_exact():
    with pytest.raises(ValueError) as e:
        g.evaluate({"gates": [FRESH]}, {}, now=datetime(2026, 10, 11, 12, 0, 0))
    assert str(e.value) == "now must be a timezone-aware datetime"


def test_now_with_tzinfo_but_no_utcoffset_refused_exact():
    now = datetime(2026, 10, 11, 12, 0, 0, tzinfo=_NoOffset())
    assert now.tzinfo is not None and now.utcoffset() is None
    with pytest.raises(ValueError) as e:
        g.evaluate({"gates": [FRESH]}, {}, now=now)
    assert str(e.value) == "now must be a timezone-aware datetime"


@pytest.mark.parametrize("ts", ["2026-10-11T11:00:00", "2026-10-11T11:00:00.123456", "2026-10-11 11:00:00", "2026-10-11"])
def test_naive_checked_at_is_invalid_never_green(ts):
    r, st = run(ts)
    assert (st["state"], st["reason"]) == ("INVALID", "invalid_observation:checked_at")
    assert r["release"] is False and r["blocked_by"] == ["f"]
