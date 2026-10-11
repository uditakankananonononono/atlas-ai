"""Row 692 Mob Programming ("Teams on one problem").

Stdlib-only scheduler and auditor for a mob session: one shared task, one
driver at the keyboard, one navigator, everyone else in the mob. The navigator
becomes the next driver and the previous driver moves to the back of the queue.

This plans and audits a session. It does not run a session, talk to people or
touch any external system. Output is review-only.
"""
from __future__ import annotations

import math
import unicodedata

METHOD = "mob_programming"


MAX_PARTICIPANTS=32
MAX_SESSION_MINUTES=1440
MAX_TURNS=2000
MAX_LOG=2000
MAX_TIME=1000000


def _pos_int(name,v):
    if type(v) is not int or not 0<v<=MAX_SESSION_MINUTES:
        raise ValueError(f"{name} must be a positive integer at most {MAX_SESSION_MINUTES}")
    return v


def _text(v,name,cap):
    if type(v) is not str:raise ValueError(f"{name} must be non-empty text")
    if len(v)>cap:raise ValueError(f"{name} exceeds raw text cap")
    if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in v):raise ValueError(f"{name} control characters refused")
    if not v.strip():raise ValueError(f"{name} must be non-empty text")
    return v.strip()


def _people(participants):
    if type(participants) not in (list,tuple):raise ValueError("participants must be a list of names")
    if len(participants)>MAX_PARTICIPANTS:raise ValueError("participants exceeds count cap")
    if len(participants)<3:raise ValueError("a mob needs at least 3 participants")
    for p in participants:
        if type(p) is str and len(p)>200:raise ValueError("participants exceeds raw text cap")
    names=[_text(p,'participants',200) for p in participants]
    if len(set(names))!=len(names):raise ValueError("participants must be unique")
    return names


def _honesty():
    return {'session_executed':False,'evidence_independently_verified':False,'human_review_required':True}


def plan_mob_session(participants, task, session_minutes, rotation_minutes,
                     start_driver=None, break_every_minutes=None, break_minutes=5):
    if type(participants) in (list,tuple) and len(participants)>MAX_PARTICIPANTS:raise ValueError("participants exceeds count cap")
    if type(task) is str and len(task)>2000:raise ValueError("task exceeds raw text cap")
    names = _people(participants)
    task=_text(task,"task",2000)
    _pos_int("session_minutes", session_minutes)
    _pos_int("rotation_minutes", rotation_minutes)
    if rotation_minutes > session_minutes:
        raise ValueError("rotation_minutes must not exceed session_minutes")
    _pos_int("break_minutes", break_minutes)
    if break_every_minutes is not None:
        _pos_int("break_every_minutes", break_every_minutes)
    count=(session_minutes+rotation_minutes-1)//rotation_minutes
    full_break_turns=(break_every_minutes+rotation_minutes-1)//rotation_minutes if break_every_minutes is not None else None
    break_count=(count-1)//full_break_turns if full_break_turns else 0
    if count+break_count>MAX_TURNS:raise ValueError("turns exceeds count cap")
    queue = list(names)
    if start_driver is not None:
        start_driver=_text(start_driver,"start_driver",200)
        if start_driver not in queue:
            raise ValueError("start_driver must be one of the participants")
        i = queue.index(start_driver)
        queue = queue[i:] + queue[:i]
    turns, clock, worked, since_break = [], 0, 0, 0
    dm = {n: 0 for n in names}
    while worked < session_minutes:
        length = min(rotation_minutes, session_minutes - worked)
        turns.append({"kind": "turn", "driver": queue[0], "navigator": queue[1],
                      "mob": queue[2:], "start_minute": clock,
                      "end_minute": clock + length, "minutes": length})
        dm[queue[0]] += length
        clock += length
        worked += length
        since_break += length
        queue = queue[1:] + queue[:1]
        if (break_every_minutes is not None and since_break >= break_every_minutes
                and worked < session_minutes):
            turns.append({"kind": "break", "start_minute": clock,
                          "end_minute": clock + break_minutes, "minutes": break_minutes})
            clock += break_minutes
            since_break = 0
    return {
        "method": METHOD, "task": task.strip(), "participants": names,
        "turns": turns, "driver_minutes": dm,
        "driver_minutes_spread": max(dm.values()) - min(dm.values()),
        "everyone_drives": all(v > 0 for v in dm.values()),
        "work_minutes": worked, "total_wall_minutes": clock,
        **_honesty(),
    }


def audit_session_log(log, participants, max_driver_share=0.5):
    if type(log) is not list:raise ValueError("log must be a list")
    if len(log)>MAX_LOG:raise ValueError("log exceeds count cap")
    if type(max_driver_share) not in (int,float) or not 0<max_driver_share<=1 or not math.isfinite(max_driver_share):
        raise ValueError("max_driver_share must be finite in (0,1]")
    names = _people(participants)
    for e in log:
        if type(e) is not dict:raise ValueError("log entry must be a dict")
        if len(e)>3:raise ValueError("log entry exceeds key cap")
        if any(type(k) is not str for k in e):raise ValueError("log key must be exact text")
        if set(e)!={'driver','start_minute','end_minute'}:raise ValueError("log entry keys refused")
        if type(e['driver']) is str and len(e['driver'])>200:raise ValueError("driver exceeds raw text cap")

    v, dm = [], {n: 0 for n in names}
    if not log:
        return {"ok": False, "violations": [{"code": "empty_log"}], "driver_minutes": dm,
                "never_drove": list(names), **_honesty()}
    good = []
    for i, e in enumerate(log):
        d, s, t = _text(e["driver"],"driver",200), e["start_minute"], e["end_minute"]
        for minute in (s,t):
            if type(minute) not in (int,float) or not 0<=minute<=MAX_TIME or not math.isfinite(minute):
                raise ValueError("log minutes must be finite in [0,1000000]")
        if d not in dm:
            v.append({"code": "unknown_driver", "index": i, "driver": d})
            continue
        if not (isinstance(s, (int, float)) and isinstance(t, (int, float))) or t <= s or s < 0:
            v.append({"code": "bad_interval", "index": i})
            continue
        good.append((s, t, d, i))
        dm[d] += t - s
    good.sort()
    for a, b in zip(good, good[1:]):
        if b[0] < a[1]:
            v.append({"code": "overlap", "index": b[3], "with_index": a[3]})
    total = sum(dm.values())
    if total and len(names) > 1:
        for n, m in dm.items():
            if m / total > max_driver_share:
                v.append({"code": "driver_share_exceeded", "driver": n,
                          "share": round(m / total, 4)})
    never = [n for n in names if dm[n] == 0]
    for n in never:
        v.append({"code": "never_drove", "driver": n})
    return {"ok": not v, "violations": v, "driver_minutes": dm, "never_drove": never,
            **_honesty()}
