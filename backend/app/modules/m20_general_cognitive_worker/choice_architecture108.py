"""Row 108 Choice Architecture (ledger: "Organizes options to influence decisions").

Ethical-use review of how a set of options is presented. Delta against the existing
_choice_architecture in negotiation_behavior_0085_0109.py: exact Pareto dominance with the
first dominator named, named failures in fixed order, bounded integer attributes, no float
interval. Checks structure only; no prediction of choices and no advice.
"""

ROW = 108
_P = "CHOICE108: "
_KEYS = ("options", "default", "attributes", "easy_opt_out", "transparent", "alternatives_visible")
_FLAGS = ("easy_opt_out", "transparent", "alternatives_visible")
_LIMITS = [
    "Supplied declarations only; higher attribute values are treated as better for every attribute.",
    "Dominated options and all material attributes must stay visible to the person choosing.",
    "Not a prediction of any choice and not advice; this checks the structure of a choice, not what people should pick.",
]


class ChoiceError(ValueError):
    pass


def _fail(msg):
    raise ChoiceError(_P + msg)


def review(data):
    if not isinstance(data, dict):
        _fail("input must be a mapping")
    for k in _KEYS:
        if k not in data:
            _fail(k + " required")
    for k in data:
        if k not in _KEYS:
            _fail("unknown key " + str(k))
    for k in _FLAGS:
        if not isinstance(data[k], bool):
            _fail(k + " must be true or false")
    opts = data["options"]
    if not isinstance(opts, list) or not 2 <= len(opts) <= 20:
        _fail("options must be a list of 2 to 20 items")
    for o in opts:
        if not isinstance(o, str) or not o.strip() or len(o) > 100:
            _fail("each option must be non-empty text of at most 100 characters")
    if len(set(opts)) != len(opts):
        _fail("duplicate option")
    if data["default"] not in opts:
        _fail("default must be one of the options")
    attrs = data["attributes"]
    if not isinstance(attrs, dict) or set(attrs) != set(opts):
        _fail("attributes must be a mapping with exactly the option names as keys")
    width = None
    for o in opts:
        row = attrs[o]
        if not isinstance(row, list) or not 1 <= len(row) <= 10:
            _fail("attributes per option must be a list of 1 to 10 values")
        if width is None:
            width = len(row)
        elif len(row) != width:
            _fail("every option needs the same number of attributes")
        for v in row:
            if isinstance(v, bool) or not isinstance(v, int) or abs(v) > 10**6:
                _fail("attribute value must be an integer within 1000000 of zero")
    dominated = []
    for o in opts:
        for p in opts:
            if p != o and all(a >= b for a, b in zip(attrs[p], attrs[o])) and any(a > b for a, b in zip(attrs[p], attrs[o])):
                dominated.append({"option": o, "by": p})
                break
    dom = {d["option"] for d in dominated}
    failures = []
    if data["default"] in dom:
        failures.append("default_dominated")
    if not data["easy_opt_out"]:
        failures.append("opt_out_not_easy")
    if not data["transparent"]:
        failures.append("not_transparent")
    if not data["alternatives_visible"]:
        failures.append("alternatives_hidden")
    return {
        "row": ROW,
        "dominated": dominated,
        "pareto_front": [o for o in opts if o not in dom],
        "burden_units": len(opts) * width,
        "over_choice_limit": len(opts) > 7,
        "failures": failures,
        "allowed": not failures,
        "limits": list(_LIMITS),
    }
