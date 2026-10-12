"""G109: portfolio analytics - exact allocation, kelly, risk stats, refusals."""
from __future__ import annotations

import pytest

from app.market import portfolio


def _assets():
    a = [0.002 * ((i % 5) - 1) + 0.001 for i in range(80)]
    b = [0.001 * ((i % 7) - 2) for i in range(80)]
    c = [0.0003 * ((i % 3) - 1) + 0.0005 for i in range(80)]
    return {"X": a, "Y": b, "Z": c}


def test_exact_allocation_hits_target():
    out = portfolio.allocate(_assets(), 0.20)
    assert out["expected_annual_return"] == pytest.approx(0.20, abs=1e-4)
    assert sum(out["weights"].values()) == pytest.approx(1.0, abs=1e-6)
    assert all(w >= 0 for w in out["weights"].values())


def test_infeasible_target_clamps_to_best_asset():
    out = portfolio.allocate(_assets(), 5.0)
    assert out["weights"] == {"X": 1.0}
    assert out["target_clamped_to"] < 5.0


def test_two_asset_matches_qp_and_simplex():
    assets = _assets()
    out = portfolio.allocate({"X": assets["X"], "Y": assets["Y"]}, 0.3)
    assert sum(out["weights"].values()) == pytest.approx(1.0, abs=1e-9)
    assert all(0 <= w <= 1 for w in out["weights"].values())
    assert out["expected_annual_return"] == pytest.approx(0.3, abs=1e-4)


def test_stats_known_values():
    flat_up = {"A": [0.001] * 60}
    s = portfolio.stats(flat_up)["A"]
    assert s["annualized_return"] == pytest.approx(0.252)
    assert s["annualized_volatility"] == 0.0
    assert s["max_drawdown"] == 0.0
    # known drawdown: +10% then -50% of peak -> 0.5
    s2 = portfolio.stats({"B": [0.10] + [0.0] * 28 + [-0.5555556] + [0.0] * 30})["B"]
    assert 0.5 <= s2["max_drawdown"] <= 0.56


def test_var_es_on_known_tail():
    rs = sorted([-0.05] * 3 + [-0.01] * 57)
    s = portfolio.stats({"A": rs})["A"]
    assert s["historical_var_95_daily"] >= 0.01
    assert s["historical_es_95_daily"] >= s["historical_var_95_daily"]


def test_kelly_cap_and_math():
    k = portfolio.kelly(0.9, 0.5)  # raw = 0.9 - 0.1/0.5 = 0.7 -> capped
    assert k["kelly_raw"] == pytest.approx(0.7)
    assert k["kelly_capped"] == portfolio.KELLY_CAP
    k2 = portfolio.kelly(0.55, 1.2)
    assert k2["kelly_capped"] == pytest.approx(0.55 - 0.45 / 1.2)
    k3 = portfolio.kelly(0.3, 1.0)  # negative edge -> zero, never negative sizing
    assert k3["kelly_capped"] == 0.0


def test_run_end_to_end_and_determinism():
    req = {"as_of": "2026-10-12", "assets": _assets(),
           "kelly": {"win_rate": 0.55, "win_loss_ratio": 1.2}}
    out1, out2 = portfolio.run(req), portfolio.run(req)
    assert out1 == out2
    assert set(out1["asset_stats"]) == {"X", "Y", "Z"}
    assert "allocation" in out1 and "kelly" in out1


def test_refusals():
    with pytest.raises(ValueError, match="MARKET_REFUSED_TRADE:rebalance_live"):
        portfolio.run({"as_of": "2026-10-12", "assets": _assets(), "rebalance_live": True})
    with pytest.raises(ValueError, match="MARKET_REFUSED_NOCREDS:secret"):
        portfolio.run({"as_of": "2026-10-12", "assets": _assets(), "secret": "x"})
    with pytest.raises(ValueError, match="MARKET_REFUSED_BAD_LENGTH"):
        portfolio.run({"as_of": "2026-10-12", "assets": {"A": [0.01] * 5}})
    with pytest.raises(ValueError, match="MARKET_REFUSED_BAD_TYPE"):
        portfolio.kelly(1.5, 1.0)
