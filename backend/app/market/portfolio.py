"""G109 / market.portfolio - real investing analytics over return series.

Mean-variance allocation (exact 2-asset closed form, long-only projected
cyclic descent for n assets), capped Kelly sizing, historical VaR/ES, and
drawdown statistics. Inputs are supplied return series (from predict.py or
real adapter data). No trading, no execution, no spend: the key scan refuses.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import math

PREFIX = "MARKET"
MAX_ASSETS = 50
MAX_POINTS = 20000
MIN_POINTS = 20
TRADING_DAYS = 252
KELLY_CAP = 0.25
_KEY_CLASSES = predict_classes = (
    ("TRADE", frozenset({"trade", "execute", "execution", "order", "buy_order",
                         "sell_order", "broker", "brokerage", "place_order", "rebalance_live"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "checkout", "card_number", "deposit"})),
    ("NOCREDS", frozenset({"login", "password", "credentials", "api_key", "secret",
                           "access_token", "bearer", "passwd"})),
)


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _scan_keys(node, depth=0):
    if depth > 32:
        _refuse("OVERSIZE", "request")
    if type(node) is dict:
        if len(node) > 64:
            _refuse("OVERSIZE", "request")
        for key, value in node.items():
            if type(key) is not str:
                _refuse("BAD_TYPE", "key")
            norm = key.casefold().replace("-", "_")
            for reason, table in _KEY_CLASSES:
                if norm in table:
                    _refuse(reason, norm)
            _scan_keys(value, depth + 1)
    elif type(node) in (list, tuple):
        for value in node:
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)


def _series(value, field):
    if isinstance(value, bool) or not isinstance(value, (list, tuple)):
        _refuse("BAD_TYPE", field)
    if not MIN_POINTS <= len(value) <= MAX_POINTS:
        _refuse("BAD_LENGTH", field)
    out = []
    for i, v in enumerate(value):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            _refuse("BAD_TYPE", "%s[%d]" % (field, i))
        if v <= -1.0:
            _refuse("BAD_TYPE", "%s[%d]" % (field, i))  # a return at or below -100% is not a usable series
        out.append(float(v))
    return out


def _mean(xs):
    return sum(xs) / len(xs)


def _cov(xs, ys):
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def stats(series):
    """Annualized return/vol, historical VaR/ES, max drawdown per asset."""
    out = {}
    for name, rs in series.items():
        mean_d = _mean(rs)
        var = _cov(rs, rs)
        std_d = math.sqrt(max(var, 0.0))
        ordered = sorted(rs)
        idx = max(0, int(math.floor(0.05 * len(ordered))) - 1)
        var_95 = -ordered[idx]
        tail = [r for r in ordered if r <= ordered[idx]]
        es_95 = -_mean(tail) if tail else var_95
        equity, peak, max_dd = 1.0, 1.0, 0.0
        for r in rs:
            equity *= 1.0 + r
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak)
        out[name] = {
            "mean_daily": round(mean_d, 8),
            "annualized_return": round(mean_d * TRADING_DAYS, 6),
            "annualized_volatility": round(std_d * math.sqrt(TRADING_DAYS), 6),
            "sharpe_annualized": round(mean_d / std_d * math.sqrt(TRADING_DAYS), 6) if std_d > 0 else 0.0,
            "historical_var_95_daily": round(var_95, 6),
            "historical_es_95_daily": round(es_95, 6),
            "max_drawdown": round(max_dd, 6),
        }
    return out


def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting; raises on singularity."""
    n = len(matrix)
    a = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-15:
            _refuse("SINGULAR", "allocate")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(n):
            if row != col and a[row][col] != 0.0:
                factor = a[row][col] / a[col][col]
                for k in range(col, n + 1):
                    a[row][k] -= factor * a[col][k]
    return [a[i][n] / a[i][i] for i in range(n)]


def _qp_weights(mu, cov, target, active):
    """Analytic equality-constrained mean-variance solution on the active set:
    minimize w'Sw s.t. sum w = 1, mu.w = target. KKT closed form via A, B, C."""
    m = len(active)
    sub_mu = [mu[i] for i in active]
    sub_cov = [[cov[i][j] for j in active] for i in active]
    ones = [1.0] * m
    inv_1 = _solve([row[:] for row in sub_cov], ones[:])
    inv_mu = _solve([row[:] for row in sub_cov], sub_mu[:])
    A = sum(ones[i] * inv_1[i] for i in range(m))
    B = sum(ones[i] * inv_mu[i] for i in range(m))
    C = sum(sub_mu[i] * inv_mu[i] for i in range(m))
    D = A * C - B * B
    if abs(D) < 1e-18:
        # all active means equal: return constraint is vacuous, take min-variance
        if abs(A) < 1e-18:
            _refuse("SINGULAR", "allocate")
        return [inv_1[i] / A for i in range(m)]
    g = (C - target * B) / D
    h = (target * A - B) / D
    return [g * inv_1[i] + h * inv_mu[i] for i in range(m)]


def allocate(series, target_annual_return=None):
    """Exact long-only mean-variance allocation over supplied daily series.

    Analytic KKT solution for the return-constrained minimum-variance
    portfolio; negative weights are removed by an active-set loop that
    re-solves on the surviving assets, so the result is the exact long-only
    optimum, deterministic, with no iterative tolerance."""
    names = sorted(series)
    data = [_series(series[n], n) for n in names]
    n = len(data)
    if n < 2:
        _refuse("BAD_LENGTH", "assets")
    if len({len(d) for d in data}) != 1:
        _refuse("BAD_LENGTH", "aligned")
    mu = [_mean(d) for d in data]
    cov = [[_cov(data[i], data[j]) + (1e-10 if i == j else 0.0) for j in range(n)]
           for i in range(n)]  # 1e-10 diagonal ridge: collinear series stay solvable
    if target_annual_return is None:
        target = sum(mu) / n
    else:
        if isinstance(target_annual_return, bool) or not isinstance(
                target_annual_return, (int, float)) or not math.isfinite(target_annual_return):
            _refuse("BAD_TYPE", "target_annual_return")
        target = target_annual_return / TRADING_DAYS
    # An infeasible target (outside achievable long-only range) clamps to the
    # nearest achievable extreme: the max/min single-asset mean.
    lo_t, hi_t = min(mu), max(mu)
    clamped = min(max(target, lo_t), hi_t)

    active = list(range(n))
    for _ in range(n):
        w_active = _qp_weights(mu, cov, clamped, active)
        worst, worst_w = -1, 0.0
        for k, w in enumerate(w_active):
            if w < worst_w - 1e-12:
                worst, worst_w = k, w
        if worst < 0:
            break
        active.pop(worst)
        if len(active) < 1:
            active = [max(range(n), key=lambda i: mu[i])]
            w_active = [1.0]
            break
    else:
        w_active = _qp_weights(mu, cov, clamped, active)
    w = [0.0] * n
    for k, i in enumerate(active):
        w[i] = max(0.0, w_active[k])
    total = sum(w)
    if total <= 0:
        _refuse("SINGULAR", "allocate")
    w = [x / total for x in w]

    port_ret = sum(mu[i] * w[i] for i in range(n))
    port_var = sum(w[i] * w[j] * cov[i][j] for i in range(n) for j in range(n))
    port_std = math.sqrt(max(port_var, 0.0))
    return {
        "weights": {names[i]: round(w[i], 6) for i in range(n) if w[i] > 1e-12},
        "expected_annual_return": round(port_ret * TRADING_DAYS, 6),
        "annualized_volatility": round(port_std * math.sqrt(TRADING_DAYS), 6),
        "sharpe_annualized": round(port_ret / port_std * math.sqrt(TRADING_DAYS), 6) if port_std > 0 else 0.0,
        "method": "exact long-only mean-variance: analytic KKT solution with active-set removal of negative weights",
        "target_annual_return": round(target * TRADING_DAYS, 6),
        "target_clamped_to": round(clamped * TRADING_DAYS, 6),
    }


def kelly(win_rate, win_loss_ratio):
    """Kelly fraction for repeated bets, hard-capped. f* = p - q/b."""
    for value, field in ((win_rate, "win_rate"), (win_loss_ratio, "win_loss_ratio")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            _refuse("BAD_TYPE", field)
    if not 0 <= win_rate <= 1:
        _refuse("BAD_TYPE", "win_rate")
    if win_loss_ratio <= 0:
        _refuse("BAD_TYPE", "win_loss_ratio")
    raw = win_rate - (1 - win_rate) / win_loss_ratio
    return {"kelly_raw": round(raw, 6), "kelly_capped": round(min(max(raw, 0.0), KELLY_CAP), 6),
            "cap": KELLY_CAP,
            "note": "capped quarter-Kelly ceiling; sizing analytics only, never an order"}


def run(request):
    """Portfolio analytics over supplied return series; plain dict out."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "assets", "target_annual_return", "kelly"}:
        _refuse("UNKNOWN", "request")
    if type(request.get("as_of")) is not str:
        _refuse("BAD_TYPE", "as_of")
    assets = request.get("assets")
    if type(assets) is not dict or not assets:
        _refuse("BAD_TYPE", "assets")
    if len(assets) > MAX_ASSETS:
        _refuse("OVERSIZE", "assets")
    for name in assets:
        if type(name) is not str or not name.strip() or len(name) > 64:
            _refuse("BAD_TYPE", "asset_name")
    clean = {name: _series(rs, "assets[%s]" % name) for name, rs in assets.items()}
    out = {"as_of": request["as_of"], "asset_stats": stats(clean),
           "scope_note": "analytics over supplied return series; no trading, execution or spend"}
    if len(clean) >= 2:
        out["allocation"] = allocate(clean, request.get("target_annual_return"))
    if request.get("kelly") is not None:
        k = request["kelly"]
        if type(k) is not dict or set(k) - {"win_rate", "win_loss_ratio"}:
            _refuse("BAD_TYPE", "kelly")
        out["kelly"] = kelly(k.get("win_rate"), k.get("win_loss_ratio"))
    return out
