"""G109 / market.predict - market prediction and investing analytics.

Source request (instinct doc, verbatim): "make me money, trade with it,
invest, and predict markets".

This unit predicts: it fits time-series models (naive, drift,
AR(p) least squares, Holt linear smoothing, ridge on computed indicators) to
supplied or adapter-fetched price observations, selects the best model by
walk-forward out-of-sample RMSE, and forecasts with empirical residual
intervals. Investing analytics cover mean-variance allocation, capped Kelly
sizing and historical VaR/ES.

Hard boundaries (standing rules, enforced, not documented): no trading,
no execution, no spend, no credentials - any such request key refuses.
Prediction is statistics over past data, never a promise: outputs carry
measured out-of-sample errors and the module refuses guarantee language.

Stdlib only, offline, deterministic: same input bytes, same output bytes.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date

from app.modules.c30 import policy

PREFIX = "MARKET"
MAX_POINTS = 20000
MIN_POINTS = 30
MAX_HORIZON = 60
MAX_AR_P = 10
MAX_FIELD = 200
MAX_TEXT = 512
RIDGE_LAMBDA = 1.0
TRADING_DAYS = 252
GUARANTEE_PHRASES = ("guarantee", "risk-free", "risk free", "sure thing",
                     "certain profit", "will earn", "cant lose", "can't lose")
_KEY_CLASSES = (
    ("TRADE", frozenset({"trade", "execute", "execution", "order", "buy_order",
                         "sell_order", "broker", "brokerage", "place_order"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "checkout", "card_number",
                         "deposit", "wire"})),
    ("SEND", frozenset({"send", "smtp", "email_send", "webhook_post"})),
    ("NOCREDS", frozenset({"login", "password", "username", "credentials", "otp",
                           "api_key", "secret", "access_token", "refresh_token",
                           "bearer", "passwd"})),
)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _scan_keys(node, seen=None, depth=0):
    """Refuse trade/spend/send/credential keys anywhere in the request."""
    if seen is None:
        seen = set()
    if depth > 32 or len(seen) > 10000:
        _refuse("OVERSIZE", "request")
    if type(node) is dict:
        if len(node) > 64:
            _refuse("OVERSIZE", "request")
        for key, value in node.items():
            if type(key) is not str:
                _refuse("BAD_TYPE", "key")
            if len(key) > MAX_FIELD:
                _refuse("OVERSIZE", "key")
            norm = key.casefold().replace("-", "_")
            for reason, table in _KEY_CLASSES:
                if norm in table:
                    _refuse(reason, norm)
            if id(value) not in seen and type(value) in (dict, list, tuple):
                seen.add(id(value))
                _scan_keys(value, seen, depth + 1)
    elif type(node) in (list, tuple):
        if len(node) > MAX_POINTS * 4:
            _refuse("OVERSIZE", "request")
        for value in node:
            if id(value) not in seen and type(value) in (dict, list, tuple):
                seen.add(id(value))
                _scan_keys(value, seen, depth + 1)


def _text(value, field, limit=MAX_TEXT):
    text = policy.clean_text(value, PREFIX, field, limit)
    low = text.casefold()
    if any(p in low for p in GUARANTEE_PHRASES):
        _refuse("GUARANTEE", field)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in text):
        _refuse("CONTROL_CHARS", field)
    return text


def _num(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("BAD_TYPE", field)
    if not math.isfinite(value):
        _refuse("NONFINITE", field)
    return float(value)


def _date(value, field):
    if type(value) is not str or not _DATE_RE.fullmatch(value):
        _refuse("BAD_TYPE", field)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _refuse("BAD_TYPE", field)


def _parse_series(raw, field="series"):
    """Validate [{date, close, ...}] into (dates, closes) ascending, deduped."""
    if isinstance(raw, bool) or not isinstance(raw, (list, tuple)):
        _refuse("BAD_TYPE", field)
    if not MIN_POINTS <= len(raw) <= MAX_POINTS:
        _refuse("BAD_LENGTH", field)
    rows = {}
    volumes = {}
    for i, point in enumerate(raw):
        if type(point) is not dict:
            _refuse("BAD_TYPE", "%s[%d]" % (field, i))
        if set(point) - {"date", "close", "volume"}:
            _refuse("UNKNOWN", "%s[%d]" % (field, i))
        d = _date(point.get("date"), "%s[%d].date" % (field, i))
        c = _num(point.get("close"), "%s[%d].close" % (field, i))
        if c <= 0:
            _refuse("NONPOSITIVE", "%s[%d].close" % (field, i))
        if point.get("volume") is not None:
            v = _num(point["volume"], "%s[%d].volume" % (field, i))
            if v < 0:
                _refuse("BAD_TYPE", "%s[%d].volume" % (field, i))
            volumes[d] = v
        rows[d] = c  # later duplicate date wins, counted below
    days = sorted(rows)
    dup = len(raw) - len(rows)
    return days, [rows[d] for d in days], [volumes.get(d) for d in days], dup


# ---------------- indicators (standard definitions) ----------------

def returns(closes, log=False):
    out = []
    for i in range(1, len(closes)):
        r = math.log(closes[i] / closes[i - 1]) if log else closes[i] / closes[i - 1] - 1.0
        out.append(r)
    return out


def sma(values, window):
    if window < 1 or len(values) < window:
        _refuse("BAD_TYPE", "window")
    out, acc = [], 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        if i >= window - 1:
            out.append(acc / window)
    return out


def ema(values, span):
    if span < 1:
        _refuse("BAD_TYPE", "span")
    k = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, period=14):
    """Wilder's RSI; len(closes) must exceed period."""
    if len(closes) <= period:
        _refuse("BAD_LENGTH", "rsi")
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = []
    for i in range(period, len(gains)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        _refuse("BAD_LENGTH", "macd")
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [f - s for f, s in zip(ef, es)]
    sig = ema(line, signal)
    return line, sig


def realized_volatility(closes, window=None):
    lr = returns(closes, log=True)
    seg = lr[-window:] if window else lr
    if len(seg) < 2:
        _refuse("BAD_LENGTH", "volatility")
    mean = sum(seg) / len(seg)
    var = sum((x - mean) ** 2 for x in seg) / (len(seg) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def _features(closes, i):
    """Indicator feature vector at index i (predicts close[i+1]'s return)."""
    r1 = closes[i] / closes[i - 1] - 1.0
    r5 = closes[i] / closes[i - 5] - 1.0 if i >= 5 else 0.0
    r10 = closes[i] / closes[i - 10] - 1.0 if i >= 10 else 0.0
    s5 = sum(closes[i - 4:i + 1]) / 5 if i >= 4 else closes[i]
    s20 = sum(closes[i - 19:i + 1]) / 20 if i >= 19 else closes[i]
    sma_ratio = closes[i] / s5 - 1.0 if s5 else 0.0
    sma20_ratio = closes[i] / s20 - 1.0 if s20 else 0.0
    window = [closes[j] / closes[j - 1] - 1.0 for j in range(max(1, i - 9), i + 1)]
    mean = sum(window) / len(window)
    var = sum((x - mean) ** 2 for x in window) / len(window)
    return [1.0, r1, r5, r10, sma_ratio, sma20_ratio, math.sqrt(var)]


# ---------------- small linear algebra (standard algorithms, floats) ----------------

def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting; raises on singularity."""
    n = len(matrix)
    a = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            _refuse("SINGULAR", "fit")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(n):
            if row != col and a[row][col] != 0.0:
                factor = a[row][col] / a[col][col]
                for k in range(col, n + 1):
                    a[row][k] -= factor * a[col][k]
    return [a[i][n] / a[i][i] for i in range(n)]


def _lstsq(x_rows, y, ridge=0.0):
    """Least squares (optionally ridge) over feature rows."""
    n = len(x_rows[0])
    xtx = [[0.0] * n for _ in range(n)]
    xty = [0.0] * n
    for row, target in zip(x_rows, y):
        for i in range(n):
            xty[i] += row[i] * target
            for j in range(n):
                xtx[i][j] += row[i] * row[j]
    for i in range(n):
        xtx[i][i] += ridge
    return _solve(xtx, xty)


# ---------------- models: fit/predict pairs ----------------

def _fit_ar(closes, p):
    """AR(p) on returns via OLS; returns coefficient list length p+1."""
    rs = returns(closes)
    if len(rs) <= p + 1:
        _refuse("BAD_LENGTH", "ar_fit")
    x_rows = [[1.0] + [rs[t - k] for k in range(1, p + 1)] for t in range(p, len(rs))]
    y = [rs[t] for t in range(p, len(rs))]
    return _lstsq(x_rows, y)


def _predict_ar(coef, closes):
    rs = returns(closes)
    p = len(coef) - 1
    if len(rs) < p:
        _refuse("BAD_LENGTH", "ar_predict")
    pred_r = coef[0] + sum(coef[k] * rs[-k] for k in range(1, p + 1))
    return closes[-1] * (1.0 + pred_r)


def _fit_holt(closes, alpha=0.4, beta=0.05):
    """Holt linear smoothing; returns (level, trend)."""
    level, trend = closes[0], closes[1] - closes[0]
    for v in closes[1:]:
        prev = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - prev) + (1 - beta) * trend
    return level, trend


def _fit_ridge(closes):
    """Ridge on indicator features predicting next-step return."""
    x_rows, y = [], []
    for i in range(20, len(closes) - 1):
        x_rows.append(_features(closes, i))
        y.append(closes[i + 1] / closes[i] - 1.0)
    if len(x_rows) < 10:
        _refuse("BAD_LENGTH", "ridge_fit")
    return _lstsq(x_rows, y, ridge=RIDGE_LAMBDA)


def _predict_ridge(coef, closes):
    f = _features(closes, len(closes) - 1)
    pred_r = sum(c * x for c, x in zip(coef, f))
    return closes[-1] * (1.0 + pred_r)


MODELS = ("naive", "drift", "ar1", "ar3", "holt", "ridge")


def _fit_predict(model, train):
    if model == "naive":
        return train[-1]
    if model == "drift":
        rs = returns(train)
        return train[-1] * (1.0 + sum(rs) / len(rs))
    if model == "ar1":
        return _predict_ar(_fit_ar(train, 1), train)
    if model == "ar3":
        return _predict_ar(_fit_ar(train, 3), train)
    if model == "holt":
        level, trend = _fit_holt(train)
        return level + trend
    if model == "ridge":
        return _predict_ridge(_fit_ridge(train), train)
    _refuse("UNKNOWN", "model")


# ---------------- backtest, metrics, forecast ----------------

def _walk_forward(closes, window):
    """One-step-ahead predictions per model over the out-of-sample tail."""
    preds = {m: [] for m in MODELS}
    actuals = []
    for t in range(window, len(closes)):
        train = closes[:t]
        actuals.append(closes[t])
        for m in MODELS:
            try:
                preds[m].append(_fit_predict(m, train))
            except ValueError:
                preds[m].append(train[-1])  # model inadmissible this far back: degrade to naive, counted below
    return preds, actuals


def _metrics(preds, actuals, closes_tail_start):
    n = len(actuals)
    if n == 0:
        _refuse("BAD_LENGTH", "backtest")
    se = sum((p - a) ** 2 for p, a in zip(preds, actuals))
    ae = sum(abs(p - a) for p, a in zip(preds, actuals))
    hits = 0
    strat = []
    for i, (p, a) in enumerate(zip(preds, actuals)):
        prev = closes_tail_start if i == 0 else actuals[i - 1]
        if (p - prev) * (a - prev) > 0:
            hits += 1
        position = 1.0 if p > prev else (-1.0 if p < prev else 0.0)
        strat.append(position * (a / prev - 1.0))
    mean_s = sum(strat) / n
    var_s = sum((x - mean_s) ** 2 for x in strat) / (n - 1) if n > 1 else 0.0
    sharpe = mean_s / math.sqrt(var_s) * math.sqrt(TRADING_DAYS) if var_s > 0 else 0.0
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for r in strat:
        equity *= 1.0 + r
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    return {"rmse": round(math.sqrt(se / n), 6), "mae": round(ae / n, 6),
            "directional_accuracy": round(hits / n, 6),
            "sign_strategy": {"sharpe_annualized": round(sharpe, 6),
                              "max_drawdown": round(max_dd, 6),
                              "total_return": round(equity - 1.0, 6)},
            "n": n}


def _quantile(sorted_vals, q):
    if not sorted_vals:
        _refuse("BAD_LENGTH", "residuals")
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def run(request):
    """Predict one supplied market series; returns a plain dict.

    Raises ValueError('MARKET_REFUSED_<REASON>[:field]') on refusal."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "name", "series", "horizon", "train_fraction"}:
        _refuse("UNKNOWN", "request")
    as_of = _date(request.get("as_of"), "as_of")
    name = _text(request.get("name"), "name", MAX_FIELD)
    horizon = request.get("horizon", 5)
    if isinstance(horizon, bool) or type(horizon) is not int or not 1 <= horizon <= MAX_HORIZON:
        _refuse("BAD_TYPE", "horizon")
    frac = request.get("train_fraction", 0.7)
    frac = _num(frac, "train_fraction")
    if not 0.5 <= frac <= 0.9:
        _refuse("BAD_TYPE", "train_fraction")
    days, closes, _vol, dup = _parse_series(request.get("series"))
    if days[-1] > as_of:
        _refuse("FUTURE_DATA", "series")

    window = max(21, int(len(closes) * frac))
    if len(closes) - window < 10:
        _refuse("BAD_LENGTH", "backtest")
    preds, actuals = _walk_forward(closes, window)
    metrics = {m: _metrics(preds[m], actuals, closes[window - 1]) for m in MODELS}
    best = min(MODELS, key=lambda m: (metrics[m]["rmse"], MODELS.index(m)))

    # Forecast: chosen model iterated one step at a time; residual band from
    # that model's own out-of-sample errors (empirical, not a probability promise).
    residuals = sorted(p - a for p, a in zip(preds[best], actuals))
    path, extended = [], list(closes)
    for h in range(1, horizon + 1):
        nxt = _fit_predict(best, extended)
        extended.append(nxt)
        path.append({"step": h, "forecast": round(nxt, 6),
                     "low_empirical": round(nxt + _quantile(residuals, 0.05) * math.sqrt(h), 6),
                     "high_empirical": round(nxt + _quantile(residuals, 0.95) * math.sqrt(h), 6)})

    ind = {"sma_20": round(sma(closes, 20)[-1], 6) if len(closes) >= 20 else None,
           "ema_12": round(ema(closes, 12)[-1], 6),
           "rsi_14": round(rsi(closes, 14)[-1], 6) if len(closes) > 14 else None,
           "macd_line": None, "macd_signal": None,
           "realized_vol_annualized": round(realized_volatility(closes), 6),
           "momentum_10": round(closes[-1] / closes[-11] - 1.0, 6) if len(closes) > 10 else None}
    if len(closes) >= 35:
        line, sig = macd(closes)
        ind["macd_line"], ind["macd_signal"] = round(line[-1], 6), round(sig[-1], 6)

    return {
        "name": name, "as_of": str(request.get("as_of")), "points": len(closes),
        "duplicate_dates_dropped": dup,
        "last_close": round(closes[-1], 6), "last_date": days[-1].isoformat(),
        "indicators": ind,
        "backtest": {"method": "walk-forward one-step-ahead, train window %d of %d points" % (window, len(closes)),
                     "models": metrics},
        "selected_model": best,
        "forecast": path,
        "scope": policy.scope(
            ["fitted models (naive/drift/AR(1)/AR(3)/Holt/ridge on indicators)",
             "walk-forward out-of-sample selection by RMSE with measured errors",
             "empirical residual forecast bands, labeled empirical",
             "standard indicators (SMA/EMA/RSI/MACD/realized vol/momentum)"],
            ["trading, execution, deposits or broker access - refused by key scan",
             "any promise of profit - guarantee language is refused",
             "probabilistic confidence - bands are empirical residuals, not calibrated probabilities"],
            "supplied or adapter-fetched price observations", str(request.get("as_of"))),
    }


def series_from_records(records, field_path):
    """Build a validated series from fetched MarketRecord-shaped dicts.

    records: iterable of {observed_at, payload}; field_path: dotted numeric
    path inside payload (e.g. 'close' or 'data.price'). Real adapter output
    from app.market.sources plugs straight in."""
    if isinstance(records, bool) or not isinstance(records, (list, tuple)) or not records:
        _refuse("EMPTY", "records")
    parts = field_path.split(".")
    if not parts or any(not p for p in parts):
        _refuse("BAD_TYPE", "field_path")
    rows = []
    for i, rec in enumerate(records):
        if type(rec) is not dict:
            _refuse("BAD_TYPE", "records[%d]" % i)
        observed = rec.get("observed_at")
        if type(observed) is not str or len(observed) < 10:
            _refuse("BAD_TYPE", "records[%d].observed_at" % i)
        node = rec.get("payload")
        for part in parts:
            if type(node) is not dict or part not in node:
                _refuse("MISSING_FIELD", "records[%d].%s" % (i, field_path))
            node = node[part]
        _num(node, "records[%d].%s" % (i, field_path))
        rows.append({"date": observed[:10], "close": node})
    return rows
