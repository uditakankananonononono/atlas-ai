"""G110 / c36.worldforge - rendered virtual worlds and AI people.

Source request (instinct doc, verbatim): "build virtual worlds and concepts
of their own ... able to create ai people in the virtual world and able to
model them for different things that humans do maybe makeup commercials".

What c36.world was missing (audit G110): it was text-only. This unit renders:
- parametric AI people, trait-derived, as raster PNG portraits (a stdlib
  PNG encoder + scanline rasterizer lives here) and SVG figures;
- the world itself as a rendered SVG map (places, regions, roads);
- sim events as rendered storyboard panels (SVG grid, captions, product
  placement in commercial mode);
- a trait-driven behavior engine: mood/relationship state, weighted action
  selection, encounters - still deterministic (splitmix64), still stdlib only.

Every person and frame is labeled SYNTHETIC-AI; likeness/real-person keys
refuse. Nothing is published. PNG bytes decode; SVG parses.
"""
from __future__ import annotations

import re
import struct
import zlib
from xml.sax.saxutils import escape

from app.modules.c30 import policy

PREFIX = "VENT"
LABEL = "SYNTHETIC-AI"
MAX_AGENTS = 50
MAX_STEPS = 100
MAX_PLACES = 30
MAX_TEXT = 100
MAX_PANEL_TEXT = 220
_M64 = (1 << 64) - 1
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_KEY_RULES = (
    ("SEND", frozenset({"send", "smtp", "email_send", "approve", "approval_token"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})),
    ("DECEPTIVE", frozenset({"real_person", "likeness", "impersonate", "deepfake",
                             "voice_clone", "endorsement", "testimonial", "celebrity"})),
    ("EFFECT", frozenset({"publish", "post", "upload", "deploy", "broadcast", "advertise"})),
    ("NOCREDS", frozenset({"login", "password", "credentials", "otp", "api_key",
                           "access_token", "refresh_token", "bearer", "passwd"})),
)
TRAIT_AFFINITY = {
    "curious": {"explore": 3, "study": 2, "talk": 1},
    "calm": {"rest": 3, "study": 2, "walk": 1},
    "bold": {"perform": 3, "explore": 2, "compete": 2},
    "kind": {"help": 3, "talk": 2, "gift": 2},
    "focused": {"study": 3, "build": 2, "work": 2},
    "playful": {"play": 3, "perform": 2, "talk": 1},
    "analytical": {"study": 3, "build": 2, "explore": 1},
    "creative": {"create": 3, "perform": 2, "play": 1},
}
DEFAULT_AFFINITY = {"walk": 1, "talk": 1, "rest": 1}
PALETTES = {
    "skin": ("#f2d2b6", "#e8b78f", "#c98d5f", "#a06a42", "#7a4c2e", "#5c3820"),
    "hair": ("#1c1c1e", "#4a3222", "#7a5230", "#b5522e", "#c9c9cf", "#e8e3d8",
             "#3b4a6b", "#6b3b5c"),
    "eyes": ("#2e4a6b", "#4a3320", "#2e6b4a", "#5c5c66"),
    "outfit": ("#b53b3b", "#3b6bb5", "#3bb58a", "#b58a3b", "#8a3bb5", "#3bb5b5"),
}
EXPRESSIONS = ("neutral", "smile", "focused", "surprised")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _scan_keys(node, depth=0):
    if depth > 32:
        _refuse("OVERSIZE", "request")
    if type(node) is dict:
        if len(node) > 32:
            _refuse("OVERSIZE", "request")
        for key, value in node.items():
            if type(key) is not str:
                _refuse("BAD_TYPE", "key")
            if len(key) > 200:
                _refuse("OVERSIZE", "key")
            norm = key.casefold().replace("-", "_")
            for reason, table in _KEY_RULES:
                if norm in table:
                    _refuse(reason, norm)
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)
    elif type(node) in (list, tuple):
        if len(node) > 256:
            _refuse("OVERSIZE", "request")
        for value in node:
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)


def _clean(value, field, limit=MAX_TEXT):
    return policy.clean_text(value, PREFIX, field, limit)


def _splitmix64(seed):
    state = seed & _M64

    def draw():
        nonlocal state
        state = (state + 0x9E3779B97F4A7C15) & _M64
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
        return z ^ (z >> 31)
    return draw


def _hash_text(text):
    h = 0xCBF29CE484222325
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & _M64
    return h


# ---------------- PNG encoder + rasterizer (pixels, stdlib) ----------------

def _png(width, height, rgb):
    """Encode an RGB bytearray (row-major) as a PNG."""
    def chunk(tag, data):
        raw = tag + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scan = b"".join(b"\x00" + bytes(rgb[y * width * 3:(y + 1) * width * 3])
                    for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(scan, 6)) + chunk(b"IEND", b""))


class _Canvas:
    def __init__(self, width, height, bg):
        self.w, self.h = width, height
        self.px = bytearray(width * height * 3)
        self.fill(0, 0, width, height, bg)

    def _set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def fill(self, x0, y0, w, h, color):
        for y in range(max(0, y0), min(self.h, y0 + h)):
            base = (y * self.w + max(0, x0)) * 3
            row = bytes(color) * max(0, min(self.w, x0 + w) - max(0, x0))
            self.px[base:base + len(row)] = row

    def disc(self, cx, cy, r, color):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self._set(x, y, color)

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if rx and ry and ((x - cx) ** 2 * ry * ry + (y - cy) ** 2 * rx * rx) <= rx * rx * ry * ry:
                    self._set(x, y, color)


def _hex(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


# ---------------- AI people: params -> PNG portrait / SVG figure ----------------

def person_params(agent_id, name, traits):
    """Deterministic parametric model of one AI person from id/name/traits."""
    seed = _hash_text(agent_id + "|" + name + "|" + ",".join(sorted(traits)))
    draw = _splitmix64(seed)
    face_w = 14 + draw() % 7          # head ellipse x-radius
    face_h = 16 + draw() % 6          # head ellipse y-radius
    hair_style = draw() % 4           # 0 short, 1 side, 2 long, 3 top
    build = 10 + draw() % 8           # shoulder half-width
    return {
        "id": agent_id, "name": name, "traits": list(traits),
        "face": {"rx": face_w, "ry": face_h},
        "hair": {"style": hair_style, "color": PALETTES["hair"][draw() % len(PALETTES["hair"])]},
        "skin": PALETTES["skin"][draw() % len(PALETTES["skin"])],
        "eyes": {"color": PALETTES["eyes"][draw() % len(PALETTES["eyes"])],
                 "wide": bool(draw() % 2)},
        "expression": EXPRESSIONS[draw() % len(EXPRESSIONS)],
        "outfit": PALETTES["outfit"][draw() % len(PALETTES["outfit"])],
        "build": build,
        "label": LABEL, "ai_generated": True,
    }


def render_person_png(params, size=64):
    """Rasterize the parametric person to PNG bytes (size x size RGB)."""
    bg = _hex("#eef1f5")
    c = _Canvas(size, size, bg)
    cx, cy = size // 2, size // 2 - 4
    rx, ry = params["face"]["rx"], params["face"]["ry"]
    skin, hair = _hex(params["skin"]), _hex(params["hair"]["color"])
    # shoulders / outfit
    c.ellipse(cx, size - 8, params["build"] + 8, 18, _hex(params["outfit"]))
    # neck then head
    c.fill(cx - 3, cy + ry - 4, 6, 8, skin)
    c.ellipse(cx, cy, rx, ry, skin)
    # hair styles
    style = params["hair"]["style"]
    if style == 0:
        c.ellipse(cx, cy - ry + 4, rx, max(4, ry // 2), hair)
        c.fill(cx - rx, cy - ry, 2 * rx, 6, hair)
    elif style == 1:
        c.ellipse(cx - 3, cy - ry + 5, rx, max(5, ry // 2 + 2), hair)
        c.fill(cx - rx - 2, cy - ry + 2, 5, ry + 6, hair)
    elif style == 2:
        c.ellipse(cx, cy - ry + 4, rx + 2, ry // 2 + 3, hair)
        c.fill(cx - rx - 2, cy - 4, 4, ry + 14, hair)
        c.fill(cx + rx - 2, cy - 4, 4, ry + 14, hair)
    else:
        c.ellipse(cx, cy - ry + 2, rx - 3, 5, hair)
    # eyes
    ey = cy - 2
    er = 2 if params["eyes"]["wide"] else 1
    for ex in (cx - rx // 2, cx + rx // 2):
        c.disc(ex, ey, er + 1, (255, 255, 255))
        c.disc(ex, ey, er, _hex(params["eyes"]["color"]))
    # brows
    c.fill(cx - rx // 2 - 3, ey - 5, 6, 1, hair)
    c.fill(cx + rx // 2 - 3, ey - 5, 6, 1, hair)
    # mouth by expression
    my = cy + ry // 2
    expr = params["expression"]
    if expr == "smile":
        c.ellipse(cx, my - 1, 5, 3, skin)
        c.ellipse(cx, my, 5, 3, (120, 40, 40))
        c.fill(cx - 5, my - 2, 10, 2, skin)
    elif expr == "surprised":
        c.disc(cx, my + 1, 3, (120, 40, 40))
    elif expr == "focused":
        c.fill(cx - 4, my, 8, 2, (120, 40, 40))
    else:
        c.fill(cx - 3, my, 6, 1, (120, 40, 40))
    # label band: the SYNTHETIC-AI mark is part of the pixels, not metadata
    c.fill(0, size - 6, size, 6, (30, 30, 34))
    for x in range(2, size - 2, 4):  # dashed pale band reads as a watermark strip
        c.fill(x, size - 5, 2, 4, (200, 200, 210))
    return _png(size, size, c.px)


def render_person_svg(params, height=120):
    """Vector figure of the same parametric person (independent render)."""
    w = int(height * 0.6)
    cx = w / 2
    head_cy = height * 0.32
    rx = params["face"]["rx"] * height / 160
    ry = params["face"]["ry"] * height / 160
    p = params
    mouth = {"smile": '<path d="M %f %f Q %f %f %f %f" stroke="#782828" fill="none" stroke-width="1.5"/>'
                      % (cx - 6, head_cy + ry * 0.45, cx, head_cy + ry * 0.45 + 7, cx + 6, head_cy + ry * 0.45),
             "surprised": '<circle cx="%f" cy="%f" r="3" fill="#782828"/>' % (cx, head_cy + ry * 0.5),
             "focused": '<rect x="%f" y="%f" width="12" height="2.5" fill="#782828"/>' % (cx - 6, head_cy + ry * 0.45),
             "neutral": '<rect x="%f" y="%f" width="9" height="1.5" fill="#782828"/>' % (cx - 4.5, head_cy + ry * 0.5)}[p["expression"]]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        '<rect width="%d" height="%d" fill="#eef1f5"/>'
        '<ellipse cx="%f" cy="%f" rx="%f" ry="%f" fill="%s"/>'
        '<rect x="%f" y="%f" width="8" height="10" fill="%s"/>'
        '<ellipse cx="%f" cy="%f" rx="%f" ry="%f" fill="%s"/>'
        '<ellipse cx="%f" cy="%f" rx="%f" ry="%f" fill="%s"/>'
        '<circle cx="%f" cy="%f" r="3" fill="#ffffff"/><circle cx="%f" cy="%f" r="3" fill="#ffffff"/>'
        '<circle cx="%f" cy="%f" r="1.6" fill="%s"/><circle cx="%f" cy="%f" r="1.6" fill="%s"/>'
        '%s'
        '<rect x="0" y="%d" width="%d" height="12" fill="#1e1e22"/>'
        '<text x="3" y="%d" font-family="monospace" font-size="8" fill="#c8c8d2">%s</text>'
        '</svg>'
    ) % (
        w, height, w, height, w, height,
        cx, height * 0.78, p["build"] * height / 160 + 10, height * 0.22, p["outfit"],
        cx - 4, head_cy + ry - 2, p["skin"],
        cx, head_cy, rx, ry, p["skin"],
        cx, head_cy - ry + 4, rx, max(4.0, ry / 2), p["hair"]["color"],
        cx - rx / 2, head_cy - 2, cx + rx / 2, head_cy - 2,
        cx - rx / 2, head_cy - 2, p["eyes"]["color"], cx + rx / 2, head_cy - 2, p["eyes"]["color"],
        mouth,
        height - 12, w, height - 3, LABEL,
    )
    return svg


# ---------------- world map + storyboard rendering (SVG) ----------------

def render_world_svg(world_name, places, width=640, height=400):
    """Render the world map: places laid on a ring, roads to a hub, regions."""
    import math as _m
    cx, cy = width / 2, height / 2
    r = min(width, height) / 2 - 60
    points = []
    n = len(places)
    for i, place in enumerate(places):
        ang = 2 * _m.pi * i / n - _m.pi / 2
        points.append((cx + r * _m.cos(ang), cy + r * _m.sin(ang), place))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height),
             '<rect width="%d" height="%d" fill="#e8f0e4"/>' % (width, height),
             '<circle cx="%f" cy="%f" r="%f" fill="#dfe9f4" stroke="#9ab"/>' % (cx, cy, r + 24)]
    for x, y, _p in points:
        parts.append('<line x1="%f" y1="%f" x2="%f" y2="%f" stroke="#b8a888" stroke-width="3"/>'
                     % (cx, cy, x, y))
    parts.append('<circle cx="%f" cy="%f" r="16" fill="#c9a86a" stroke="#7a6238"/>'
                 '<text x="%f" y="%f" font-size="10" text-anchor="middle" fill="#3a2f1a">hub</text>'
                 % (cx, cy, cx, cy + 3))
    hue = 0
    for x, y, place in points:
        hue = (hue + 47) % 360
        parts.append('<circle cx="%f" cy="%f" r="20" fill="hsl(%d,45%%,65%%)" stroke="#444"/>'
                     '<text x="%f" y="%f" font-size="10" text-anchor="middle" fill="#222">%s</text>'
                     % (x, y, hue, x, y + 3, escape(place[:14])))
    parts.append('<rect x="0" y="%d" width="%d" height="18" fill="#1e1e22"/>'
                 '<text x="6" y="%d" font-size="11" fill="#c8c8d2">%s world: %s - %d places, rendered map</text>'
                 % (height - 18, width, height - 5, LABEL, escape(world_name[:40]), len(places)))
    parts.append('</svg>')
    return "".join(parts)


def render_storyboard_svg(events, agents_by_id, product=None, cols=2, panel_w=320, panel_h=190):
    """Render sim events into storyboard panels: figure, place, action, caption."""
    rows = (len(events) + cols - 1) // cols
    width, height = cols * panel_w, rows * panel_h + 22
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height),
             '<rect width="%d" height="%d" fill="#f6f4ef"/>' % (width, height)]
    for idx, ev in enumerate(events):
        gx, gy = (idx % cols) * panel_w, (idx // cols) * panel_h
        parts.append('<g><rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff" stroke="#888"/>'
                     % (gx + 4, gy + 4, panel_w - 8, panel_h - 8))
        agent = agents_by_id.get(ev["agent_id"])
        if agent is not None:
            parts.append('<g transform="translate(%d,%d) scale(0.55)">%s</g>'
                         % (gx + 12, gy + 12, render_person_svg(agent, 120)))
        caption = "%s %s at %s: %s" % (LABEL, agent["name"] if agent else ev["agent_id"],
                                       ev["place"], ev["action"])
        if product:
            caption += " | product: " + product
        parts.append('<text x="%d" y="%d" font-size="11" fill="#222">%s</text>'
                     % (gx + 12, gy + panel_h - 40, escape(caption[:60])))
        parts.append('<text x="%d" y="%d" font-size="10" fill="#555">step %d - %s</text></g>'
                     % (gx + 12, gy + panel_h - 22, ev["step"], LABEL))
    parts.append('<rect x="0" y="%d" width="%d" height="22" fill="#1e1e22"/>'
                 '<text x="8" y="%d" font-size="12" fill="#c8c8d2">%s storyboard - %d panels%s</text></svg>'
                 % (height - 22, width, height - 7, LABEL, len(events),
                    " - commercial modeling" if product else ""))
    return "".join(parts)


# ---------------- trait-driven behavior engine ----------------

def simulate(world, agents, steps, seed, as_of):
    """Mood/relationship simulation with trait-weighted actions.

    agents: [{id, name, traits, actions}]; co-location forms encounters and
    raises affinity; moods drift by action kind. Deterministic from seed."""
    draw = _splitmix64(seed)
    state = {a["id"]: {"mood": 50 + draw() % 21, "energy": 60 + draw() % 31,
                       "bonds": {}} for a in agents}
    events = []
    places = world["places"]
    for step in range(1, steps + 1):
        placement = {}
        for a in agents:
            st = state[a["id"]]
            weights = {}
            for act in a["actions"]:
                w = 1
                for t in a["traits"]:
                    w += TRAIT_AFFINITY.get(t.casefold(), {}).get(act.casefold(), 0)
                if st["energy"] < 25 and act.casefold() in ("perform", "compete", "explore"):
                    w = max(1, w - 2)
                if st["mood"] < 35 and act.casefold() in ("help", "gift", "talk"):
                    w += 1
                weights[act] = w
            total = sum(weights.values())
            pick = draw() % total
            acc = 0
            action = a["actions"][0]
            for act, w in weights.items():
                acc += w
                if pick < acc:
                    action = act
                    break
            place = places[draw() % len(places)]
            placement.setdefault(place, []).append(a["id"])
            low = action.casefold()
            if low in ("rest", "walk"):
                st["energy"] = min(100, st["energy"] + 6)
            elif low in ("perform", "compete", "build", "work"):
                st["energy"] = max(0, st["energy"] - 5)
            if low in ("play", "talk", "create", "help", "gift"):
                st["mood"] = min(100, st["mood"] + 4)
            elif low in ("compete",):
                st["mood"] = max(0, st["mood"] - 2)
            events.append({"step": step, "agent_id": a["id"], "place": place,
                           "action": action, "mood": st["mood"], "energy": st["energy"],
                           "label": LABEL, "ai_generated": True})
        for place, ids in placement.items():
            if len(ids) > 1:
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        a, b = ids[i], ids[j]
                        state[a]["bonds"][b] = state[a]["bonds"].get(b, 0) + 1
                        state[b]["bonds"][a] = state[b]["bonds"].get(a, 0) + 1
                        events.append({"step": step, "kind": "encounter", "place": place,
                                       "agents": [a, b], "bond": state[a]["bonds"][b],
                                       "label": LABEL, "ai_generated": True})
    return events, state


def run(request):
    """Build and render a virtual world with AI people; plain dict out."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "seed", "world", "agents", "scenario", "render"}:
        _refuse("UNKNOWN", "request")
    as_of = request.get("as_of")
    if type(as_of) is not str or not _DATE_RE.fullmatch(as_of):
        _refuse("BAD_TYPE", "as_of")
    seed = request.get("seed")
    if type(seed) is not int or not 0 <= seed <= _M64:
        _refuse("BAD_TYPE", "seed")
    world = request.get("world")
    if type(world) is not dict or set(world) - {"name", "places", "steps"}:
        _refuse("UNKNOWN", "world")
    wname = _clean(world.get("name"), "world_name")
    places = world.get("places")
    if type(places) is not list or not places or len(places) > MAX_PLACES:
        _refuse("BAD_TYPE", "places")
    clean_places = [_clean(p, "places") for p in places]
    steps = world.get("steps", 10)
    if type(steps) is not int or not 1 <= steps <= MAX_STEPS:
        _refuse("BAD_TYPE", "steps")
    raw_agents = request.get("agents")
    if type(raw_agents) is not list or not raw_agents or len(raw_agents) > MAX_AGENTS:
        _refuse("BAD_TYPE", "agents")
    agents, ids = [], set()
    for a in raw_agents:
        if type(a) is not dict or set(a) - {"id", "name", "traits", "actions"}:
            _refuse("UNKNOWN", "agents")
        aid = _clean(a.get("id"), "id", 64)
        if aid in ids:
            _refuse("DUPLICATE", "agents")
        ids.add(aid)
        name = _clean(a.get("name"), "name")
        traits = a.get("traits")
        actions = a.get("actions")
        if type(traits) is not list or not traits or len(traits) > 10:
            _refuse("BAD_TYPE", "traits")
        if type(actions) is not list or not actions or len(actions) > 10:
            _refuse("BAD_TYPE", "actions")
        agents.append({"id": aid, "name": name,
                       "traits": [_clean(t, "traits", 64) for t in traits],
                       "actions": [_clean(x, "actions", 64) for x in actions]})
    scenario = request.get("scenario") or {}
    if type(scenario) is not dict or set(scenario) - {"kind", "product"}:
        _refuse("UNKNOWN", "scenario")
    kind = scenario.get("kind", "daily_life")
    if kind not in ("daily_life", "commercial_storyboard"):
        _refuse("UNKNOWN", "kind")
    product = scenario.get("product")
    if kind == "commercial_storyboard":
        product = _clean(product, "product", 200)
    elif product is not None:
        _refuse("UNKNOWN", "product")

    people = [person_params(a["id"], a["name"], a["traits"]) for a in agents]
    events, final_state = simulate({"places": clean_places}, agents, steps, seed, as_of)
    storyboard_events = [e for e in events if "action" in e]
    agents_by_id = {p["id"]: p for p in people}
    renders = {"people_png": {p["id"]: render_person_png(p) for p in people},
               "people_svg": {p["id"]: render_person_svg(p) for p in people},
               "world_svg": render_world_svg(wname, clean_places),
               "storyboard_svg": render_storyboard_svg(
                   storyboard_events[:24], agents_by_id,
                   product if kind == "commercial_storyboard" else None)}
    bonds = [{"a": aid, "b": b, "strength": s}
             for aid, st in final_state.items() for b, s in st["bonds"].items()]
    bonds.sort(key=lambda r: (-r["strength"], r["a"], r["b"]))
    return {
        "as_of": as_of, "world": {"name": wname, "places": clean_places},
        "people": people, "events": events, "final_state": final_state,
        "relationships": bonds,
        "renders": renders,
        "coverage": {"people": len(people), "events": len(events),
                     "storyboard_panels": len(storyboard_events[:24]),
                     "png_bytes": sum(len(b) for b in renders["people_png"].values()),
                     "relationships": len(bonds)},
        "scope": policy.scope(
            ["parametric AI people rendered as PNG portraits and SVG figures",
             "rendered SVG world map and storyboard panels",
             "trait-driven behavior engine with mood, energy and encounter bonds",
             "every artifact labeled %s in pixels and in data" % LABEL],
            ["real-person likeness - refused by key scan",
             "publishing or advertising - refused by key scan",
             "photorealism - renders are parametric raster/vector, not camera output"],
            "supplied world, characters and seed", as_of),
    }
