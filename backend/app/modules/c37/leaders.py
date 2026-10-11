"""S6.2 / c37.leaders - leaders-and-concepts integrator.

Turns SUPPLIED source passages into structured entity records (person,
company, product, concept) with evidence spans, plus fixed-template idea
prompts per confirmed entity. Entities are found only by a supplied
known_entities list (case-sensitive exact) or an ASCII capitalized-phrase
regex; regex hits are flagged candidate_unconfirmed. No knowledge graph,
no entity resolution beyond exact name match, no judgement of who is a
'leader', no live fetch. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "INTEL"
ENTITY_TYPES = ("person", "company", "product", "concept")
MAX_SNIPPET = 160
MAX_FOCUS = 200
MAX_NAME = 256
MAX_TEXT = 100000
MAX_ID = 256

_CANDIDATE = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}\b")

T1_ID = "T1"
T1_TEMPLATE = "What would {name}'s approach look like applied to {focus}?"
T2_ID = "T2"
T2_TEMPLATE = "How does {name} compare with {other}?"


def _fail(reason: str):
    raise ValueError(f"{PREFIX}_REFUSED_{reason}")


def _valid_url(u) -> bool:
    if not isinstance(u, str) or not u.startswith("https://"):
        return False
    if any(c.isspace() or ord(c) <= 32 or 127 <= ord(c) <= 159
           or 0x200B <= ord(c) <= 0x200F or 0x202A <= ord(c) <= 0x202E
           or 0x2066 <= ord(c) <= 0x2069 or ord(c) == 0xFEFF for c in u):
        return False
    return bool(urlsplit(u).hostname)


def _build_record(name, type_, status, mentions, as_of, homonym_types=None):
    """One entity record. A record with zero mentions is UNSOURCED and can
    never be emitted (internal invariant)."""
    if not mentions:
        _fail("UNSOURCED")
    rec = {"name": name, "type": type_, "status": status,
           "mentions": sorted(mentions, key=lambda x: (x["passage_id"], x["offset"])),
           "first_seen": as_of}
    if homonym_types:
        rec["homonym_types"] = list(homonym_types)
    return rec


def _snippet(text, off, length):
    return text[max(0, off - 60):off + length + 60][:MAX_SNIPPET]


def _collect_matches(passages, known):
    """All (passage_id, start, length, name, type, status) matches. Known
    entities match case-sensitively at every occurrence; candidates come
    from the capitalized-phrase regex. Overlap: at one start, longest wins;
    a known entity beats a candidate on the same span; a candidate equal to
    a known name is not duplicated."""
    known_names = {k["name"] for k in known}
    raw = []
    for p in passages:
        text = p["text"]
        for k in known:
            pos = text.find(k["name"])
            while pos != -1:
                raw.append((p["id"], pos, len(k["name"]), k["name"], k["type"], "confirmed"))
                pos = text.find(k["name"], pos + 1)
        for hit in _CANDIDATE.finditer(text):
            if hit.group(0) in known_names:
                continue
            raw.append((p["id"], hit.start(), len(hit.group(0)), hit.group(0), "concept",
                        "candidate_unconfirmed"))
    raw.sort(key=lambda r: (r[0], r[1], -r[2], 0 if r[5] == "confirmed" else 1))
    chosen = []
    for row in raw:
        pid, start, length = row[0], row[1], row[2]
        overlap = False
        for c in chosen:
            if c[0] == pid and c[3] != row[3] and start < c[1] + c[2] and c[1] < start + length:
                overlap = True
                break
        if not overlap:
            chosen.append(row)
    return chosen


def run(request: dict) -> dict:
    """Integrate supplied passages into entity records and idea prompts."""
    if isinstance(request, bool) or not isinstance(request, dict):
        _fail("BAD_TYPE:request")
    as_of = policy.clean_text(request.get("as_of"), PREFIX, "as_of", 64)
    known = request.get("known_entities")
    known = [] if known is None else known
    if isinstance(known, bool) or not isinstance(known, list):
        _fail("BAD_TYPE:known_entities")
    for k in known:
        if not isinstance(k, dict) or not isinstance(k.get("name"), str) \
                or not k["name"].strip() or k.get("type") not in ENTITY_TYPES:
            _fail("BAD_TYPE:known_entities")
        policy.clean_text(k["name"], PREFIX, "name", MAX_NAME)
    if len({(k["name"], k["type"]) for k in known}) != len(known):
        _fail("BAD_TYPE:known_entities")
    focus = request.get("focus")
    if focus is not None:
        focus = policy.clean_text(focus, PREFIX, "focus", MAX_FOCUS)

    passages = request.get("passages")
    if isinstance(passages, bool) or not isinstance(passages, list):
        _fail("BAD_TYPE:passages")
    if not passages:
        _fail("EMPTY")
    used = []
    dropped = {"no_https_url": 0, "empty_text": 0}
    for row in passages:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) \
                or not row["id"].strip():
            _fail("BAD_TYPE:passages")
        policy.clean_text(row["id"], PREFIX, "id", MAX_ID)
        if not _valid_url(row.get("url")):
            dropped["no_https_url"] += 1
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            dropped["empty_text"] += 1
            continue
        policy.clean_text(text, PREFIX, "text", MAX_TEXT, allow_ws=True)
        used.append({"id": policy.clean_text(row["id"], PREFIX, "id", MAX_ID), "text": text})
    if len({row["id"] for row in passages}) != len(passages):
        _fail("BAD_TYPE:passages")
    if not used:
        _fail("NOSOURCE")

    matches = _collect_matches(used, known)
    grouped = {}
    seen_mentions = {}
    for pid, start, length, name, type_, status in matches:
        key = (name, type_, status)
        if (pid, start) in seen_mentions.setdefault(key, set()):
            continue
        seen_mentions[key].add((pid, start))
        grouped.setdefault(key, []).append(
            {"passage_id": pid, "offset": start,
             "snippet": _snippet(next(p["text"] for p in used if p["id"] == pid), start, length)})

    types_by_name = {}
    for (name, type_, _s) in grouped:
        types_by_name.setdefault(name, set()).add(type_)
    entities = []
    for (name, type_, status), mentions in sorted(grouped.items()):
        hom = sorted(types_by_name[name]) if len(types_by_name[name]) > 1 else None
        entities.append(_build_record(name, type_, status, mentions, as_of, hom))
    entities.sort(key=lambda e: (e["name"], e["type"]))

    confirmed = [e for e in entities if e["status"] == "confirmed"]
    prompts = []
    for i, e in enumerate(confirmed):
        if focus is not None:
            prompts.append({"entity": e["name"], "template_id": T1_ID,
                            "text": T1_TEMPLATE.format(name=e["name"], focus=focus),
                            "label": "template_prompt"})
        if len(confirmed) >= 2:
            other = confirmed[(i + 1) % len(confirmed)]["name"]
            prompts.append({"entity": e["name"], "template_id": T2_ID,
                            "text": T2_TEMPLATE.format(name=e["name"], other=other),
                            "label": "template_prompt"})

    known_not_found = sorted(k["name"] for k in known if k["name"] not in
                             {name for (name, _t, s) in grouped if s == "confirmed"})
    coverage = {"passages_supplied": len(passages), "passages_used": len(used),
                "dropped_by_reason": dropped, "entities_found": len(entities),
                "known_not_found": known_not_found}
    return {"entities": entities, "prompts": prompts, "coverage": coverage,
            "scope": policy.scope(
                ["structured entity records from supplied passages with evidence spans",
                 "fixed-template idea prompts for confirmed entities"],
                ["knowledge graph", "entity resolution beyond exact name match",
                 "judging who is a leader", "live fetch", "verified entity facts"],
                "supplied-passages", as_of)}
