"""P260|L207 (output-format) self-improvement plans register. Source pin: instinct doc P260|L207, line map v4: "Output: Self-improvement plans".

Registry only: it records and renders caller-supplied per-tool dated plan artifacts and their status. It implements no
self-improvement (the P61|L52 line is separate), reads no clock, does no I/O and verifies no claim. See
docs/INSTINCT_P260_L207_IMPROVEMENT_REGISTER_CONTRACT.md. Field names, statuses, transitions and codes are interpretation choices.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date as _date

STATUSES = ("proposed", "approved", "in_progress", "done", "dropped")
TRANSITIONS = {"proposed": ("approved", "dropped"), "approved": ("in_progress", "dropped"), "in_progress": ("done", "dropped"), "done": (), "dropped": ()}
FIELDS = ("id", "tool", "date", "title", "summary", "source_ref", "status")
TEXT_LIMITS = {"id": 64, "tool": 64, "title": 128, "summary": 256, "source_ref": 128, "status": 16}
MAX_PLANS = 1024
MAX_TOOLS = 128
_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_BAD_CATEGORIES = ("Cc", "Zl", "Zp")


@dataclass(frozen=True)
class Register:
    plans: tuple = ()  # tuple of (id, tool, date, title, summary, source_ref, status, history)


def create_register() -> Register:
    return Register()


def _err(code: str) -> ValueError:
    return ValueError("P260:" + code)


def _text(value, name: str, limit: int | None = None) -> str:
    """Type, blank, control-character and length checks; the code never contains the offending value."""
    if type(value) is not str:
        raise _err("bad_type:" + name)
    if any(unicodedata.category(c) in _BAD_CATEGORIES for c in value):
        raise _err("control_char:" + name)
    if not value.strip():
        raise _err("empty_field:" + name)
    if limit is not None and len(value) > limit:
        raise _err("text_too_long:" + name)
    return value


def _date_value(value, name: str = "date") -> str:
    _text(value, name)
    if not re.fullmatch(_DATE, value):
        raise _err("bad_date")
    try:
        _date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        raise _err("bad_date") from None
    return value


def _status_value(value, name: str = "status") -> str:
    _text(value, name, TEXT_LIMITS["status"])
    if value not in STATUSES:
        raise _err("bad_status:" + value)
    return value


def _check_register(reg) -> None:
    if type(reg) is not Register:
        raise _err("bad_type:register")


def _validate(plan) -> tuple:
    if type(plan) is not dict:
        raise _err("bad_type:plan")
    if any(type(k) is not str or k not in FIELDS for k in plan):
        raise _err("unknown_fields:plan")
    for name in FIELDS:
        if name not in plan:
            raise _err("empty_field:" + name)
    for name in FIELDS:
        if type(plan[name]) is not str:
            raise _err("bad_type:" + name)
    for name in FIELDS:
        if any(unicodedata.category(c) in _BAD_CATEGORIES for c in plan[name]):
            raise _err("control_char:" + name)
    for name in FIELDS:
        if not plan[name].strip():
            raise _err("empty_field:" + name)
    for name in ("id", "tool", "title", "summary", "source_ref"):
        if len(plan[name]) > TEXT_LIMITS[name]:
            raise _err("text_too_long:" + name)
    _date_value(plan["date"])
    _status_value(plan["status"])
    return tuple(plan[name] for name in FIELDS)


def add_plan(reg: Register, plan) -> Register:
    _check_register(reg)
    pid, tool, day, title, summary, ref, status = _validate(plan)
    if any(p[0] == pid for p in reg.plans):
        raise _err("duplicate_id:" + pid)
    if len(reg.plans) >= MAX_PLANS:
        raise _err("limit_exceeded:plans")
    if all(p[1] != tool for p in reg.plans) and len({p[1] for p in reg.plans}) >= MAX_TOOLS:
        raise _err("limit_exceeded:tools")
    return Register(reg.plans + ((pid, tool, day, title, summary, ref, status, ((status, day),)),))


def _record(p: tuple) -> dict:
    return {"id": p[0], "tool": p[1], "date": p[2], "title": p[3], "summary": p[4], "source_ref": p[5], "status": p[6],
            "history": [{"status": s, "date": d} for s, d in p[7]], "registry_only": True, "implements_self_improvement": False}


def get_plan(reg: Register, plan_id) -> dict:
    _check_register(reg)
    _text(plan_id, "plan_id", TEXT_LIMITS["id"])
    for p in reg.plans:
        if p[0] == plan_id:
            return _record(p)
    raise _err("unknown_plan:" + plan_id)


def update_status(reg: Register, plan_id, status, as_of) -> Register:
    _check_register(reg)
    _text(plan_id, "plan_id", TEXT_LIMITS["id"])
    _status_value(status)
    _date_value(as_of)
    for i, p in enumerate(reg.plans):
        if p[0] == plan_id:
            break
    else:
        raise _err("unknown_plan:" + plan_id)
    if status not in TRANSITIONS[p[6]]:
        raise _err("bad_transition:%s>%s" % (p[6], status))
    if as_of < p[7][-1][1]:
        raise _err("date_regression:" + plan_id)
    updated = p[:6] + (status, p[7] + ((status, as_of),))
    return Register(reg.plans[:i] + (updated,) + reg.plans[i + 1:])


def _sorted(plans) -> list:
    return sorted(plans, key=lambda p: (p[2], p[0]))


def list_plans(reg: Register, tool=None, status=None) -> list:
    _check_register(reg)
    if tool is not None:
        _text(tool, "tool", TEXT_LIMITS["tool"])
    if status is not None:
        _status_value(status)
    return [_record(p) for p in _sorted(reg.plans) if (tool is None or p[1] == tool) and (status is None or p[6] == status)]


def render(reg: Register, tool=None) -> str:
    _check_register(reg)
    if tool is None:
        tools = sorted({p[1] for p in reg.plans})
    else:
        _text(tool, "tool", TEXT_LIMITS["tool"])
        if all(p[1] != tool for p in reg.plans):
            raise _err("unknown_tool:" + tool)
        tools = [tool]
    lines = []
    for t in tools:
        mine = _sorted(p for p in reg.plans if p[1] == t)
        lines.append("tool %s (%d plan%s)" % (t, len(mine), "" if len(mine) == 1 else "s"))
        for p in mine:
            lines.append("%s %s %s %s - %s [%s]" % (p[2], p[0], p[6], p[3], p[4], p[5]))
    return "\n".join(lines)
