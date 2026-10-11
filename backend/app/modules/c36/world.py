"""S5.6 / c36.world - virtual world and AI people sim (toy, seeded, text only).

A deterministic simulation of SUPPLIED synthetic characters in a SUPPLIED small
world. It emits an event log and a text storyboard draft. It uses its own
integer generator (splitmix64), not the random module, so the output is
byte-identical across Python versions. Every character, event and frame is
labeled SYNTHETIC-AI and no input can turn that off. Nothing is published,
generated as media, or matched against real people. Stdlib only, offline.
"""
from __future__ import annotations

import re

from app.modules.c30 import policy

PREFIX = "VENT"
LABEL = "SYNTHETIC-AI"
MAX_AGENTS = 50
MAX_ID = 64
MAX_NAME = 100
MAX_TRAITS = 10
MAX_ACTIONS = 10
MAX_TRAIT_LEN = 64
MAX_ACTION_LEN = 64
MAX_PLACES = 30
MAX_PLACE_LEN = 100
MAX_WORLD_NAME = 100
MAX_STEPS = 100
MAX_SEED = 4294967295
MAX_PRODUCT = 200
MAX_AS_OF = 10
MAX_KIND = 64
# Request scan budget, checked before any container is read (blanket limits; the schema caps above are tighter).
MAX_CONTAINERS = 10000
MAX_DICT_KEYS = 32
MAX_LIST_ITEMS = 64
MAX_DEPTH = 32
MAX_KEY_LEN = 200  # raw request-key length, checked before normalization

TOP_KEYS = frozenset({"as_of", "seed", "world", "agents", "scenario"})
WORLD_KEYS = frozenset({"name", "places", "steps"})
AGENT_KEYS = frozenset({"id", "name", "traits", "actions"})
SCENARIO_KEYS = frozenset({"kind", "product"})
KINDS = ("commercial_storyboard", "daily_life")

# Forbidden request keys: casefold, "-" -> "_", exact match, any depth.
# Precedence: SEND > SPEND > DECEPTIVE > EFFECT > NOCREDS; the alphabetically first matched key is the suffix.
_KEY_RULES = (
    ("SEND", frozenset({"send", "approve", "approved", "approval", "approval_token", "smtp",
                        "token", "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})),
    ("DECEPTIVE", frozenset({"real_person", "likeness", "impersonate", "deepfake", "voice_clone",
                             "endorsement", "testimonial", "celebrity"})),
    ("EFFECT", frozenset({"publish", "post", "upload", "deploy", "broadcast", "advertise"})),
    ("NOCREDS", frozenset({"login", "password", "username", "credentials", "otp", "api_key",
                           "access_token", "refresh_token", "bearer", "pass", "passwd"})),
)
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})", re.ASCII)
_M64 = (1 << 64) - 1


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


_SCAN_TYPES = (dict, list, tuple)


def _scan_keys(request):
    """Steps 2 and 3, under a container budget checked before any container is read."""
    hits = {}
    non_str = False
    if type(request) not in _SCAN_TYPES:
        _refuse("BAD_TYPE", "request")
    seen = {id(request)}
    stack = [(request, 0)]
    while stack:
        node, depth = stack.pop()
        if type(node) is dict:
            if len(node) > MAX_DICT_KEYS:
                _refuse("OVERSIZE", "request")
            children = []
            for key, value in node.items():
                if type(key) is str:
                    if len(key) > MAX_KEY_LEN:
                        _refuse("OVERSIZE", "request")  # raw cap, before any normalization
                    norm = key.casefold().replace("-", "_")
                    for rule, keys in _KEY_RULES:
                        if norm in keys:
                            hits.setdefault(rule, set()).add(norm)
                elif isinstance(key, str):
                    _refuse("BAD_TYPE", "request")  # str subclass: refused untouched
                else:
                    non_str = True
                children.append(value)
        else:
            if len(node) > MAX_LIST_ITEMS:
                _refuse("OVERSIZE", "request")
            children = node
        for child in children:
            if isinstance(child, (dict, list, tuple)) and type(child) not in _SCAN_TYPES:
                _refuse("BAD_TYPE", "request")  # a subclass may misreport its size: refused unread
            if type(child) in _SCAN_TYPES and id(child) not in seen:
                if depth + 1 > MAX_DEPTH or len(seen) >= MAX_CONTAINERS:
                    _refuse("OVERSIZE", "request")
                seen.add(id(child))
                stack.append((child, depth + 1))
    for rule, _keys in _KEY_RULES:
        if rule in hits:
            _refuse(rule, sorted(hits[rule])[0])
    if non_str:
        _refuse("BAD_TYPE", "key")


def _valid_date(value):
    match = _DATE_RE.fullmatch(value)
    if not match:
        return False
    year, month, day = (int(g) for g in match.groups())
    if year < 1 or not 1 <= month <= 12 or day < 1:
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    return day <= days


def _exact_int(value):
    return type(value) is int


def _cap(value, field, limit):
    """Unit-level cap, checked before clean_text so the shared helper's own length code never surfaces."""
    if type(value) is str and len(value) > limit:
        _refuse("OVERSIZE", field)


def _clean(value, field, limit):
    return policy.clean_text(value, PREFIX, field, limit)


def _splitmix64(seed):
    state = seed

    def draw():
        nonlocal state
        state = (state + 0x9E3779B97F4A7C15) & _M64
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
        return z ^ (z >> 31)
    return draw


def run(request):
    """Simulate supplied synthetic characters; returns {agents, events, frames, coverage, scope}."""
    # 1. request is an exact dict
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    # 2-3. forbidden-key scan, then non-str keys
    _scan_keys(request)
    # 4. unknown keys, top level then each nested level in schema order
    if set(request) - TOP_KEYS:
        _refuse("UNKNOWN", "request")
    world = request.get("world")
    if type(world) is dict and set(world) - WORLD_KEYS:
        _refuse("UNKNOWN", "world")
    agents = request.get("agents")
    if type(agents) is list:
        for agent in agents:
            if type(agent) is dict and set(agent) - AGENT_KEYS:
                _refuse("UNKNOWN", "agents")
    scenario = request.get("scenario")
    if type(scenario) is dict:
        if set(scenario) - SCENARIO_KEYS:
            _refuse("UNKNOWN", "scenario")
        kind = scenario.get("kind")
        if type(kind) is str:
            if len(kind) > MAX_KIND:
                _refuse("OVERSIZE", "kind")  # raw cap before membership
            if kind not in KINDS:
                _refuse("UNKNOWN", "kind")
    # 5. top-level and world types; empty required lists
    as_of = request.get("as_of")
    if type(as_of) is not str:
        _refuse("BAD_TYPE", "as_of")
    seed = request.get("seed")
    if not _exact_int(seed) or seed < 0:
        _refuse("BAD_TYPE", "seed")
    if type(world) is not dict:
        _refuse("BAD_TYPE", "world")
    if type(agents) is not list:
        _refuse("BAD_TYPE", "agents")
    if type(scenario) is not dict:
        _refuse("BAD_TYPE", "scenario")
    world_name = world.get("name")
    places = world.get("places")
    steps = world.get("steps")
    if type(world_name) is not str:
        _refuse("BAD_TYPE", "world_name")
    if type(places) is not list:
        _refuse("BAD_TYPE", "places")
    if not _exact_int(steps) or steps < 1:
        _refuse("BAD_TYPE", "steps")
    kind = scenario.get("kind")
    if type(kind) is not str:
        _refuse("BAD_TYPE", "kind")
    product = scenario.get("product")
    if kind == "commercial_storyboard" and type(product) is not str:
        _refuse("BAD_TYPE", "product")
    if product is not None and type(product) is not str:
        _refuse("BAD_TYPE", "product")
    if not agents or not places:
        _refuse("EMPTY")
    # 6. caps (OVERSIZE), before any clean_text, in a fixed order
    _cap(as_of, "as_of", MAX_AS_OF)
    _cap(world_name, "world_name", MAX_WORLD_NAME)
    if len(places) > MAX_PLACES:
        _refuse("OVERSIZE", "places")
    for place in places:
        _cap(place, "places", MAX_PLACE_LEN)
    if steps > MAX_STEPS:
        _refuse("OVERSIZE", "steps")
    if seed > MAX_SEED:
        _refuse("OVERSIZE", "seed")
    if len(agents) > MAX_AGENTS:
        _refuse("OVERSIZE", "agents")
    for agent in agents:
        if type(agent) is not dict:
            continue
        _cap(agent.get("id"), "id", MAX_ID)
        _cap(agent.get("name"), "name", MAX_NAME)
        for field, limit, item_limit in (("traits", MAX_TRAITS, MAX_TRAIT_LEN), ("actions", MAX_ACTIONS, MAX_ACTION_LEN)):
            items = agent.get(field)
            if type(items) is list:
                if len(items) > limit:
                    _refuse("OVERSIZE", field)
                for item in items:
                    _cap(item, field, item_limit)
    _cap(product, "product", MAX_PRODUCT)
    # 7. per-field validation in list order
    if not _valid_date(as_of):
        _refuse("BAD_TYPE", "as_of")
    as_of = _clean(as_of, "as_of", MAX_AS_OF)
    world_name = _clean(world_name, "world_name", MAX_WORLD_NAME)
    clean_places, folded = [], set()
    for place in places:
        text = _clean(place, "places", MAX_PLACE_LEN)
        if text.casefold() in folded:
            _refuse("BAD_TYPE", "places")
        folded.add(text.casefold())
        clean_places.append(text)
    if product is not None:
        product = _clean(product, "product", MAX_PRODUCT)
    rows, ids = [], set()
    for agent in agents:
        if type(agent) is not dict:
            _refuse("BAD_TYPE", "agents")
        aid = _clean(agent.get("id"), "id", MAX_ID)
        name = _clean(agent.get("name"), "name", MAX_NAME)
        lists = {}
        for field, item_limit in (("traits", MAX_TRAIT_LEN), ("actions", MAX_ACTION_LEN)):
            items = agent.get(field)
            if type(items) is not list:
                _refuse("BAD_TYPE", field)
            if not items:
                _refuse("EMPTY")
            lists[field] = [_clean(item, field, item_limit) for item in items]
        if aid in ids:
            _refuse("BAD_TYPE", "agents")
        ids.add(aid)
        rows.append({"id": aid, "name": name, "traits": lists["traits"], "actions": lists["actions"]})
    # 8. compute
    draw = _splitmix64(seed)
    events, frames = [], []
    for step in range(1, steps + 1):
        for row in rows:
            place = clean_places[draw() % len(clean_places)]
            action = row["actions"][draw() % len(row["actions"])]
            events.append({"step": step, "agent_id": row["id"], "place": place, "action": action,
                           "label": LABEL, "ai_generated": True})
            frame = "Frame %d [%s] %s at %s: %s." % (step, LABEL, row["name"], place, action)
            if kind == "commercial_storyboard":
                frame += " Product: %s." % product
            frames.append(frame + " TO_WRITE: voiceover")
    out_agents = [dict(row, label=LABEL, ai_generated=True) for row in rows]
    return {
        "agents": out_agents, "events": events, "frames": frames, "world": {"name": world_name, "places": clean_places},
        "coverage": {"agents": len(rows), "steps": steps, "events": len(events), "frames": len(frames)},
        "scope": policy.scope(["seeded deterministic toy sim of supplied synthetic characters",
                               "event log", "text storyboard draft"],
                              ["behavior model", "real-person check", "media generation", "publishing"],
                              "supplied world and characters", as_of),
    }
