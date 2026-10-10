"""Pure supplied-input estimates. No imports of app state or external effects.

The standalone v1 interface is defined in COST_ESTIMATE_CONTRACT_02.md.
Missing/None values are unknown, never implicit zero. Invalid known inputs
raise ValueError, including mismatched currencies even beside unknown amounts.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, localcontext
import re

__all__ = ["estimate_net_cost", "summarize_awards"]
_COST_KEYS = ("tuition", "fees", "living")
_BOUNDARY = "Supplied-input estimate only. No payment, aid, renewal or eligibility guarantee."
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _object(value, path):
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _number(value, path, unknown):
    if value is None:
        unknown.append(path)
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"{path} must be a nonnegative finite decimal number")
    text = str(value)
    if len(text) > 128 or not _NUMBER.fullmatch(text):
        raise ValueError(f"{path} must be a nonnegative finite decimal number")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{path} must be a decimal number") from exc
    # Explicit arithmetic bounds prevent unbounded rendering and precision loss.
    if not number.is_finite() or number < 0 or number > Decimal("1e30"):
        raise ValueError(f"{path} must be finite, nonnegative and at most 1e30")
    if number.as_tuple().exponent < -28 or number.as_tuple().exponent > 30:
        raise ValueError(f"{path} exponent must be between -28 and 30")
    return number


def _currency(value, path, unknown):
    if value is None:
        unknown.append(path)
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError(f"{path} must be a three-letter uppercase currency label")
    return value


def _money(value, path, currencies, unknown):
    if value is None:
        unknown.extend((f"{path}.amount", f"{path}.currency"))
        return None
    row = _object(value, path)
    amount = _number(row.get("amount"), f"{path}.amount", unknown)
    currency = _currency(row.get("currency"), f"{path}.currency", unknown)
    if currency is not None:
        currencies.add(currency)
    return amount


def _rows(value, path, unknown):
    if value is None:
        unknown.append(path)
        return []
    if not isinstance(value, list) or len(value) > 500:
        raise ValueError(f"{path} must be a list of at most 500 objects")
    return value


def _compatible(currencies):
    if len(currencies) > 1:
        raise ValueError("Mixed currencies are not supported; no conversion or sum performed")


def _text(value):
    if value is None:
        return None
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def estimate_net_cost(data: Mapping) -> dict:
    """Estimate flat annual costs minus an explicit caller-supplied aid schedule.

    aid timing is annual (prorated by supplied years) or program_total (once).
    This does not verify that aid is offered, accepted, renewable or payable.
    """
    data = _object(data, "data")
    unknown, currencies = [], set()
    currency = _currency(data.get("currency"), "currency", unknown)
    if currency is not None:
        currencies.add(currency)
    years = _number(data.get("years"), "years", unknown)
    costs = data.get("annual_costs")
    costs = {} if costs is None else _object(costs, "annual_costs")
    amounts = [_money(costs.get(key), f"annual_costs.{key}", currencies, unknown)
               for key in _COST_KEYS]
    aid_entries = []
    for index, value in enumerate(_rows(data.get("aid"), "aid", unknown)):
        path = f"aid[{index}]"
        row = _object(value, path)
        amount = _money(row, path, currencies, unknown)
        timing = row.get("timing")
        if timing is None:
            unknown.append(f"{path}.timing")
        elif timing not in ("annual", "program_total"):
            raise ValueError(f"{path}.timing must be annual or program_total")
        aid_entries.append((amount, timing))
    _compatible(currencies)
    with localcontext() as context:
        context.prec = 200
        gross = sum(amounts, Decimal(0)) * years if years is not None and all(
            x is not None for x in amounts) else None
        # Unknown currency prevents presentation of a numerical money estimate.
        ready = not unknown
        aid_total = sum((amount * years if timing == "annual" else amount
                         for amount, timing in aid_entries), Decimal(0)) if ready else None
        net = max(Decimal(0), gross - aid_total) if ready else None
        excess = max(Decimal(0), aid_total - gross) if ready else None
        return {"status": "unknown_inputs" if unknown else "estimated",
                "currency": currency, "years": _text(years),
                "gross_cost": _text(gross) if currency is not None and not any(
                    path.startswith("annual_costs.") for path in unknown) else None,
                "aid_scenario_total": _text(aid_total), "net_cost": _text(net),
                "unapplied_aid": _text(excess), "unknown_inputs": sorted(set(unknown)),
                "estimate_only": True, "boundary": _BOUNDARY}


def summarize_awards(data: Mapping) -> dict:
    """Sum same-currency face amounts, never mix annual and total timings.

    Totals are not disbursement forecasts and do not establish available funds.
    accepted must be a literal bool; missing/None makes that subtotal unknown.
    """
    data = _object(data, "data")
    unknown, currencies = [], set()
    currency = _currency(data.get("currency"), "currency", unknown)
    if currency is not None:
        currencies.add(currency)
    parsed, timings = [], set()
    for index, value in enumerate(_rows(data.get("awards"), "awards", unknown)):
        path = f"awards[{index}]"
        row = _object(value, path)
        amount = _money(row, path, currencies, unknown)
        timing = row.get("timing")
        if timing is None:
            unknown.append(f"{path}.timing")
        elif timing not in ("annual", "program_total"):
            raise ValueError(f"{path}.timing must be annual or program_total")
        else:
            timings.add(timing)
        accepted = row.get("accepted")
        if accepted is None:
            unknown.append(f"{path}.accepted")
        elif type(accepted) is not bool:
            raise ValueError(f"{path}.accepted must be true or false")
        parsed.append((amount, accepted))
    _compatible(currencies)
    if len(timings) > 1:
        raise ValueError("Mixed award timings are not supported; no sum performed")
    face_unknown = [path for path in unknown if not path.endswith(".accepted")]
    with localcontext() as context:
        context.prec = 200
        offered = sum((amount for amount, _ in parsed), Decimal(0)) if not face_unknown else None
        accepted_total = sum((amount for amount, accepted in parsed if accepted is True),
                             Decimal(0)) if not unknown else None
        return {"status": "unknown_inputs" if unknown else "estimated",
                "currency": currency, "timing": next(iter(timings)) if timings else None,
                "total_offered": _text(offered), "accepted_total": _text(accepted_total),
                "unknown_inputs": sorted(set(unknown)), "award_count": len(parsed),
                "estimate_only": True, "boundary": _BOUNDARY}
