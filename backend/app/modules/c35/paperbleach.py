"""A2 / c35.paperbleach - paperbleach identification + connector.

Source excerpt (verbatim): "completed applications entirely and uses
paperbleach".

What "paperbleach" is has NOT been verified. This unit starts with an
identification step over SUPPLIED candidate records (her docs/links); it
never guesses. Only an exact-name match with supplied evidence counts as
identified. A connector stub is generated only for an identified free tool;
anything else refuses and reports the one question to ask her.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "APPLY"
TARGET = "paperbleach"
MAX_CANDIDATES = 256
IDENTIFY_QUESTION = ("What is paperbleach? Please send its link or the doc "
                     "where you saw it, so the connector can be built for the "
                     "right tool.")


def identify(candidates):
    """Classify supplied candidates; returns the identification ledger."""
    if isinstance(candidates, bool) or not isinstance(candidates, (list, tuple)):
        raise ValueError("APPLY_REFUSED_NOSOURCE")
    if not candidates:
        raise ValueError("APPLY_REFUSED_NOSOURCE")
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError("APPLY_REFUSED_OVERSIZE")
    rows = []
    hits = []
    seen = set()
    for c in candidates:
        if not isinstance(c, dict):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:candidate")
        name = policy.clean_text(c.get("name"), PREFIX, "name", 128)
        key = name.strip().lower()  # normalized identity: case/space collisions
        if key in seen:             # are duplicates, never two silent hits
            raise ValueError("APPLY_REFUSED_DUPLICATE:" + key)
        seen.add(key)
        evidence = policy.clean_text(c.get("evidence"), PREFIX, "evidence", 2000)
        free_tier = c.get("free_tier")
        if free_tier is not None and not isinstance(free_tier, bool):
            raise ValueError("APPLY_REFUSED_BAD_TYPE:free_tier")
        # evidence is already guaranteed non-blank by clean_text above
        identified = name.strip().lower() == TARGET
        rows.append({"name": name, "identified": identified, "free_tier": free_tier,
                     "evidence": evidence})
        if identified:
            hits.append(rows[-1])
    status = "identified" if hits else "unidentified"
    return {"status": status, "candidates": rows, "matched": hits,
            "question": None if hits else IDENTIFY_QUESTION,
            "scope": policy.scope(
                ["identification ledger over supplied candidates",
                 "exact-name match with evidence only"],
                ["guessing what paperbleach is", "live lookup", "spend"],
                "supplied candidate records (her docs/links)")}


def connector_stub(identified_row):
    """Generate an offline connector stub for an identified FREE tool."""
    # Provenance is rechecked, never trusted from the caller: the row must
    # carry the EXACT normalized target name and a boolean identified=True,
    # as identify() would have produced it.
    if not isinstance(identified_row, dict) \
            or identified_row.get("identified") is not True \
            or not isinstance(identified_row.get("name"), str) \
            or identified_row["name"].strip().lower() != TARGET:
        raise ValueError("APPLY_REFUSED_UNIDENTIFIED")  # never guess
    if identified_row.get("free_tier") is not True:
        policy.check("spend", PREFIX)  # paid or unknown tier refuses spend
    # Evidence provenance is rechecked at stub entry: the row must still carry
    # the nonblank supplied evidence identify() validated. Presence proves a
    # supplied source, not the truth of its contents.
    evidence = identified_row.get("evidence")
    if evidence is not None and not isinstance(evidence, str):
        raise ValueError("APPLY_REFUSED_BAD_TYPE:evidence")
    if not evidence or not evidence.strip():
        raise ValueError("APPLY_REFUSED_NO_EVIDENCE")
    name = identified_row["name"]
    return {"tool": name,
            "stub": ("# connector stub for %r (offline; not installed)\n"
                     "def submit(packet):\n"
                     "    raise NotImplementedError(%r)"
                     % (name, "%s connector not installed" % name)),
            "scope": policy.scope(
                ["generated connector stub"],
                ["installing or calling the tool", "auto-submission"],
                "identified supplied record")}


def report(candidates):
    return identify(candidates)
