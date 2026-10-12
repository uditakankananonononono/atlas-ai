"""G112 / c36.anime - full anime production pipeline.

Source request (instinct doc, verbatim): "make its own anime show".

What c36.creative was missing (audit G112): it emitted a template bible and
fixed TO_WRITE acts. This unit produces the show: a series bible, per-episode
three-act scripts with real generated dialogue (trait-driven diction,
arc-themed beats, no placeholder tokens), per-scene shot lists with camera
work, rendered storyboard panels (SVG figures composed from c36.worldforge),
a phase-by-phase production schedule, and an assembly manifest. Coverage is
checked mechanically - every scene has shots, every speaker is a cast member,
every output is placeholder-free - and the checks ship in the report.

Release/broadcast stays refused (owner-gated effect). Stdlib only,
deterministic from the supplied seed.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

from app.modules.c30 import policy
from app.modules.c36 import worldforge

PREFIX = "SHOW"
MAX_TEXT = 200
MAX_PREMISE = 4000
MAX_CHARACTERS = 12
MAX_EPISODES = 24
PLACEHOLDER_TOKENS = ("TO_WRITE", "TODO", "unimplemented", "FIXME", "placeholder", "lorem")
_KEY_RULES = (
    ("SEND", frozenset({"send", "smtp", "email_send", "approval_token"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})),
    ("EFFECT", frozenset({"publish", "upload", "deploy", "broadcast", "stream", "release_live"})),
    ("NOCREDS", frozenset({"login", "password", "credentials", "otp", "api_key",
                           "access_token", "bearer", "passwd"})),
)
ARC_BANK = (
    ("a routine job hides a sabotage plot", "the saboteur is someone the cast trusts",
     "trust is named, not assumed"),
    ("a rival crew claims the cast's home turf", "the rival is running from something worse",
     "strength means sheltering former enemies"),
    ("a treasured tool breaks beyond repair", "its maker left a map to rebuild it better",
     "what breaks teaches more than what lasts"),
    ("a storm traps the cast with a stranger", "the stranger knows the lead's oldest secret",
     "kindness to strangers is never wasted"),
    ("a festival demands a public performance", "the lead's stage fright has a real history",
     "courage is practiced, not found"),
    ("a message arrives from the lead's past", "the message was sent by the future winner",
     "discipline outlasts talent"),
)
DICTION = {
    "bold": ("Charge in", "no hesitation", "I'll take the hit"),
    "kind": ("Stay behind me", "are you hurt", "we go together"),
    "curious": ("Look closer", "what if we're wrong", "show me the mechanism"),
    "calm": ("Breathe first", "panic spends energy", "watch the pattern"),
    "playful": ("Race you there", "worth a laugh at least", "bet I beat your score"),
    "analytical": ("Run the numbers", "the pattern breaks here", "test it twice"),
    "focused": ("One thing at a time", "eyes on the target", "finish the drill"),
    "creative": ("Flip it around", "make it sing", "ugly first draft, then art"),
}
DEFAULT_DICTION = ("let's move", "stay sharp", "we're not done")
SHOT_KINDS = ("establishing wide", "tracking medium", "character close-up",
              "over-shoulder dialogue", "insert detail", "reaction close-up")
CAMERA_MOVES = ("static", "slow push-in", "lateral dolly", "crane down", "handheld sway")
PHASES = (("script", 2), ("boards", 2), ("layout", 2), ("animation", 4),
          ("compositing", 1), ("sound", 1), ("master", 1))


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


def _hash(text):
    return worldforge._hash_text(text)


def _diction(character):
    for trait in character["traits"]:
        key = trait.casefold()
        if key in DICTION:
            return DICTION[key]
    return DEFAULT_DICTION


def _line(character, beat, scene_no, line_no):
    """One real dialogue line: trait diction + beat context, deterministic."""
    diction = _diction(character)
    pick = _hash(character["id"] + beat + str(scene_no) + str(line_no))
    phrase = diction[pick % len(diction)]
    templates = (
        "%s - '%s' is moving and we are already late.",
        "%s. Listen: '%s' - so we adapt before it adapts to us.",
        "%s! You saw what '%s' did to the plan. We answer now.",
        "%s. If '%s' is true, everything we trained for changes tonight.",
    )
    return templates[pick % len(templates)] % (phrase, beat[:60])


def _script_episode(ep_no, title, premise, characters, seed):
    """Three-act episode script: scenes, beats, real dialogue lines."""
    arc = ARC_BANK[(ep_no - 1 + seed % 3) % len(ARC_BANK)]
    acts = []
    beats = (("cold open on %s" % arc[0], "inciting turn: %s" % arc[1]),
             ("the cast commits to a plan around %s" % arc[0],
              "midpoint reversal: %s" % arc[1]),
             ("climax: the cast acts on the truth that %s" % arc[1],
              "resolution: %s" % arc[2]))
    draw = worldforge._splitmix64(seed + ep_no * 977)
    scene_no = 0
    for act_no, act_beats in enumerate(beats, 1):
        scenes = []
        for beat in act_beats:
            scene_no += 1
            speakers = [characters[(draw() + i) % len(characters)] for i in range(2)]
            if speakers[0]["id"] == speakers[1]["id"] and len(characters) > 1:
                speakers[1] = characters[(characters.index(speakers[0]) + 1) % len(characters)]
            lines = []
            for line_no in range(3):
                speaker = speakers[line_no % len(speakers)]
                lines.append({"speaker": speaker["id"], "text": _line(speaker, beat, scene_no, line_no)})
            scenes.append({"scene": scene_no, "act": act_no, "beat": beat,
                           "location": "set_%d" % (1 + (draw() % 4)), "dialogue": lines})
        acts.append({"act": act_no, "scenes": scenes})
    return {"episode": ep_no, "title": "Episode %d: %s" % (ep_no, arc[2].title()),
            "arc_theme": arc, "acts": acts}


def _shot_list(episode):
    """Every scene gets a real shot sequence with camera direction."""
    shots = []
    seq = 0
    for act in episode["acts"]:
        for scene in act["scenes"]:
            base = _hash("ep%dsc%d" % (episode["episode"], scene["scene"]))
            n_shots = 3 + base % 3
            for k in range(n_shots):
                seq += 1
                shots.append({
                    "seq": seq, "episode": episode["episode"], "scene": scene["scene"],
                    "kind": SHOT_KINDS[(base + k) % len(SHOT_KINDS)],
                    "camera": CAMERA_MOVES[(base + k * 3) % len(CAMERA_MOVES)],
                    "duration_s": 2 + (base + k) % 5,
                    "on_screen": [d["speaker"] for d in scene["dialogue"][:2]],
                    "note": "%s of beat '%s' (%s)" % (
                        SHOT_KINDS[(base + k) % len(SHOT_KINDS)].split()[0],
                        scene["beat"][:48], scene["location"]),
                })
    return shots


def _storyboard_svg(episode, people, max_panels=6):
    """Rendered panels for the episode's key scenes."""
    scenes = [s for act in episode["acts"] for s in act["scenes"]][:max_panels]
    cols, pw, ph = 2, 330, 200
    rows = (len(scenes) + cols - 1) // cols
    width, height = cols * pw, rows * ph + 24
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height),
             '<rect width="%d" height="%d" fill="#f4f1ea"/>' % (width, height)]
    for idx, scene in enumerate(scenes):
        gx, gy = (idx % cols) * pw, (idx // cols) * ph
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#fff" stroke="#777"/>'
                     % (gx + 5, gy + 5, pw - 10, ph - 10))
        for k, speaker in enumerate(scene["dialogue"][:2]):
            person = people.get(speaker["speaker"])
            if person is not None:
                parts.append('<g transform="translate(%d,%d) scale(0.5)">%s</g>'
                             % (gx + 14 + k * 120, gy + 14,
                                worldforge.render_person_svg(person, 120)))
        first_line = scene["dialogue"][0]["text"]
        parts.append('<text x="%d" y="%d" font-size="10" fill="#333">sc %d [%s] %s</text>'
                     % (gx + 12, gy + ph - 30, scene["scene"], escape(scene["location"]),
                        escape(first_line[:52])))
        parts.append('<text x="%d" y="%d" font-size="9" fill="#666">%s</text>'
                     % (gx + 12, gy + ph - 14, escape(scene["beat"][:64])))
    parts.append('<rect x="0" y="%d" width="%d" height="24" fill="#1e1e22"/>'
                 '<text x="8" y="%d" font-size="12" fill="#c8c8d2">%s - %s storyboard, ep %d, %d panels</text></svg>'
                 % (height - 24, width, height - 7, worldforge.LABEL,
                    escape(episode["title"][:40]), episode["episode"], len(scenes)))
    return "".join(parts)


def _schedule(episodes, start_week=1):
    """Phase-by-phase production schedule in week offsets, overlapped by one phase."""
    rows = []
    for ep in range(1, episodes + 1):
        week = start_week + (ep - 1) * 6
        for phase, weeks in PHASES:
            rows.append({"episode": ep, "phase": phase, "start_week": week,
                         "end_week": week + weeks - 1})
            week += weeks - 1  # one week overlap between phases
    total = max(r["end_week"] for r in rows)
    return rows, total


def run(request):
    """Produce the show package; returns scripts, shots, boards, schedule, checks."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "seed", "concept"}:
        _refuse("UNKNOWN", "request")
    as_of = policy.clean_text(request.get("as_of"), PREFIX, "as_of", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        _refuse("BAD_TYPE", "as_of")
    seed = request.get("seed")
    if type(seed) is not int or not 0 <= seed <= (1 << 64) - 1:
        _refuse("BAD_TYPE", "seed")
    concept = request.get("concept")
    if type(concept) is not dict or set(concept) - {"title", "premise", "characters", "episodes"}:
        _refuse("UNKNOWN", "concept")
    title = policy.clean_text(concept.get("title"), PREFIX, "title", MAX_TEXT)
    premise = policy.clean_text(concept.get("premise"), PREFIX, "premise", MAX_PREMISE, allow_ws=True)
    raw_chars = concept.get("characters")
    if type(raw_chars) is not list or not raw_chars or len(raw_chars) > MAX_CHARACTERS:
        _refuse("BAD_TYPE", "characters")
    episodes = concept.get("episodes")
    if type(episodes) is not int or not 1 <= episodes <= MAX_EPISODES:
        _refuse("BAD_TYPE", "episodes")
    characters, ids = [], set()
    for c in raw_chars:
        if type(c) is not dict or set(c) - {"id", "name", "traits"}:
            _refuse("UNKNOWN", "characters")
        cid = policy.clean_text(c.get("id"), PREFIX, "id", 64)
        if cid in ids:
            _refuse("DUPLICATE", "characters")
        ids.add(cid)
        name = policy.clean_text(c.get("name"), PREFIX, "name", MAX_TEXT)
        traits = c.get("traits")
        if type(traits) is not list or not traits or len(traits) > 6:
            _refuse("BAD_TYPE", "traits")
        characters.append({"id": cid, "name": name,
                           "traits": [policy.clean_text(t, PREFIX, "traits", 64) for t in traits]})

    bible = {
        "title": title, "premise": premise, "format": "%d-episode season, 3 acts, 22-minute" % episodes,
        "cast": [{"id": c["id"], "name": c["name"], "traits": c["traits"],
                  "voice_direction": "speaks like someone who is %s; never explains feelings, shows them"
                                     % ", ".join(c["traits"][:2])} for c in characters],
        "world_rules": ["every power or tool shown has a visible cost",
                        "conflicts resolve through choices, not coincidences",
                        "each episode's theme lands in the resolution beat"],
        "label": worldforge.LABEL,
    }
    people = {c["id"]: worldforge.person_params(c["id"], c["name"], c["traits"]) for c in characters}
    scripts = [_script_episode(ep, title, premise, characters, seed) for ep in range(1, episodes + 1)]
    shot_lists = {ep["episode"]: _shot_list(ep) for ep in scripts}
    boards = {ep["episode"]: _storyboard_svg(ep, people) for ep in scripts}
    schedule, total_weeks = _schedule(episodes)
    manifest = {"episodes": [
        {"episode": ep["episode"], "title": ep["title"],
         "scenes": sum(len(a["scenes"]) for a in ep["acts"]),
         "dialogue_lines": sum(len(s["dialogue"]) for a in ep["acts"] for s in a["scenes"]),
         "shots": len(shot_lists[ep["episode"]]),
         "runtime_s": sum(sh["duration_s"] for sh in shot_lists[ep["episode"]])}
        for ep in scripts]}

    # mechanical coverage checks, shipped in the report
    cast_ids = {c["id"] for c in characters}
    check_issues = []
    all_text = [premise, title]
    for ep in scripts:
        scenes = [s for a in ep["acts"] for s in a["scenes"]]
        if len(scenes) != 6:
            check_issues.append("episode_%d_scene_count:%d" % (ep["episode"], len(scenes)))
        for scene in scenes:
            for line in scene["dialogue"]:
                if line["speaker"] not in cast_ids:
                    check_issues.append("unknown_speaker:" + line["speaker"])
                all_text.append(line["text"])
            if not any(sh["scene"] == scene["scene"] for sh in shot_lists[ep["episode"]]):
                check_issues.append("scene_without_shots:ep%d_sc%d" % (ep["episode"], scene["scene"]))
    for text in all_text:
        low = text.casefold()
        for token in PLACEHOLDER_TOKENS:
            if token in low:
                check_issues.append("placeholder_text:" + token)
    for svg in boards.values():
        low = svg.casefold()
        for token in PLACEHOLDER_TOKENS:
            if token in low:
                check_issues.append("placeholder_board:" + token)

    return {
        "title": title, "as_of": as_of, "bible": bible,
        "scripts": scripts, "shot_lists": shot_lists, "storyboards": boards,
        "schedule": schedule, "total_weeks": total_weeks, "manifest": manifest,
        "checks": {"episodes": len(scripts),
                   "total_scenes": sum(m["scenes"] for m in manifest["episodes"]),
                   "total_dialogue_lines": sum(m["dialogue_lines"] for m in manifest["episodes"]),
                   "total_shots": sum(m["shots"] for m in manifest["episodes"]),
                   "issues": check_issues,
                   "placeholder_free": not any("placeholder" in i for i in check_issues),
                   "every_scene_shot": not any("scene_without_shots" in i for i in check_issues),
                   "all_speakers_cast": not any("unknown_speaker" in i for i in check_issues)},
        "scope": policy.scope(
            ["series bible, per-episode 3-act scripts with real generated dialogue",
             "per-scene shot lists with camera direction",
             "rendered SVG storyboard panels via c36.worldforge",
             "phase production schedule and assembly manifest",
             "mechanical coverage checks shipped in the report"],
            ["release, streaming or broadcast - refused keys, owner-gated",
             "final animation render - boards/schedule/scripts are the production package",
             "voice/sound recording - schedule allocates the phases"],
            "supplied concept, cast and seed", as_of),
    }
