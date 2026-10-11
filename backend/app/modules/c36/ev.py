"""S7.1 / c36.ev - opportunity EV ranker.

Ranks candidate money-making opportunities (scholarships, grants, prizes,
gigs, side hustles) by expected value computed from SUPPLIED numbers, with
explicit low/high uncertainty. It never promises income and holds no authority
to spend, send, post, trade or open accounts: an opportunity that needs cash
or a spend is listed separately and is never actionable here.

Stdlib only, offline, deterministic. Arithmetic is exact (Fraction); output
floats are rounded to 6 places.
"""
from __future__ import annotations

import math
from datetime import date
from fractions import Fraction
from itertools import combinations

from app.modules.c30 import policy

PREFIX = "MONEY"
BANNER = "Expected values from supplied estimates; not a promise of income."
SPEND_NOTE = "spending needs the owner's separate per-action approval outside this unit"
KINDS = ("scholarship", "grant", "prize", "gig", "hustle")
GUARANTEE_PHRASES = ("guarantee", "risk-free", "risk free", "will earn", "sure thing",
                     "certain profit")
MAX_OPPS = 256
MAX_BRUTE = 15
TEXT_LIMIT = 512


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _text(value, name):
    try:
        text = policy.clean_text(value, PREFIX, name, TEXT_LIMIT)
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    low = text.lower()
    if any(p in low for p in GUARANTEE_PHRASES):
        _refuse("GUARANTEE", name)
    return text


def _num(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        _refuse("BAD_TYPE", field)
    f = Fraction(repr(value)) if isinstance(value, float) else Fraction(value)
    if minimum is not None and f < minimum:
        _refuse("BAD_TYPE", field)
    if maximum is not None and f > maximum:
        _refuse("BAD_TYPE", field)
    return f


def _prob(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        _refuse("BADPROB", field)
    f = Fraction(repr(value)) if isinstance(value, float) else Fraction(value)
    if f < 0 or f > 1:
        _refuse("BADPROB", field)
    return f


def _date(value, field):
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        _refuse("BAD_TYPE", field)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _refuse("BAD_TYPE", field)


def _currency(value, field):
    if not isinstance(value, str) or len(value) != 3 or not value.isascii() \
            or not value.isalpha() or not value.isupper():
        _refuse("BAD_TYPE", field)
    return value


def _need(d, key, path=""):
    if key not in d or d[key] is None:
        _refuse("NOINPUT", path + key)
    return d[key]


def _f(x):
    return round(float(x), 6) + 0.0


def _original(x):
    return int(x) if x.denominator == 1 else _f(x)


def _fx_table(fx, base):
    """Validated {currency: (rate Fraction, rate float, as_of str)}."""
    if fx is None:
        return {}
    if not isinstance(fx, dict):
        _refuse("CURRENCY", "fx")
    as_of = fx.get("as_of")
    try:
        _date(as_of, "fx.as_of")
    except ValueError:
        _refuse("CURRENCY", "fx.as_of")
    rates = fx.get("rates_to_base")
    if not isinstance(rates, dict):
        _refuse("CURRENCY", "fx.rates_to_base")
    table = {}
    for cur, rate in rates.items():
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) \
                or not math.isfinite(rate) or rate <= 0:
            _refuse("CURRENCY", "fx.rates_to_base")
        if cur != base:
            table[cur] = (Fraction(repr(rate)) if isinstance(rate, float) else Fraction(rate),
                          rate, as_of)
    return table


def _rate(cur, base, table):
    if cur == base:
        return Fraction(1)
    if cur not in table:
        _refuse("CURRENCY", cur)
    return table[cur][0]


def _parse(o, base, as_of, table, hourly):
    if not isinstance(o, dict):
        _refuse("BAD_TYPE", "opportunity")
    oid = _text(_need(o, "id"), "id")
    name = _text(_need(o, "name"), "name")
    kind = _need(o, "kind")
    if kind not in KINDS:
        _refuse("BAD_TYPE", "kind")
    notes = _text(o["notes"], "notes") if o.get("notes") is not None else None
    label = _text(o["label"], "label") if o.get("label") is not None else None
    url = _text(_need(o, "source_url"), "source_url")
    pay = _need(o, "payoff")
    if not isinstance(pay, dict):
        _refuse("BAD_TYPE", "payoff")
    lo = _num(_need(pay, "low", "payoff."), "payoff.low", 0)
    ba = _num(_need(pay, "base", "payoff."), "payoff.base", 0)
    hi = _num(_need(pay, "high", "payoff."), "payoff.high", 0)
    if not lo <= ba <= hi:
        _refuse("BAD_TYPE", "payoff")
    pcur = _currency(_need(pay, "currency", "payoff."), "payoff.currency")
    ps = _need(o, "p_success")
    if not isinstance(ps, dict):
        _refuse("BADPROB", "p_success")
    pp = _prob(_need(ps, "point", "p_success."), "p_success.point")
    pl = _prob(_need(ps, "low", "p_success."), "p_success.low")
    ph = _prob(_need(ps, "high", "p_success."), "p_success.high")
    if not pl <= pp <= ph:
        _refuse("BADPROB", "p_success")
    cost = _need(o, "cost")
    if not isinstance(cost, dict):
        _refuse("BAD_TYPE", "cost")
    cash = _num(_need(cost, "cash", "cost."), "cost.cash", 0)
    hours = _num(_need(cost, "hours", "cost."), "cost.hours", 0)
    ccur = _currency(cost["currency"], "cost.currency") if cost.get("currency") is not None \
        else pcur
    deadline_s = _need(o, "deadline")
    deadline = _date(deadline_s, "deadline")
    spend = o.get("requires_spend", False)
    outreach = o.get("requires_outreach", False)
    if not isinstance(spend, bool):
        _refuse("BAD_TYPE", "requires_spend")
    if not isinstance(outreach, bool):
        _refuse("BAD_TYPE", "requires_outreach")
    rp = _rate(pcur, base, table)
    rc = _rate(ccur, base, table)
    cash_b = cash * rc
    time_cost = hours * hourly
    ev = pp * ba * rp - cash_b - time_cost
    ev_low = pl * lo * rp - cash_b - time_cost
    ev_high = ph * hi * rp - cash_b - time_cost
    days = (deadline - as_of).days
    weeks = max(1, -(-days // 7)) if days >= 0 else 0
    fx = {}
    for cur in sorted({pcur, ccur}):
        if cur != base:
            fx[cur] = {"rate_to_base": table[cur][1], "as_of": table[cur][2]}
    return {"id": oid, "name": name, "kind": kind, "notes": notes, "label": label,
            "url": url, "ev": ev, "ev_low": ev_low, "ev_high": ev_high, "hours": hours,
            "deadline": deadline_s, "days": days, "weeks": weeks,
            "cash_positive": cash_b > 0, "spend": spend, "outreach": outreach,
            "original": {"payoff": {"low": _original(lo), "base": _original(ba),
                                    "high": _original(hi), "currency": pcur},
                         "cash": {"amount": _original(cash), "currency": ccur}},
            "fx": fx or None, "_pcur": pcur, "_ccur": ccur}


def _order_key(x):
    return (-x["ev"], x["hours"], x["deadline"], x["id"])


def _row(x, rank=None):
    row = {"id": x["id"], "name": x["name"], "kind": x["kind"], "ev": _f(x["ev"]),
           "ev_low": _f(x["ev_low"]), "ev_high": _f(x["ev_high"]),
           "ev_per_hour": _f(x["ev"] / x["hours"]) if x["hours"] > 0 else None,
           "hours": _original(x["hours"]), "deadline": x["deadline"],
           "days_to_deadline": x["days"], "weeks_available": x["weeks"],
           "flags": ["draft_only_needs_approval"] if x["outreach"] else [],
           "source_url": x["url"], "original": x["original"], "fx": x["fx"]}
    if x["notes"] is not None:
        row["notes"] = x["notes"]
    if x["label"] is not None:
        row["label"] = x["label"]
    if rank is not None:
        row["rank"] = rank
    return row


def _feasible(items, weekly):
    """Deadline-ordered cumulative-hours check: by each deadline the chosen
    items' hours must fit weekly hours x weeks available at that deadline."""
    total = Fraction(0)
    for x in sorted(items, key=lambda z: (z["deadline"], z["id"])):
        total += x["hours"]
        if total > weekly * x["weeks"]:
            return False
    return True


def _greedy(items, weekly):
    pool = [x for x in items if x["ev"] > 0]
    pool.sort(key=lambda x: (0, 0, -x["ev"], x["id"]) if x["hours"] == 0
              else (1, -(x["ev"] / x["hours"]), -x["ev"], x["id"]))
    chosen, skipped = [], []
    for x in pool:
        if _feasible(chosen + [x], weekly):
            chosen.append(x)
        else:
            skipped.append(x)
    return chosen, skipped


def _usage(chosen, weekly):
    """Per member deadline d: hours of all members with deadline <= d against
    weekly hours x weeks available at d."""
    out = []
    for d in sorted({x["deadline"] for x in chosen}):
        members = [x for x in chosen if x["deadline"] <= d]
        out.append({"deadline": d, "weeks_available": next(x["weeks"] for x in chosen if x["deadline"] == d),
                    "used_hours": _original(sum((x["hours"] for x in members), Fraction(0))),
                    "capacity_hours": _original(weekly * next(
                        x["weeks"] for x in chosen if x["deadline"] == d))})
    return out


def _brute(items, weekly):
    pool = sorted(items, key=lambda x: x["id"])
    best, best_key = [], (Fraction(0), Fraction(0), ())
    for n in range(len(pool) + 1):
        for combo in combinations(pool, n):
            if not _feasible(list(combo), weekly):
                continue
            ev = sum((x["ev"] for x in combo), Fraction(0))
            hrs = sum((x["hours"] for x in combo), Fraction(0))
            key = (ev, -hrs, tuple(-1 for _ in ()))
            better = ev > best_key[0] or (ev == best_key[0] and hrs < -best_key[1]) or (
                ev == best_key[0] and hrs == -best_key[1]
                and [x["id"] for x in combo] < list(best_key[2]))
            if better:
                best, best_key = list(combo), (ev, -hrs, tuple(x["id"] for x in combo))
    return best


def _plan_block(chosen, weekly, skipped=None):
    block = {"selected": [x["id"] for x in chosen],
            "total_ev": _f(sum((x["ev"] for x in chosen), Fraction(0))),
            "total_hours": _original(sum((x["hours"] for x in chosen), Fraction(0))),
            "usage": _usage(chosen, weekly)}
    if skipped is not None:
        block["over_budget"] = sorted(x["id"] for x in skipped)
    return block


def run(request):
    """Rank supplied opportunities by EV; returns a plain dict or raises
    ValueError('MONEY_REFUSED_<REASON>[:field]')."""
    if not isinstance(request, dict):
        _refuse("BAD_TYPE", "request")
    as_of_s = _need(request, "as_of")
    as_of = _date(as_of_s, "as_of")
    weekly = _num(_need(request, "hours_budget_per_week"), "hours_budget_per_week", 0)
    hourly = _num(_need(request, "hourly_value"), "hourly_value", 0)
    base = _currency(_need(request, "currency"), "currency")
    opps = _need(request, "opportunities")
    if isinstance(opps, bool) or not isinstance(opps, (list, tuple)):
        _refuse("BAD_TYPE", "opportunities")
    if not opps:
        _refuse("EMPTY", "opportunities")
    if len(opps) > MAX_OPPS:
        _refuse("BAD_TYPE", "opportunities")
    table = _fx_table(request.get("fx"), base)
    items, seen = [], set()
    for o in opps:
        x = _parse(o, base, as_of, table, hourly)
        if x["id"] in seen:
            _refuse("BAD_TYPE", "id")
        seen.add(x["id"])
        items.append(x)
    expired = sorted((x for x in items if x["days"] < 0), key=lambda x: (x["deadline"], x["id"]))
    live = [x for x in items if x["days"] >= 0]
    held = sorted((x for x in live if x["cash_positive"] or x["spend"]), key=_order_key)
    actionable = sorted((x for x in live if not (x["cash_positive"] or x["spend"])),
                        key=_order_key)
    greedy, over = _greedy(actionable, weekly)
    over_ids = {x["id"] for x in over}
    ranked = []
    for i, x in enumerate(actionable, 1):
        row = _row(x, i)
        if x["id"] in over_ids:
            row["flags"] = row["flags"] + ["over_budget"]
        ranked.append(row)
    held_rows = []
    for x in held:
        row = _row(x)
        row["note"] = SPEND_NOTE
        held_rows.append(row)
    plan = {"method": "greedy by EV per hour (zero-hour items first), positive EV only, "
                      "kept feasible against deadline-cumulative hours budget",
            "hours_budget_per_week": _original(weekly),
            "greedy": _plan_block(greedy, weekly, over), "brute_force": None, "gap_ev": None}
    if len(actionable) <= MAX_BRUTE:
        opt = _brute([x for x in actionable if x["ev"] > 0], weekly)
        bf = _plan_block(opt, weekly)
        bf["considered"] = len(actionable)
        plan["brute_force"] = bf
        plan["gap_ev"] = _f(sum((x["ev"] for x in opt), Fraction(0))
                            - sum((x["ev"] for x in greedy), Fraction(0)))
    else:
        plan["brute_force_note"] = "not computed: more than %d actionable opportunities" % MAX_BRUTE
    warnings = []
    positive = [x for x in actionable if x["ev"] > 0]
    total_pos = sum((x["ev"] for x in positive), Fraction(0))
    for x in positive:
        if len(positive) > 1 and x["ev"] * 2 >= total_pos \
                and (x["ev_high"] - x["ev_low"]) > x["ev"]:
            warnings.append("single_item_dominates:" + x["id"])
    for x in actionable:
        if x["ev"] < 0:
            warnings.append("negative_ev:" + x["id"])
    warnings.sort()
    summary = "%s; %d supplied excluded as expired; %d held for separate approval" % (
        ("highest EV: %s (%s) of %d ranked supplied" % (_f(actionable[0]["ev"]),
                                                       actionable[0]["id"], len(actionable)))
        if actionable else "no actionable opportunity among %d supplied" % len(items),
        len(expired), len(held))
    return {
        "banner": BANNER, "as_of": as_of_s, "currency": base,
        "hourly_value": _original(hourly), "hours_budget_per_week": _original(weekly),
        "summary": summary, "ranked": ranked,
        "not_actionable_without_separate_approval": held_rows,
        "expired": [{"id": x["id"], "name": x["name"], "deadline": x["deadline"]}
                    for x in expired],
        "plan": plan, "warnings": warnings,
        "fx_used": [{"currency": c, "rate_to_base": table[c][1], "as_of": table[c][2]}
                    for c in sorted({k for x in items for k in (x["_pcur"], x["_ccur"])
                                     if k != base})],
        "scope": policy.scope(
            ["EV ranking over supplied estimates (EV from point, low and high inputs)",
             "greedy plan with exact brute-force comparison up to %d opportunities" % MAX_BRUTE,
             "offline FX conversion from a supplied dated rate table"],
            ["market data", "taxes", "spending, sending, posting, trading or account creation",
             "income promises"],
            "supplied opportunity estimates", as_of_s),
    }
