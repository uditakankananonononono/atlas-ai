"""S6.4 / c37.breakthroughs - breakthrough digest over SUPPLIED release items.

Source excerpt (verbatim, owner spec text): "train and model the best tools
across all sectors and present breakthroughs".

Honest reading: ranks supplied items per sector on stated criteria. Grades come
ONLY from supplied labels (nothing is verified or fetched here). "Train and
model" is not implemented (no training, no compute). "best"/"breakthrough" is
only ever a computed score. Guard: c30.policy (real helper, no local fallback).
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import datetime
import json
import math
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from app.modules.c30 import policy

PREFIX = "INTEL"
DEFAULT_WINDOW = 14
MAX_WINDOW = 365
DEFAULT_TOP_N = 5
MAX_TOP_N = 100
GRADE_RANK = {"A": 3, "B": 2, "C": 1, "D": 0}
WEIGHT = {"A": 1.0, "B": 0.6}
OPEN_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD", "BSD-2-Clause", "BSD-3-Clause", "CC0"})
KINDS = frozenset({"tool", "paper", "model", "dataset"})
SOURCES = frozenset({"vendor", "third_party", "journal", "conference", "unknown"})
EVIDENCE = frozenset({"benchmark", "peer_reviewed", "vendor_statement", "none"})


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _has_control(value):
    return isinstance(value, str) and any(
        unicodedata.category(c) in policy.FORBIDDEN_CATEGORIES for c in value)


def _r6(x):
    return round(x, 6)


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _parse_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def normalize_url(url):
    """Lowercase scheme+host, drop fragment, trailing slash and utm_* params.
    Returns None unless it is a public-looking https URL with a host and no
    userinfo."""
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() != "https" or not host or "@" in parts.netloc:
        return None
    netloc = host.lower() + (":%d" % port if port else "")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_")])
    return urlunsplit(("https", netloc, parts.path.rstrip("/"), query, ""))


def _claim_grade(claim, has_baseline):
    """-> (grade, flags) from the supplied labels only."""
    if not isinstance(claim, dict):
        return "D", []
    etype = claim.get("evidence_type")
    prov = claim.get("provenance") if isinstance(claim.get("provenance"), dict) else {}
    src = prov.get("source")
    repro = prov.get("independent_reproduction_url")
    has_repro = isinstance(repro, str) and bool(repro.strip())
    if etype == "peer_reviewed":
        if src in ("journal", "conference"):
            return "A", []
        return "C", ["label_conflict"]
    if etype == "benchmark":
        if has_repro:
            return "A", []
        if src == "third_party" and has_baseline:
            return "B", []
        return "C", []
    if etype == "vendor_statement":
        return "C", []
    return "D", []


def _item_grade(claims, has_baseline):
    best, flags = "D", []
    for c in claims:
        g, f = _claim_grade(c, has_baseline)
        flags += f
        if GRADE_RANK[g] > GRADE_RANK[best]:
            best = g
    return best, sorted(set(flags))


METRIC_DROP_REASONS = ("malformed_control_dropped", "metric_baseline_invalid", "metric_direction_invalid",
                       "metric_name_invalid", "metric_not_object", "metric_value_invalid", "metrics_not_list")


def _metrics(raw, drops):
    """-> list of normalized metrics. Never drops the item (item 16).
    `raw` missing or null is []; present but not a list is [] with one
    `metrics_not_list` drop; an entry that is not an object is dropped per entry
    (`metric_not_object`). A metric is dropped when its name is missing, null,
    non-str, blank or over 128 chars, its value is not a finite number, a present
    baseline_value is not a finite number, or higher_is_better is not a bool
    (per-field reasons: `malformed_control_dropped`, `metric_name_invalid`, `metric_value_invalid`, `metric_baseline_invalid`, `metric_direction_invalid`).
    Each drop is counted once, by the first failure in the order name, value,
    baseline_value, higher_is_better. A null or missing baseline is legal."""
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        drops.append("metrics_not_list")
        return out
    for mt in raw:
        if not isinstance(mt, dict):
            drops.append("metric_not_object")
            continue
        name = mt.get("name")
        if _has_control(name):
            drops.append("malformed_control_dropped")
            continue
        try:
            name = policy.clean_text(name, PREFIX, "metric_name", 128)
        except ValueError:
            drops.append("metric_name_invalid")
            continue
        hib = mt.get("higher_is_better")
        base = mt.get("baseline_value")
        # one counted reason per dropped metric: first failure in the order
        # name, value, baseline_value (when present), higher_is_better (item 17)
        if not _is_num(mt.get("value")):
            drops.append("metric_value_invalid")
            continue
        if base is not None and not _is_num(base):
            drops.append("metric_baseline_invalid")
            continue
        if not isinstance(hib, bool):
            drops.append("metric_direction_invalid")
            continue
        delta = None
        mflags = []
        if base == 0:
            mflags.append("baseline_zero")
        if base is not None and base != 0:
            diff = (mt["value"] - base) if hib else (base - mt["value"])
            delta = _r6(diff / abs(base))
        out.append({"name": name, "value": _r6(mt["value"]),
                    "baseline_value": None if base is None else _r6(base),
                    "higher_is_better": hib, "delta": delta, "flags": mflags})
    return out


ITEM_DROP_REASONS = ("sector_not_requested", "id_invalid", "title_invalid", "url_invalid", "url_not_https",
                     "published_invalid", "future_date", "stale", "malformed_control", "duplicate_url")
def _bad_required_text(v, cap):
    return not isinstance(v, str) or not v.strip() or len(v) > cap


def _validate_item(raw, sectors, as_of, window):
    """-> (item dict, None) or (None, drop_reason). Item 21 chain, first failure wins:
    sector_not_requested, id_invalid, title_invalid, url_invalid, url_not_https,
    published_invalid, future_date, stale, malformed_control."""
    if not isinstance(raw, dict):
        return None, "sector_not_requested"       # no sector to attribute (item 22c)
    sec = raw.get("sector")
    if not (isinstance(sec, str) and sec in sectors):
        return None, "sector_not_requested"
    if _bad_required_text(raw.get("id"), 256):
        return None, "id_invalid"
    if _bad_required_text(raw.get("title"), 512):
        return None, "title_invalid"
    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        return None, "url_invalid"
    nurl = normalize_url(url)
    if nurl is None:
        return None, "url_not_https"
    pub = _parse_date(raw.get("published"))
    if pub is None:
        return None, "published_invalid"
    age = (as_of - pub).days
    if age < 0:
        return None, "future_date"
    if age > window:
        return None, "stale"
    # control characters: a required field drops the item (last in the chain),
    # an optional field is dropped to "unknown"
    if any(_has_control(raw.get(k)) for k in ("id", "title", "url", "published", "sector")):
        return None, "malformed_control"
    # optional kind/license (item 23). Missing or null -> "unknown", no flag. A control
    # character -> "unknown" + malformed_control_dropped (item 12). Any other bad value ->
    # "unknown" + kind_invalid / license_invalid. kind must be one of KINDS (exact case);
    # license is free-form (non-blank str up to 64 chars, "unknown" included).
    dropped = []
    opt = {}
    extra_flags = set()
    for key in ("kind", "license"):
        v = raw.get(key)
        if v is None:
            v = "unknown"
        elif _has_control(v):
            dropped.append(key)
            v = "unknown"
        elif _bad_required_text(v, 64) or (key == "kind" and v not in KINDS):
            extra_flags.add(key + "_invalid")
            v = "unknown"
        opt[key] = v
    iid, title, kind, lic = raw["id"], raw["title"], opt["kind"], opt["license"]
    sector = sec
    # claims: not a list -> [] with flag; a non-object entry is dropped alone with the flag (item 22a)
    claims = raw.get("claims")
    claims_invalid = False
    if claims is None:
        claims = []
    elif not isinstance(claims, list):
        claims, claims_invalid = [], True
    else:
        good_claims = [c for c in claims if isinstance(c, dict)]
        claims_invalid = len(good_claims) != len(claims)
        claims = good_claims
    metric_drops = []
    mets = _metrics(raw.get("metrics"), metric_drops)
    has_base = any(x["baseline_value"] is not None for x in mets)
    grade, flags = _item_grade(claims, has_base)
    if any("baseline_zero" in x["flags"] for x in mets):
        flags = sorted(set(flags) | {"baseline_zero"})
    if claims_invalid:
        flags = sorted(set(flags) | {"claims_invalid"})
    flags = sorted(set(flags) | extra_flags)
    if dropped or "malformed_control_dropped" in metric_drops:
        flags = sorted(set(flags) | {"malformed_control_dropped"})
    if set(metric_drops) - {"malformed_control_dropped"}:
        flags = sorted(set(flags) | {"metric_invalid"})
    return {"id": iid, "title": title, "sector": sector, "kind": kind, "license": lic,
            "url": nurl, "published": pub.isoformat(), "age": age, "grade": grade,
            "flags": flags, "metrics": mets, "metric_drops": metric_drops}, None


def _score(it, window):
    deltas = [x["delta"] for x in it["metrics"] if x["delta"] is not None]
    if not deltas or it["grade"] not in WEIGHT:
        return 0.0
    recency = 1.0 - 0.5 * it["age"] / window
    return _r6(sum(deltas) / len(deltas) * WEIGHT[it["grade"]] * recency)


def _view(it, score=None, extra_flags=()):
    row = {"id": it["id"], "title": it["title"], "url": it["url"], "kind": it["kind"],
           "published": it["published"], "grade": it["grade"],
           "grade_label": "supplied-label grade %s (not verified by this unit)" % it["grade"],
           "flags": sorted(set(it["flags"]) | set(extra_flags)), "metrics": it["metrics"], "license": it["license"],
           "integrable_open_source": it["license"] in OPEN_LICENSES, "caveats": _caveats(it)}
    if score is not None:
        row["score"] = score
    return row


def _caveats(it):
    out = []
    if it["grade"] == "C":
        out.append("vendor-stated or label-conflicted, untested")
    if it["grade"] == "D":
        out.append("no usable evidence label")
    if "label_conflict" in it["flags"]:
        out.append("peer_reviewed label with non-journal/conference source")
    if it["metrics"] and all(x["delta"] is None for x in it["metrics"]):
        out.append("no computable delta (missing or zero baseline)")
    return out


def run(request):
    """Digest SUPPLIED items. Refusals raise ValueError('INTEL_REFUSED_<REASON>')."""
    if not isinstance(request, dict):
        _refuse("BAD_TYPE", "request")
    as_of_raw = request.get("as_of")
    if _has_control(as_of_raw):
        _refuse("CONTROL_CHARS", "as_of")
    as_of = _parse_date(as_of_raw)
    if as_of is None:
        _refuse("BAD_TYPE", "as_of")
    window = request.get("window_days", DEFAULT_WINDOW)
    if _has_control(window):
        _refuse("CONTROL_CHARS", "window_days")
    if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= MAX_WINDOW:
        _refuse("BAD_TYPE", "window_days")
    top_n = request.get("top_n", DEFAULT_TOP_N)
    if _has_control(top_n):
        _refuse("CONTROL_CHARS", "top_n")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= MAX_TOP_N:
        _refuse("BAD_TYPE", "top_n")
    sectors_raw = request.get("sectors")
    if not isinstance(sectors_raw, list):
        _refuse("BAD_TYPE", "sectors")
    if not sectors_raw:
        _refuse("EMPTY", "sectors")
    for s in sectors_raw:
        if not isinstance(s, str) or not s.strip():
            _refuse("BAD_TYPE", "sectors")
    sectors = sorted({policy.clean_text(s, PREFIX, "sector", 64) for s in sectors_raw})
    items = request.get("items")
    if not isinstance(items, list):
        _refuse("BAD_TYPE", "items")
    if not items:
        _refuse("NOITEMS")

    cov = {s: {"items_supplied": 0, "items_used": 0, "items_dropped_by_reason": {}}
           for s in sectors}
    unattributed = {}
    valid = []
    for raw in items:
        sec = raw.get("sector") if isinstance(raw, dict) else None
        if not isinstance(sec, str):
            sec = None
        if sec in cov:
            cov[sec]["items_supplied"] += 1
        it, reason = _validate_item(raw, sectors, as_of, window)
        if it is not None:
            valid.append(it)
            continue
        if sec in cov:
            d = cov[sec]["items_dropped_by_reason"]
            d[reason] = d.get(reason, 0) + 1
        else:
            unattributed[reason] = unattributed.get(reason, 0) + 1
    if not valid:
        _refuse("NOSOURCE")

    groups = {}
    for it in valid:
        groups.setdefault(it["url"], []).append(it)
    kept, dup_count = [], 0
    for url in sorted(groups):
        g = sorted(groups[url], key=lambda x: (-GRADE_RANK[x["grade"]],
                                               -datetime.date.fromisoformat(x["published"]).toordinal(),
                                               x["id"]))
        kept.append(g[0])
        for lost in g[1:]:
            dup_count += 1
            d = cov[lost["sector"]]["items_dropped_by_reason"]
            d["duplicate_url"] = d.get("duplicate_url", 0) + 1

    out_sectors = {s: {"breakthroughs": [], "notable": [], "unverified": []} for s in sectors}
    candidates = []
    total_cut = 0
    for s in sectors:
        mine = [it for it in kept if it["sector"] == s]
        cov[s]["items_used"] = len(mine)
        ranked, notable, unver = [], [], []
        for it in mine:
            sc = _score(it, window)
            if it["grade"] in WEIGHT and sc > 0:
                ranked.append((it, sc))
            elif it["grade"] == "D":
                unver.append(it)
            else:
                notable.append(it)
        ranked.sort(key=lambda p: (-p[1], p[0]["id"]))
        cov[s]["cut_top_n"] = max(0, len(ranked) - top_n)
        total_cut += cov[s]["cut_top_n"]
        for n, (it, sc) in enumerate(ranked[:top_n], 1):
            row = _view(it, sc)
            row["rank"] = n
            out_sectors[s]["breakthroughs"].append(row)
            if row["integrable_open_source"]:
                candidates.append({"id": it["id"], "sector": s, "title": it["title"],
                                   "url": it["url"], "license": it["license"],
                                   "action": "ticket_stub_only_no_install"})
        for it in sorted(notable, key=lambda x: x["id"]):
            extra = ("no_positive_delta",) if it["grade"] in WEIGHT else ()
            out_sectors[s]["notable"].append(_view(it, None, extra))
        # eligible items cut by top_n are still shown, unranked, under notable
        for it, sc in ranked[top_n:]:
            out_sectors[s]["notable"].append(_view(it, None, ("cut_top_n",)))
        for it in sorted(unver, key=lambda x: x["id"]):
            out_sectors[s]["unverified"].append(_view(it))
    metric_drop_counts = dict.fromkeys(METRIC_DROP_REASONS, 0)
    for it in kept:
        for r in it["metric_drops"]:
            metric_drop_counts[r] = metric_drop_counts.get(r, 0) + 1
    coverage = {"by_sector": cov, "metrics_dropped_by_reason": dict(sorted(metric_drop_counts.items())), "duplicate_url_count": dup_count,
                "unattributed_dropped_by_reason": dict(sorted(unattributed.items())),
                "cut_top_n": total_cut, "sectors_covered": sectors}
    scope = policy.scope(
        ["ranking of supplied items by supplied-label grade and computed metric deltas",
         "url dedupe", "window filter", "open-source ticket stubs"],
        ["training or modelling (no compute)", "external verification of any claim",
         "fetching or scraping releases", "installation of any tool",
         "coverage of sectors beyond those supplied"],
        "supplied request items only, no network", as_of_raw)
    return {"as_of": as_of_raw, "window_days": window, "top_n": top_n,
            "breakthroughs_by_sector": out_sectors, "coverage": coverage, "integration_candidates": sorted(candidates, key=lambda c: (c["sector"], c["id"])),
            "scope": scope}


def to_json(report):
    """Deterministic serialization."""
    return json.dumps(report, sort_keys=True, separators=(",", ":"))
