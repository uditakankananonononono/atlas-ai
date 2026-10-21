"""RED-first tests for M04 deterministic result interpretation stats.

Spec: Module 4 - "Results are interpreted and plotted". Row 232 currently only
echoes caller-supplied interpretations. This unit adds a deterministic
descriptive-statistics fallback, honestly labelled as heuristic derivation -
not causal inference and not LLM-quality interpretation.
"""

import pytest

from app.modules.m04_research_scientist.stats import descriptive_stats


def test_descriptive_stats_basic_series():
    stats = descriptive_stats({"accuracy": [0.8, 0.9, 1.0]})
    assert stats["accuracy"]["n"] == 3
    assert stats["accuracy"]["mean"] == pytest.approx(0.9)
    assert stats["accuracy"]["min"] == 0.8
    assert stats["accuracy"]["max"] == 1.0


def test_descriptive_stats_scalar_normalised_to_single_series():
    stats = descriptive_stats({"accuracy": 0.91})
    assert stats["accuracy"] == {"n": 1, "mean": 0.91, "min": 0.91, "max": 0.91}


def test_descriptive_stats_deterministic_and_non_mutating():
    results = {"a": [1, 2, 3], "b": [4]}
    snapshot = {"a": [1, 2, 3], "b": [4]}
    first = descriptive_stats(results)
    second = descriptive_stats(results)
    assert first == second
    assert results == snapshot


def test_descriptive_stats_rejects_empty_and_non_dict():
    with pytest.raises(ValueError):
        descriptive_stats({})
    with pytest.raises(ValueError):
        descriptive_stats([1, 2, 3])


def test_descriptive_stats_rejects_empty_series():
    with pytest.raises(ValueError, match="empty or not a numeric sequence"):
        descriptive_stats({"a": []})
    with pytest.raises(ValueError, match="empty or not a numeric sequence"):
        descriptive_stats({"a": None})


def test_descriptive_stats_rejects_non_numeric_and_bool_and_nonfinite():
    with pytest.raises(ValueError):
        descriptive_stats({"a": [1, "x"]})
    with pytest.raises(ValueError):
        descriptive_stats({"a": [True, 2]})
    with pytest.raises(ValueError):
        descriptive_stats({"a": [1, float("nan")]})
    with pytest.raises(ValueError):
        descriptive_stats({"a": [1, float("inf")]})


from app.modules.m04_research_scientist.expanded_211_258 import run as m4


def test_row232_caller_interpretations_win():
    out = m4(232, {"results": {"accuracy": [0.9]}, "interpretations": ["accuracy improved"]})
    result = out["result"]
    assert result["interpretations"] == ["accuracy improved"]
    assert "descriptive_stats" not in result
    assert result["causality_not_inferred"] is True


def test_row232_derives_stats_when_interpretations_absent():
    out = m4(232, {"results": {"accuracy": [0.8, 1.0]}})
    result = out["result"]
    assert result["descriptive_stats"]["accuracy"]["n"] == 2
    assert result["descriptive_stats"]["accuracy"]["mean"] == pytest.approx(0.9)
    assert result["interpretation_heuristic"] is True
    assert result["causality_not_inferred"] is True
    assert result["interpretations"] == []


def test_row232_fails_closed_on_non_numeric_results_without_interpretations():
    with pytest.raises(ValueError):
        m4(232, {"results": {"accuracy": ["high"]}})


def test_mounted_route_row232_bad_results_returns_422_not_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m04_research_scientist.routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    url = "/research-scientist/expanded-211-258/232"
    assert client.post(url, json={"results": {"accuracy": [0.9]}}).status_code == 200
    assert client.post(url, json={"results": {"accuracy": ["high"]}}).status_code == 422


def test_descriptive_stats_rejects_huge_int_without_overflowerror():
    with pytest.raises(ValueError):
        descriptive_stats({"a": [10**1000]})


def test_descriptive_stats_mean_of_large_finite_values_stays_finite():
    import math
    stats = descriptive_stats({"a": [1e308, 1e308]})
    assert math.isfinite(stats["a"]["mean"])
    assert stats["a"]["mean"] == pytest.approx(1e308)
    assert math.isfinite(stats["a"]["min"]) and math.isfinite(stats["a"]["max"])


def test_mounted_route_row232_huge_int_422_and_large_sum_200_finite():
    import math
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m04_research_scientist.routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    url = "/research-scientist/expanded-211-258/232"
    assert client.post(url, json={"results": {"a": [10**1000]}}).status_code == 422
    ok = client.post(url, json={"results": {"a": [1e308, 1e308]}})
    assert ok.status_code == 200
    mean = ok.json()["result"]["descriptive_stats"]["a"]["mean"]
    assert math.isfinite(mean)


def test_row232_empty_interpretations_list_falls_back_to_derivation():
    out = m4(232, {"results": {"accuracy": [0.9]}, "interpretations": []})
    result = out["result"]
    assert result["descriptive_stats"]["accuracy"]["n"] == 1
    assert result["interpretation_heuristic"] is True


def test_descriptive_stats_g6_rejects_numeric_strings_with_reason():
    # G6 survivor pin: the guard must reject numeric-looking strings outright;
    # a weakened guard that attempts float('5') would admit them (n=2, mean 5.5).
    with pytest.raises(ValueError, match="non-numeric or non-finite"):
        descriptive_stats({"a": ["5", "6"]})


def test_row232_g6_json_route_rejects_numeric_string_results_with_reason():
    # Same G6 guard, exercised through the row 232 JSON route (no caller
    # interpretations, so the derive branch runs descriptive_stats).
    with pytest.raises(ValueError, match="non-numeric or non-finite"):
        m4(232, {"results": {"a": ["5", "6"]}})


def test_descriptive_stats_g11_stringifies_int_labels():
    # G11 survivor pin: out key must be the stringified label, never the raw
    # non-str key; a mutant keying on the raw label would return int key 1.
    stats = descriptive_stats({1: [1, 2]})
    assert list(stats.keys()) == ["1"]
    assert 1 not in stats
    assert stats["1"] == {"n": 2, "mean": 1.5, "min": 1.0, "max": 2.0}
    assert isinstance(stats["1"]["mean"], float)
    assert isinstance(stats["1"]["min"], float)
    assert isinstance(stats["1"]["max"], float)


def test_descriptive_stats_s07_rejects_set_series_with_reason():
    # s07 survivor pin: the sequence guard must reject an unordered set with
    # the 'empty or not a numeric sequence' reason; dropping the guard would
    # iterate the set and silently compute stats.
    with pytest.raises(ValueError, match="empty or not a numeric sequence"):
        descriptive_stats({"a": {1, 2}})


def test_descriptive_stats_s08_accepts_tuple_series():
    # s08 survivor pin: tuples are valid numeric sequences; a list-only guard
    # would wrongly reject them.
    stats = descriptive_stats({"a": (1, 2)})
    assert stats == {"a": {"n": 2, "mean": 1.5, "min": 1.0, "max": 2.0}}


def test_descriptive_stats_s16_scaled_fsum_cancels_catastrophically():
    # s16 survivor pin: (1e16 + 1 - 1e16) / 3 must give exactly 1/3. A plain
    # sum of the scaled terms gives 0.5 on CPython 3.10; 3.12's compensated
    # sum() masks the mutant, so this pin is interpreter-dependent by
    # construction (see the stats.py docstring fsum policy note).
    stats = descriptive_stats({"a": [1e16, 1, -1e16]})
    assert stats["a"]["mean"] == 1 / 3


def test_row232_s22_need_results_fails_closed_not_keyerror():
    # s22 survivor pin: stats-standalone pin of the row 232 _need(d,'results')
    # guard (same site as the summarize-suite C1 pin): missing key must fail
    # closed with the shared reason, not crash KeyError.
    with pytest.raises(ValueError, match="missing required fields: results"):
        m4(232, {})


def test_descriptive_stats_s23_processes_every_label():
    # s23 survivor pin (auditor correction: fifth survivor): the per-label
    # loop must process EVERY entry; a mutant truncating to the first entry
    # would silently drop 'b'. Witness per peer.
    stats = descriptive_stats({"a": [1.0], "b": [2.0, 4.0]})
    assert sorted(stats.keys()) == ["a", "b"]
    assert stats["b"] == {"n": 2, "mean": 3.0, "min": 2.0, "max": 4.0}
