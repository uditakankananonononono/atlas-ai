"""Row 1524 Human Factors Engineering: use-error risk framing over supplied tasks.

Pure computation over caller-supplied tasks, use errors with caller-assigned
severity and likelihood (integers 1..5), and mitigation references. Computes
risk_index = severity * likelihood, a fixed band (this unit's convention, not
a standard), unmitigated-high lists, and reference checks. It runs no usability
study, validates nothing with users, and claims no human-factors compliance.
"""
import unicodedata
MAX_TASKS = 64
MAX_USERS = 64
MAX_MITIGATIONS = 128
MAX_ERRORS = 32
MAX_MITIGATION_IDS = 16
MAX_PARTICIPANTS = 64
MAX_TEXT = 128
HIGH_AT = 15
MEDIUM_AT = 8

_TOP = frozenset(("users", "tasks", "mitigations", "validation_participants"))
_USER = frozenset(("id", "role"))
_TASK = frozenset(("id", "name", "safety_consequence", "use_errors"))
_ERROR = frozenset(("id", "description", "severity", "likelihood", "mitigation_ids"))
_MIT = frozenset(("id", "description"))
_PART = frozenset(("id",))


def _fail(code):
    raise ValueError("HUMANF1524:" + code)


_BAD_CHARS = frozenset("\x7f\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")


def _has_forbidden(value):
    return any(c in _BAD_CHARS or unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in value)


MAX_KEYS = 64


def _extra(d, allowed):
    # key count is checked before any set construction or iteration
    if len(d) > MAX_KEYS:
        _fail("invalid_count:keys")
    return set(d) - allowed


def _text(value, field):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT or not value.strip() or _has_forbidden(value):
        _fail("invalid_text:" + field)
    return value


def _items(value, name, lo, hi, allowed):
    if type(value) is not list or not lo <= len(value) <= hi:
        _fail("invalid_count:" + name)
    for item in value:
        if type(item) is not dict:
            _fail("invalid_item:" + name)
        if _extra(item, allowed):
            _fail("unknown_key")
    return value


def _unique(rows, name):
    seen = set()
    for row in rows:
        ident = _text(row.get("id"), "id")
        if ident in seen:
            _fail("duplicate_id:" + name)
        seen.add(ident)
    return seen


def _scale(value, field):
    if type(value) is not int or not 1 <= value <= 5:
        _fail("invalid_scale:" + field)
    return value


def _band(index):
    return "high" if index >= HIGH_AT else "medium" if index >= MEDIUM_AT else "low"


def run(request):
    if type(request) is not dict:
        _fail("invalid_request")
    if _extra(request, _TOP):
        _fail("unknown_key")
    users = _items(request.get("users", []), "users", 0, MAX_USERS, _USER)
    tasks = _items(request.get("tasks"), "tasks", 1, MAX_TASKS, _TASK)
    mits = _items(request.get("mitigations", []), "mitigations", 0, MAX_MITIGATIONS, _MIT)
    parts = _items(request.get("validation_participants", []), "validation_participants", 0, MAX_PARTICIPANTS, _PART)
    _unique(users, "users")
    for user in users:
        _text(user.get("role"), "role")
    _unique(tasks, "tasks")
    mit_ids = _unique(mits, "mitigations")
    for mit in mits:
        _text(mit.get("description"), "description")
    _unique(parts, "validation_participants")
    out_tasks, unmitigated_high, top, error_count = [], [], 0, 0
    for task in tasks:
        _text(task.get("name"), "name")
        if type(task.get("safety_consequence")) is not bool:
            _fail("invalid_bool:safety_consequence")
        errors = _items(task.get("use_errors", []), "use_errors", 0, MAX_ERRORS, _ERROR)
        _unique(errors, "use_errors")
        rows = []
        for err in errors:
            _text(err.get("description"), "description")
            sev = _scale(err.get("severity"), "severity")
            lik = _scale(err.get("likelihood"), "likelihood")
            ids = err.get("mitigation_ids", [])
            if type(ids) is not list or len(ids) > MAX_MITIGATION_IDS:
                _fail("invalid_count:mitigation_ids")
            for mid in ids:
                _text(mid, "mitigation_ids")
                if mid not in mit_ids:
                    _fail("unknown_mitigation")
            index = sev * lik
            band = _band(index)
            mitigated = len(ids) > 0
            if band == "high" and not mitigated:
                unmitigated_high.append(task["id"] + "/" + err["id"])
            top = max(top, index)
            rows.append({"id": err["id"], "severity": sev, "likelihood": lik, "risk_index": index, "band": band,
                         "mitigated": mitigated, "mitigation_ids": list(ids)})
        rows.sort(key=lambda r: (-r["risk_index"], r["id"]))
        error_count += len(rows)
        out_tasks.append({"id": task["id"], "name": task["name"], "critical": task["safety_consequence"],
                          "use_errors": rows})
    return {"tasks": out_tasks, "unvalidated": True, "usability_study_claimed": False,
            "summary": {"task_count": len(tasks), "error_count": error_count, "max_risk_index": top,
                        "unmitigated_high_ids": sorted(unmitigated_high),
                        "validation_participant_count": len(parts)}}
