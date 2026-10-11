"""Unit 14 University-fit filter over a USER-SUPPLIED table (stdlib only).

The module is loaded by file path so the package __init__ (and third-party
imports) are not needed. It never fetches data and never claims admission odds.
"""
import copy
import importlib.util
import itertools
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD_DIR = ROOT / "backend/app/modules/m23_study_abroad"
MOD_PATH = MOD_DIR / "university_fit.py"
SCHEMA_PATH = MOD_DIR / "university_fit_schema.json"


def _load(path=MOD_PATH, name="university_fit"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


uf = _load()
NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
URL = "https://example.edu/aid"


def row(name="Alpha U", country="US", **over):
    r = {"university": name, "country": country, "source_url": URL,
         "checked_at": "2026-10-01T00:00:00+00:00", "intl_ug_aid": "full",
         "additional_written_test": "no", "sat": "optional", "ielts_accepted": "yes"}
    r.update(over)
    return r


PROFILE = {"has_sat": True}


def ev(rows, profile=None, now=NOW, **kw):
    return uf.evaluate(rows, PROFILE if profile is None else profile, now, **kw)


def only(res):
    assert len(res["rows"]) == 1
    return res["rows"][0]


# ---------------- basic verdicts ----------------
def test_fits_when_all_criteria_met_and_fresh():
    r = only(ev([row()]))
    assert r["verdict"] == "fits" and r["reasons"] == []
    assert r["source_url"] == URL and r["checked_at"] == "2026-10-01T00:00:00+00:00"
    assert r["age_days"] == pytest.approx(10.5)


@pytest.mark.parametrize("over,reason", [
    ({"intl_ug_aid": "partial"}, "aid_not_full"),
    ({"intl_ug_aid": "none"}, "aid_not_full"),
    ({"additional_written_test": "yes"}, "additional_written_test_required"),
    ({"sat": "required"}, None),  # profile has SAT here: fits
    ({"ielts_accepted": "no"}, "ielts_not_accepted"),
])
def test_single_criterion_failures(over, reason):
    r = only(ev([row(**over)], {"has_sat": True, "ielts": "yes"}))
    if reason is None:
        assert r["verdict"] == "fits"
    else:
        assert r["verdict"] == "does_not_fit" and r["reasons"] == [reason]


def test_sat_required_without_profile_sat():
    r = only(ev([row(sat="required")], {"has_sat": False}))
    assert r["verdict"] == "does_not_fit" and r["reasons"] == ["sat_required_profile_has_none"]
    assert only(ev([row(sat="optional")], {"has_sat": False}))["verdict"] == "fits"
    assert only(ev([row(sat="not_considered")], {"has_sat": False}))["verdict"] == "fits"


def test_reason_order_is_fixed():
    r = only(ev([row(intl_ug_aid="none", additional_written_test="yes", sat="required", ielts_accepted="no")],
                {"has_sat": False, "ielts": "yes"}))
    assert r["reasons"] == ["aid_not_full", "additional_written_test_required",
                            "sat_required_profile_has_none", "ielts_not_accepted"]


def test_profile_flags_can_disable_criteria():
    rr = row(intl_ug_aid="partial", additional_written_test="yes")
    assert only(ev([rr], {"has_sat": True, "require_full_aid": False, "forbid_additional_written_test": False}))["verdict"] == "fits"
    assert only(ev([rr], {"has_sat": True, "require_full_aid": False}))["reasons"] == ["additional_written_test_required"]
    assert only(ev([rr], {"has_sat": True, "forbid_additional_written_test": False}))["reasons"] == ["aid_not_full"]


def test_ielts_profile_values():
    no_ielts = row(ielts_accepted="no")
    assert only(ev([no_ielts], {"has_sat": True, "ielts": "no"}))["verdict"] == "fits"
    assert only(ev([no_ielts], {"has_sat": True, "ielts": "maybe"}))["reasons"] == ["ielts_not_accepted"]
    assert only(ev([no_ielts], {"has_sat": True}))["reasons"] == ["ielts_not_accepted"]  # default maybe
    assert only(ev([no_ielts], {"has_sat": True, "ielts": "yes"}))["reasons"] == ["ielts_not_accepted"]


def oracle(aid, written, sat, ielts_acc, has_sat, ielts):
    reasons = []
    if aid != "full": reasons.append("aid_not_full")
    if written == "yes": reasons.append("additional_written_test_required")
    if sat == "required" and not has_sat: reasons.append("sat_required_profile_has_none")
    if ielts_acc == "no" and ielts != "no": reasons.append("ielts_not_accepted")
    return ("fits" if not reasons else "does_not_fit"), reasons


def test_exhaustive_oracle_all_216_combinations():
    n = 0
    for aid, written, sat, acc, has_sat, ielts in itertools.product(
            ["full", "partial", "none"], ["yes", "no"], ["required", "optional", "not_considered"],
            ["yes", "no"], [True, False], ["yes", "no", "maybe"]):
        r = only(ev([row(intl_ug_aid=aid, additional_written_test=written, sat=sat, ielts_accepted=acc)],
                    {"has_sat": has_sat, "ielts": ielts}))
        assert (r["verdict"], r["reasons"]) == oracle(aid, written, sat, acc, has_sat, ielts)
        n += 1
    assert n == 216


# ---------------- freshness and source (per row) ----------------
def test_age_boundary_exact_days():
    exactly = (NOW - timedelta(days=180)).isoformat()
    over = (NOW - timedelta(days=180, seconds=1)).isoformat()
    assert only(ev([row(checked_at=exactly)]))["verdict"] == "fits"
    r = only(ev([row(checked_at=over)]))
    assert r["verdict"] == "unverified" and r["reasons"] == ["stale"]
    assert only(ev([row(checked_at=over)], max_age_days=181))["verdict"] == "fits"


def test_future_and_exact_now():
    assert only(ev([row(checked_at=NOW.isoformat())]))["verdict"] == "fits"
    r = only(ev([row(checked_at=(NOW + timedelta(seconds=1)).isoformat())]))
    assert r["verdict"] == "unverified" and r["reasons"] == ["checked_at_future"]


@pytest.mark.parametrize("val,reason", [
    (None, "checked_at_missing"), ("", "checked_at_missing"), ("   ", "checked_at_missing"),
    ("2026-10-01T00:00:00", "checked_at_naive"), ("2026-10-01", "checked_at_naive"),
    ("last week", "checked_at_invalid"), (20261001, "checked_at_invalid"), ("2026-13-01T00:00:00Z", "checked_at_invalid"),
    ("2026-10-01T00:00:00Z" + "x" * 60, "checked_at_invalid"),
])
def test_bad_dates_are_unverified_never_fit(val, reason):
    r = only(ev([row(checked_at=val)]))
    assert r["verdict"] == "unverified" and r["reasons"] == [reason]


def test_z_suffix_and_offsets_accepted_and_normalised():
    r = only(ev([row(checked_at="2026-10-01T05:30:00+05:30")]))
    assert r["verdict"] == "fits" and r["checked_at"] == "2026-10-01T00:00:00+00:00"
    assert only(ev([row(checked_at="2026-10-01T00:00:00Z")]))["verdict"] == "fits"


@pytest.mark.parametrize("val,reason", [
    (None, "source_url_missing"), ("", "source_url_missing"),
    ("http://example.edu/aid", "source_url_invalid"), ("https://", "source_url_invalid"),
    ("example.edu/aid", "source_url_invalid"), ("https://u:p@example.edu/", "source_url_invalid"),
    ("https://exa mple.edu/", "source_url_invalid"), ("https://example.edu/" + "a" * 2100, "source_url_invalid"),
    (5, "source_url_invalid"),
])
def test_bad_sources_are_unverified(val, reason):
    r = only(ev([row(source_url=val)]))
    assert r["verdict"] == "unverified" and r["reasons"] == [reason]


def test_unverified_beats_criteria_failure_and_lists_all_problems():
    r = only(ev([row(source_url=None, checked_at=None, intl_ug_aid="none")]))
    assert r["verdict"] == "unverified"
    assert r["reasons"] == ["source_url_missing", "checked_at_missing"]


def test_missing_and_invalid_fields_are_unverified():
    bad = row(); del bad["sat"]
    assert only(ev([bad])) ["reasons"] == ["missing_field:sat"]
    assert only(ev([row(intl_ug_aid="maybe")]))["reasons"] == ["invalid_value:intl_ug_aid"]
    assert only(ev([row(additional_written_test=True)]))["reasons"] == ["invalid_value:additional_written_test"]
    assert only(ev([row(ielts_accepted="YES")]))["reasons"] == ["invalid_value:ielts_accepted"]
    assert only(ev([row(sat="maybe")]))["reasons"] == ["invalid_value:sat"]


@pytest.mark.parametrize("field", ["acceptance_probability", "rank", "score", "essay", "user_id"])
def test_unsupported_row_fields_unverified(field):
    r = only(ev([row(**{field: 1})]))
    assert r["verdict"] == "unverified" and r["reasons"] == [f"unsupported_field:{field}"]


# ---------------- batch-level errors (exact) ----------------
def test_batch_errors_exact():
    with pytest.raises(ValueError, match=r"^rows must be a list$"):
        ev("abc")
    with pytest.raises(ValueError, match=r"^row 1 must be an object$"):
        ev([row(), 5])
    with pytest.raises(ValueError, match=r"^row 0 needs a non-empty university and country$"):
        ev([row(name="")])
    with pytest.raises(ValueError, match=r"^row 0 needs a non-empty university and country$"):
        ev([row(country=None)])
    with pytest.raises(ValueError, match=r"^duplicate row Alpha U \(US\)$"):
        ev([row(), row()])
    with pytest.raises(ValueError, match=r"^now must be a timezone-aware datetime$"):
        ev([row()], now=datetime(2026, 10, 11))
    with pytest.raises(ValueError, match=r"^now must be a timezone-aware datetime$"):
        ev([row()], now="2026-10-11")
    for bad in (0, -1, 3651, 1.5, True, "9"):
        with pytest.raises(ValueError, match=r"^max_age_days must be an integer from 1 to 3650$"):
            ev([row()], max_age_days=bad)
    assert only(ev([row()], max_age_days=3650))["verdict"] == "fits"
    assert only(ev([row()], max_age_days=1))["reasons"] == ["stale"]


def test_profile_errors_exact():
    with pytest.raises(ValueError, match=r"^profile must be an object$"):
        uf.evaluate([row()], None, NOW)
    with pytest.raises(ValueError, match=r"^profile needs has_sat$"):
        uf.evaluate([row()], {}, NOW)
    for k in ("has_sat", "require_full_aid", "forbid_additional_written_test"):
        p = {"has_sat": True}; p[k] = "yes"
        with pytest.raises(ValueError, match=rf"^profile.{k} must be true or false$"):
            uf.evaluate([row()], p, NOW)
    with pytest.raises(ValueError, match=r"^profile.ielts must be one of yes, no, maybe$"):
        uf.evaluate([row()], {"has_sat": True, "ielts": "sometimes"}, NOW)
    for key in ("gpa", "marks", "cbse", "income", "nationality"):
        with pytest.raises(ValueError, match=rf"^profile has unsupported field {key}$"):
            uf.evaluate([row()], {"has_sat": True, key: 1}, NOW)


def test_row_bounds_exact_N_and_N_plus_1():
    assert uf.MAX_ROWS == 2000
    ok = [row(name=f"U{i:04d}") for i in range(2000)]
    res = ev(ok)
    assert res["counts"]["rows"] == 2000
    with pytest.raises(ValueError, match=r"^at most 2000 rows are allowed, got 2001$"):
        ev(ok + [row(name="extra")])
    assert ev([])["rows"] == [] and ev([])["counts"]["rows"] == 0


# ---------------- determinism, immutability, output contract ----------------
def test_unsorted_input_determinism_all_permutations():
    base = [row(name="C U"), row(name="A U", intl_ug_aid="none"), row(name="B U", source_url=None), row(name="A U", country="CA")]
    ref = ev(base)
    for perm in itertools.permutations(base):
        assert ev(list(perm)) == ref
    assert [(r["university"], r["country"]) for r in ref["rows"]] == [("A U", "CA"), ("A U", "US"), ("B U", "US"), ("C U", "US")]


def test_counts_and_limits_and_gaps_declared():
    res = ev([row(name="A"), row(name="B", intl_ug_aid="none"), row(name="C", source_url=None)])
    assert res["counts"] == {"rows": 3, "fits": 1, "does_not_fit": 1, "unverified": 1}
    assert "supplied" in res["method_limits"] and "no admission" in res["method_limits"]
    assert res["data_provenance"] == "caller-supplied table; not verified by this module"


def test_input_not_mutated():
    rows = [row(name="B"), row(name="A", intl_ug_aid="none")]; p = {"has_sat": True}
    r0, p0 = copy.deepcopy(rows), copy.deepcopy(p)
    ev(rows, p)
    assert rows == r0 and p == p0


def test_whitespace_in_names_normalised_for_duplicates():
    with pytest.raises(ValueError, match=r"^duplicate row Alpha U \(US\)$"):
        ev([row(name="Alpha U"), row(name="  Alpha U ", country=" US")])


def test_no_network_or_third_party_imports():
    text = MOD_PATH.read_text()
    for banned in ("import requests", "import httpx", "urllib.request", "socket", "subprocess", "open(", "import app", "fastapi"):
        assert banned not in text.replace("SCHEMA_PATH.read_text", "")


# ---------------- schema file ----------------
def test_schema_file_is_valid_json_and_drives_enums():
    s = json.loads(SCHEMA_PATH.read_text())
    assert s["schema_version"] == 1
    assert s["row"]["enums"] == {"intl_ug_aid": ["full", "partial", "none"], "additional_written_test": ["yes", "no"],
                                 "sat": ["required", "optional", "not_considered"], "ielts_accepted": ["yes", "no"]}
    assert s["profile"]["enums"] == {"ielts": ["yes", "no", "maybe"]}
    assert s["limits"] == {"max_rows": 2000, "default_max_age_days": 180, "max_age_days_ceiling": 3650}
    assert uf.MAX_ROWS == 2000 and uf.DEFAULT_MAX_AGE_DAYS == 180 and uf.MAX_AGE_DAYS_CEILING == 3650


def test_schema_enum_change_changes_behaviour(tmp_path):
    d = tmp_path / "m"; d.mkdir()
    s = json.loads(SCHEMA_PATH.read_text()); s["row"]["enums"]["sat"].append("sometimes")
    (d / "university_fit_schema.json").write_text(json.dumps(s))
    (d / "university_fit.py").write_text(MOD_PATH.read_text())
    m2 = _load(d / "university_fit.py", "university_fit_alt")
    assert m2.evaluate([row(sat="sometimes")], PROFILE, NOW)["rows"][0]["verdict"] == "fits"
    assert uf.evaluate([row(sat="sometimes")], PROFILE, NOW)["rows"][0]["reasons"] == ["invalid_value:sat"]


# ---------------- independent mutants ----------------
def _mutant(name, old, new):
    src = MOD_PATH.read_text()
    assert old in src, f"mutant {name}: anchor missing"
    d = pathlib.Path(__import__("tempfile").mkdtemp())
    (d / "university_fit_schema.json").write_text(SCHEMA_PATH.read_text())
    (d / "university_fit.py").write_text(src.replace(old, new, 1))
    return _load(d / "university_fit.py", f"uf_mut_{name}")


from datetime import tzinfo as _tzinfo


class _NoOffset(_tzinfo):
    """tzinfo that is present but reports no UTC offset (datetime then counts as naive)."""
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None

    def tzname(self, dt):
        return None


def _url_of_len(n):
    prefix = "https://example.edu/"
    return prefix + "a" * (n - len(prefix))


def _kill_checks(m):
    """Independent checks, each run on its own. Each returns True when it detects a mismatch."""
    def e(rows, profile=None, now=NOW, **kw):
        return m.evaluate(rows, PROFILE if profile is None else profile, now, **kw)

    def r0(rows, **kw):
        return e(rows, **kw)["rows"][0]

    def oracle_sweep():
        for aid, written, sat, acc, has_sat, ielts in itertools.product(
                ["full", "partial", "none"], ["yes", "no"], ["required", "optional", "not_considered"],
                ["yes", "no"], [True, False], ["yes", "no", "maybe"]):
            r = r0([row(intl_ug_aid=aid, additional_written_test=written, sat=sat, ielts_accepted=acc)], profile={"has_sat": has_sat, "ielts": ielts})
            if (r["verdict"], r["reasons"]) != oracle(aid, written, sat, acc, has_sat, ielts):
                return True
        return False

    def raises(fn):
        try:
            fn()
        except ValueError:
            return False
        return True

    ts = lambda **kw: (NOW - timedelta(**kw)).isoformat()
    checks = {
        "oracle_sweep": oracle_sweep,
        "age_exact_fresh": lambda: r0([row(checked_at=ts(days=180))])["verdict"] != "fits",
        "age_plus_1s_stale": lambda: r0([row(checked_at=ts(days=180, seconds=1))])["reasons"] != ["stale"],
        "now_exact_fresh": lambda: r0([row(checked_at=NOW.isoformat())])["verdict"] != "fits",
        "future_1s": lambda: r0([row(checked_at=(NOW + timedelta(seconds=1)).isoformat())])["reasons"] != ["checked_at_future"],
        "naive_old": lambda: r0([row(checked_at="2026-10-01T00:00:00")])["reasons"] != ["checked_at_naive"],
        "naive_recent": lambda: r0([row(checked_at="2026-10-11T11:00:00")])["reasons"] != ["checked_at_naive"],
        "http_scheme": lambda: r0([row(source_url="http://example.edu/")])["reasons"] != ["source_url_invalid"],
        "userinfo": lambda: r0([row(source_url="https://u:p@example.edu/")])["reasons"] != ["source_url_invalid"],
        "port_bad_text": lambda: r0([row(source_url="https://example.edu:bad/path")])["reasons"] != ["source_url_invalid"],
        "port_too_big": lambda: r0([row(source_url="https://example.edu:99999/path")])["reasons"] != ["source_url_invalid"],
        "port_65536": lambda: r0([row(source_url="https://example.edu:65536/")])["reasons"] != ["source_url_invalid"],
        "port_zero": lambda: r0([row(source_url="https://example.edu:0/")])["reasons"] != ["source_url_invalid"],
        "port_65535_ok": lambda: r0([row(source_url="https://example.edu:65535/")])["verdict"] != "fits",
        "port_1_ok": lambda: r0([row(source_url="https://example.edu:1/")])["verdict"] != "fits",
        "unverified_priority": lambda: r0([row(source_url=None, checked_at=None, intl_ug_aid="none")])["verdict"] != "unverified",
        "unverified_bad_field_priority": lambda: r0([row(intl_ug_aid="maybe")])["verdict"] != "unverified",
        "url_len_2048_ok": lambda: r0([row(source_url=_url_of_len(2048))])["verdict"] != "fits",
        "url_len_2049_bad": lambda: r0([row(source_url=_url_of_len(2049))])["reasons"] != ["source_url_invalid"],
        "url_no_host_with_port": lambda: r0([row(source_url="https://:443/x")])["reasons"] != ["source_url_invalid"],
        "date_padded_stripped_first": lambda: r0([row(checked_at=" " * 20 + "2026-10-01T00:00:00.123456+05:30" + " " * 20)])["verdict"] != "fits",
        "date_33_chars_invalid": lambda: r0([row(checked_at="2026-10-01T00:00:00.123456+05:30" + "0")])["reasons"] != ["checked_at_invalid"],
        "now_tz_without_offset": lambda: raises(lambda: e([row()], now=datetime(2026, 10, 11, tzinfo=_NoOffset()))),
        "age_days_rounding_6": lambda: [r0([row(checked_at=ts(days=1, seconds=1))])["age_days"], r0([row(checked_at=ts(seconds=1))])["age_days"],
                                        r0([row(checked_at=ts(days=2, microseconds=1))])["age_days"]] != [1.000012, 0.000012, 2.0],
        "empty_port_accepted_pin": lambda: r0([row(source_url="https://example.edu:/x")])["verdict"] != "fits",
        "unsupported_field": lambda: r0([row(rank=1)])["reasons"] != ["unsupported_field:rank"],
        "sorted": lambda: e([row(name="B"), row(name="A")])["rows"][0]["university"] != "A",
        "rows_2001": lambda: raises(lambda: e([row(name=f"U{i}") for i in range(2001)])),
        "rows_2000_ok": lambda: len(e([row(name=f"U{i}") for i in range(2000)])["rows"]) != 2000,
        "dup": lambda: raises(lambda: e([row(), row()])),
        "max_age_3651": lambda: raises(lambda: e([row()], max_age_days=3651)),
        "now_naive": lambda: raises(lambda: e([row()], now=datetime(2026, 10, 11))),
        "profile_gpa": lambda: raises(lambda: e([row()], {"has_sat": True, "gpa": 3})),
        "profile_has_sat_str": lambda: raises(lambda: e([row()], {"has_sat": "yes"})),
    }
    return checks


def _kill_kind(m):
    """'assert' if any check detects a behavioural mismatch; else 'error:<Type>' if only crashes; else None."""
    errors = []
    for name, fn in _kill_checks(m).items():
        try:
            if fn():
                return "assert"
        except Exception as exc:  # a crash proves error detection, not an assertion
            errors.append(type(exc).__name__)
    return ("error:" + sorted(set(errors))[0]) if errors else None


def _killed(m):
    return _kill_kind(m) is not None


MUTANTS = [
    ("aid_check_dropped", "if prof['require_full_aid'] and aid != 'full':", "if False:"),
    ("aid_partial_ok", "aid != 'full'", "aid == 'none'"),
    ("written_dropped", "if prof['forbid_additional_written_test'] and written == 'yes':", "if False:"),
    ("sat_check_dropped", "if sat == 'required' and not prof['has_sat']:", "if False:"),
    ("sat_inverted", "not prof['has_sat']", "prof['has_sat']"),
    ("ielts_ignores_profile", "ielts_acc == 'no' and prof['ielts'] != 'no'", "ielts_acc == 'no'"),
    ("ielts_maybe_exempt", "prof['ielts'] != 'no'", "prof['ielts'] == 'yes'"),
    ("age_ge", "age > timedelta(days=max_age_days)", "age >= timedelta(days=max_age_days)"),
    ("future_allowed", "if checked > now:", "if False:"),
    ("naive_allowed", "if dt.tzinfo is None or dt.utcoffset() is None:", "if False:"),
    ("http_allowed", "parts.scheme != 'https'", "parts.scheme not in ('http', 'https')"),
    ("userinfo_allowed", "'@' in parts.netloc", "False"),
    ("unverified_not_priority", "if problems:", "if False:"),
    ("unsupported_field_ignored", "for k in sorted(r, key=str):\n        if k not in allowed:", "for k in []:\n        if k not in allowed:"),
    ("no_sort", "out.sort(key=lambda x: (x['university'], x['country']))", "pass"),
    ("max_rows_off", "MAX_ROWS = _S['limits']['max_rows']", "MAX_ROWS = _S['limits']['max_rows'] + 1"),
    ("dup_allowed", "if key in seen:", "if False:"),
    ("age_ceiling_off", "or not 1 <= max_age_days <= MAX_AGE_DAYS_CEILING", "or not 1 <= max_age_days <= MAX_AGE_DAYS_CEILING + 1"),
    ("fits_when_reasons", "'fits' if not reasons else 'does_not_fit'", "'fits'"),
    ("port_range_unchecked", "if port is not None and not 1 <= port <= 65535:", "if False:"),
    ("port_valueerror_ignored", "    try:\n        port = parts.port\n    except ValueError:\n        return 'source_url_invalid'\n", "    port = None\n"),
    ("port_zero_ok", "not 1 <= port <= 65535", "not 0 <= port <= 65535"),
    ("url_len_ge", "len(raw) > MAX_URL", "len(raw) >= MAX_URL"),
    ("url_len_gt_plus1", "len(raw) > MAX_URL", "len(raw) > MAX_URL + 1"),
    ("url_scheme_arm_dropped", "parts.scheme != 'https' or ", ""),
    ("url_hostname_arm_dropped", "or not parts.hostname:", ":"),
    ("url_scheme_netloc_or_to_and", "parts.scheme != 'https' or not parts.netloc", "parts.scheme != 'https' and not parts.netloc"),
    ("url_netloc_hostname_or_to_and", "not parts.netloc or not parts.hostname", "not parts.netloc and not parts.hostname"),
    ("date_len_checked_before_strip", "    s = raw.strip()\n    if len(s) > MAX_DATE_TEXT:", "    s = raw.strip()\n    if len(raw) > MAX_DATE_TEXT:"),
    ("date_len_limit_32", "MAX_DATE_TEXT = 40", "MAX_DATE_TEXT = 31"),
    ("now_tz_or_to_and", "now.tzinfo is None or now.utcoffset() is None:\n        raise ValueError('now must", "now.tzinfo is None and now.utcoffset() is None:\n        raise ValueError('now must"),
    ("now_offset_arm_dropped", "or now.tzinfo is None or now.utcoffset() is None:\n        raise ValueError('now must", "or now.tzinfo is None:\n        raise ValueError('now must"),
    ("age_round_5", "round(age.total_seconds() / 86400, 6)", "round(age.total_seconds() / 86400, 5)"),
    ("age_round_7", "round(age.total_seconds() / 86400, 6)", "round(age.total_seconds() / 86400, 7)"),
    ("age_not_rounded", "round(age.total_seconds() / 86400, 6)", "age.total_seconds() / 86400"),
]


@pytest.mark.parametrize("name,old,new", MUTANTS, ids=[m[0] for m in MUTANTS])
def test_mutant_is_killed(name, old, new):
    assert _killed(_mutant(name, old, new)), f"mutant {name} survived"


def test_negative_control_unmutated_not_killed():
    assert _killed(uf) is False


# =====================================================================
# R2: URL port validation (peer audit defect) and honest kill classes.
# =====================================================================
BAD_PORT_URLS = [
    "https://example.edu:bad/path", "https://example.edu:99999/path", "https://example.edu:65536/",
    "https://example.edu:0/", "https://example.edu:-1/", "https://example.edu:80a/",
    "https://example.edu:+80/", "https://[::1]:99999/", "https://[::1/",
]
GOOD_PORT_URLS = ["https://example.edu:443/aid", "https://example.edu:1/", "https://example.edu:65535/",
                  "https://example.edu:8443/a?b=c#d", "https://[::1]:8443/", "https://example.edu/"]


@pytest.mark.parametrize("url", BAD_PORT_URLS)
def test_r2_bad_port_row_is_unverified_through_full_evaluate(url):
    res = ev([row(source_url=url)])
    r = only(res)
    assert r["verdict"] == "unverified" and r["reasons"] == ["source_url_invalid"]
    assert res["counts"] == {"rows": 1, "fits": 0, "does_not_fit": 0, "unverified": 1}


@pytest.mark.parametrize("url", GOOD_PORT_URLS)
def test_r2_valid_port_row_still_fits(url):
    r = only(ev([row(source_url=url)]))
    assert r["verdict"] == "fits" and r["reasons"] == [] and r["source_url"] == url


def test_r2_bad_port_does_not_hide_a_criteria_failure_as_fit():
    r = only(ev([row(source_url="https://example.edu:99999/", intl_ug_aid="none")]))
    assert r["verdict"] == "unverified"  # unverified takes priority; never judged


def test_r2_every_mutant_is_killed_by_an_assertion_not_a_crash():
    kinds = {name: _kill_kind(_mutant(name, old, new)) for name, old, new in MUTANTS}
    assert {k: v for k, v in kinds.items() if v != "assert"} == {}
    assert _kill_kind(uf) is None


def test_r2_equivalent_mutant_noted():
    # upper-bound 65535 -> 65536 is equivalent here: urllib's parts.port already raises for 65536.
    r = only(ev([row(source_url="https://example.edu:65536/")]))
    assert r["reasons"] == ["source_url_invalid"]


# ---------------- R3: pins named in the peer's second audit ----------------
def test_r3_empty_port_is_accepted_documented_residual():
    # RESIDUAL (named, not a blocker): "https://example.edu:/x" has an empty port. RFC 3986 allows an
    # empty port and it means the scheme default (443). urllib reports port None, so the row is accepted.
    # No core tightening in R3; this test documents the current behaviour only.
    r = only(ev([row(source_url="https://example.edu:/x")]))
    assert r["verdict"] == "fits" and r["source_url"] == "https://example.edu:/x"


def test_r3_url_length_2048_accepted_2049_rejected():
    assert uf.MAX_URL == 2048
    ok, bad = _url_of_len(2048), _url_of_len(2049)
    assert len(ok) == 2048 and len(bad) == 2049
    assert only(ev([row(source_url=ok)]))["verdict"] == "fits"
    r = only(ev([row(source_url=bad)]))
    assert r["verdict"] == "unverified" and r["reasons"] == ["source_url_invalid"]


def test_r3_url_hostname_arm_alone_and_scheme_arm_alone():
    # netloc present but no hostname: only the hostname guard catches it
    r = only(ev([row(source_url="https://:443/x")]))
    assert r["reasons"] == ["source_url_invalid"]
    # valid host, wrong scheme: only the scheme guard catches it
    assert only(ev([row(source_url="http://example.edu/")]))["reasons"] == ["source_url_invalid"]
    assert only(ev([row(source_url="ftp://example.edu/")]))["reasons"] == ["source_url_invalid"]
    # empty netloc
    assert only(ev([row(source_url="https:///x")]))["reasons"] == ["source_url_invalid"]


def test_r3_date_text_limit_with_strip_first():
    assert uf.MAX_DATE_TEXT == 40
    valid32 = "2026-10-01T00:00:00.123456+05:30"
    assert len(valid32) == 32
    assert only(ev([row(checked_at=" " * 20 + valid32 + " " * 20)]))["verdict"] == "fits"  # raw length 72, stripped 32
    for extra in (1, 8, 9, 40):  # stripped lengths 33, 40, 41, 72: all invalid dates
        r = only(ev([row(checked_at=valid32 + "0" * extra)]))
        assert r["verdict"] == "unverified" and r["reasons"] == ["checked_at_invalid"]
    # RESIDUAL: the 40 versus 41 boundary cannot be separated here. On this Python, no valid ISO
    # date text longer than 32 characters parses, so len > 40 and len >= 40 behave the same.


def test_r3_now_with_tzinfo_but_no_offset_refused():
    with pytest.raises(ValueError, match=r"^now must be a timezone-aware datetime$"):
        ev([row()], now=datetime(2026, 10, 11, 12, 0, 0, tzinfo=_NoOffset()))
    with pytest.raises(ValueError, match=r"^now must be a timezone-aware datetime$"):
        ev([row()], now=datetime(2026, 10, 11, 12, 0, 0))


def test_r3_age_days_rounds_to_exactly_six_decimals():
    assert only(ev([row(checked_at=(NOW - timedelta(days=1, seconds=1)).isoformat())]))["age_days"] == 1.000012
    assert only(ev([row(checked_at=(NOW - timedelta(seconds=1)).isoformat())]))["age_days"] == 0.000012
    assert only(ev([row(checked_at=(NOW - timedelta(days=2, microseconds=1)).isoformat())]))["age_days"] == 2.0
    assert only(ev([row(checked_at=(NOW - timedelta(days=3, hours=6)).isoformat())]))["age_days"] == 3.25
    assert only(ev([row(checked_at=(NOW - timedelta(seconds=43200 + 3)).isoformat())]))["age_days"] == 0.500035


# Mutants that are equivalent on this Python/urllib, pinned so a change is noticed.
EQUIVALENT_MUTANTS = [
    ("url_netloc_arm_dropped", "or not parts.netloc or not parts.hostname", "or not parts.hostname"),
    ("date_len_ge_40", "len(s) > MAX_DATE_TEXT", "len(s) >= MAX_DATE_TEXT"),
    ("port_upper_65536", "not 1 <= port <= 65535", "not 1 <= port <= 65536"),
]


@pytest.mark.parametrize("name,old,new", EQUIVALENT_MUTANTS, ids=[m[0] for m in EQUIVALENT_MUTANTS])
def test_r3_equivalent_mutant_survives_by_equivalence(name, old, new):
    assert _kill_kind(_mutant(name, old, new)) is None
