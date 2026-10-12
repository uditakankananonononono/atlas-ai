"""G114 / c31.lenslab - measured cognitive-style lens transformations.

Source request (instinct doc, verbatim): "mimic humans disease and thinking
process ... how creatively a person with savant syndrome, autism
intelligence, depression creativity etc".

What c31.lenses was missing (audit G114): it returned the strategy NAME
wrapped around the idea - no transformation, no measurement. This unit makes
each lens a text operator with a distinct, inspectable transformation,
and adds a divergent-thinking battery that MEASURES the effect: baseline vs
lens-applied generation scored on fluency, flexibility, originality and
elaboration with documented formulas over a built-in word-frequency baseline.

No clinical claims anywhere: diagnosis input refuses, the disclaimer is
mandatory in every output. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import re

from app.modules.c30 import policy

PREFIX = "FLEET"
MAX_IDEA = 20000
DISCLAIMER = ("Style lenses are divergent-thinking strategies named after cognitive styles. "
              "They are not diagnoses, not imitations of any condition, and carry no clinical "
              "or medical meaning. Scores compare generated texts, not people.")
STOPWORDS = frozenset(
    "the a an and or but if then else for to of in on with by from at as is are was were be been "
    "it its this that these those we you they he she i me my your their our not no do does did "
    "have has had will would can could should may might must shall".split())
CONSTRAINT_WORDS = ("must", "cannot", "can't", "only", "never", "always", "at most", "limit")
VERBS_HINT = ("build", "make", "create", "connect", "track", "learn", "share", "grow",
              "measure", "predict", "design", "teach", "play", "trade", "help", "scan")
# coarse frequency baseline: common = 1.0 (frequent), absent words = 0.35 (rarer)
COMMON_WORDS = frozenset(
    "app platform user users data system tool tools people time work world good new way "
    "idea make build social media money game learn learning content online market business".split())
DOMAINS = {
    "mycology": ("networks share nutrients across a whole forest", "hyphal branching explores space"),
    "jazz": ("improvisation over a fixed progression", "call and response between players"),
    "ant_colony": ("stigmergic trails coordinate without a leader", "simple local rules, global order"),
    "origami": ("one sheet, many forms, no cuts", "creases store instructions"),
    "ecology": ("niches partition scarce resources", "succession rebuilds after disturbance"),
    "cryptography": ("one-way functions protect without hiding goals", "proof without disclosure"),
}
CATEGORIES = {
    "product": frozenset({"app", "tool", "platform", "feature", "product", "service"}),
    "story": frozenset({"story", "narrative", "character", "episode", "plot"}),
    "process": frozenset({"process", "pipeline", "routine", "habit", "workflow", "loop"}),
    "community": frozenset({"community", "group", "club", "network", "team", "people"}),
    "art": frozenset({"art", "design", "music", "visual", "aesthetic", "style"}),
}


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _tokens(text):
    return [t for t in re.findall(r"[a-z][a-z'-]*", text.casefold()) if t not in STOPWORDS]


def _hash(text):
    h = 0xCBF29CE484222325
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & ((1 << 64) - 1)
    return h


# ---------------- lens operators ----------------

def _op_systemizing(idea, toks):
    verbs = [t for t in dict.fromkeys(toks) if t in VERBS_HINT][:4]
    nouns = [t for t in dict.fromkeys(toks) if t not in VERBS_HINT][:6]
    rules = ["when input '%s' arrives, apply '%s'" % (n, verbs[i % len(verbs)] if verbs else "process")
             for i, n in enumerate(nouns[:3])]
    return {"inputs": nouns, "rules": rules,
            "outputs": ["%sed %s state" % (verbs[i % len(verbs)] if verbs else "process", n)
                        for i, n in enumerate(nouns[:3])]}


def _op_constraint_flip(idea, toks):
    low = idea.casefold()
    found = [w for w in CONSTRAINT_WORDS if w in low]
    flips = []
    for w in found[:4]:
        sentences = [s.strip() for s in re.split(r"[.!?]", idea) if w in s.casefold()]
        for s in sentences[:1]:
            if re.search(r"\bmust (never|not)\b", s, re.I):
                inverted = re.sub(r"\bmust (never|not)\b", "may now", s, count=1, flags=re.I)
            else:
                inverted = re.sub(r"\b" + re.escape(w) + r"\b",
                                  {"must": "may choose not to", "cannot": "can now",
                                   "can't": "can now", "only": "no longer only",
                                   "never": "is now free to", "always": "no longer must",
                                   "at most": "beyond the old cap of", "limit": "remove the limit on"}[w],
                                  s, count=1, flags=re.I)
            row = {"constraint": s[:160], "inverted": inverted[:200]}
            if row not in flips:
                flips.append(row)
    if not flips:
        strongest = toks[0] if toks else "the core assumption"
        flips.append({"constraint": "implicit: '%s' is fixed" % strongest,
                      "inverted": "treat '%s' as the free variable and rebuild around it" % strongest})
    return {"flips": flips}


def _op_lateral_jump(idea, toks):
    domain = sorted(DOMAINS)[_hash(idea) % len(DOMAINS)]
    mech = DOMAINS[domain]
    return {"domain": domain, "imported": list(mech),
            "mapping": ["apply '%s' to: %s" % (m, (toks[0] if toks else "the idea")[:60])
                        for m in mech]}


def _op_pattern_first(idea, toks):
    counts = {}
    for t in toks:
        counts[t] = counts.get(t, 0) + 1
    repeated = sorted(((c, t) for t, c in counts.items() if c > 1), reverse=True)[:3]
    if repeated:
        pattern = "the recurring signal is '%s' (%dx)" % (repeated[0][1], repeated[0][0])
    else:
        pattern = "no token repeats; the pattern is breadth over depth across %d concepts" % len(counts)
    return {"pattern": pattern, "repeated": [{"token": t, "count": c} for c, t in repeated]}


def _op_hyperfocus(idea, toks):
    if not toks:
        return {"focus": None, "detail": "empty idea"}
    rare = min(dict.fromkeys(toks), key=lambda t: (t in COMMON_WORDS, -len(t), t))
    return {"focus": rare,
            "detail": ["define '%s' precisely in this context" % rare,
                       "list three properties only '%s' has here" % rare,
                       "push '%s' one level deeper than the idea needs" % rare]}


def _op_melancholic_depth(idea, toks):
    low = idea.casefold()
    loss_words = [w for w in ("lost", "miss", "gone", "forgot", "leave", "left", "alone",
                              "end", "goodbye", "empty") if w in low]
    if loss_words:
        driver = "the idea already carries absence: %s" % ", ".join(loss_words[:3])
    else:
        driver = "nothing in the idea accounts for what its users lose by adopting it"
    return {"absence": loss_words, "driver": driver,
            "variation": "design the version that mourns what it replaces: %s"
                         % ((toks[-1] if toks else "the old way")[:60])}


OPERATORS = {"systemizing": _op_systemizing, "constraint-flip": _op_constraint_flip,
             "lateral-jump": _op_lateral_jump, "pattern-first": _op_pattern_first,
             "hyperfocus": _op_hyperfocus, "melancholic-depth": _op_melancholic_depth}


def transform(idea, lens):
    """Apply one lens operator; returns the transformed artifact."""
    if type(lens) is not str or lens not in OPERATORS:
        _refuse("BAD_LENS", str(lens)[:64] if isinstance(lens, str) else "lens")
    text = policy.clean_text(idea, PREFIX, "idea", MAX_IDEA)
    toks = _tokens(text)
    return {"lens": lens, "result": OPERATORS[lens](text, toks), "disclaimer": DISCLAIMER}


# ---------------- measured divergent-thinking battery ----------------

def _generate(idea, lens, n=12):
    """Generate n candidate variations, baseline or lens-shaped."""
    toks = _tokens(idea) or ["idea"]
    base = toks[:6]
    out = []
    for i in range(n):
        if lens is None:
            text = "%s %s with %s focus" % (base[i % len(base)], base[(i + 1) % len(base)],
                                            base[(i + 2) % len(base)])
        else:
            art = transform(idea, lens)["result"]
            key = sorted(art)[i % len(art)]
            payload = art[key]
            fragment = payload[0] if isinstance(payload, list) and payload else str(payload)
            if isinstance(fragment, dict):
                fragment = fragment.get("inverted") or fragment.get("token") or str(fragment)
            text = "%s via %s: %s" % (base[i % len(base)], lens, str(fragment)[:80])
        out.append(text)
    return out


def _category(text):
    cats = {name for name, words in CATEGORIES.items() if any(w in text.split() for w in words)}
    return cats or {"uncategorized"}


def _score(texts):
    """Fluency/flexibility/originality/elaboration with documented formulas."""
    fluency = len(texts)
    flex_buckets = set()
    for t in texts:
        flex_buckets.update(_category(t))
    flexibility = len(flex_buckets)
    words = [w for t in texts for w in _tokens(t)]
    if words:
        originality = round(sum(1.0 if w not in COMMON_WORDS else 0.35 for w in words) / len(words), 6)
    else:
        originality = 0.0
    elaboration = round(sum(len(_tokens(t)) for t in texts) / len(texts), 6) if texts else 0.0
    return {"fluency": fluency, "flexibility": flexibility,
            "originality": originality, "elaboration": elaboration}


def battery(idea, lenses=None, n=12, diagnose=False):
    """Baseline vs lens-applied generation, with measured per-lens deltas."""
    if diagnose:
        _refuse("CLINICAL")
    text = policy.clean_text(idea, PREFIX, "idea", MAX_IDEA)
    chosen = sorted(OPERATORS) if lenses is None else list(lenses)
    for l in chosen:
        if l not in OPERATORS:
            _refuse("BAD_LENS", l)
    baseline_texts = _generate(text, None, n)
    baseline = _score(baseline_texts)
    rows = []
    for l in chosen:
        scored = _score(_generate(text, l, n))
        rows.append({"lens": l, "scores": scored,
                     "delta": {k: round(scored[k] - baseline[k], 6) for k in scored}})
    best = max(rows, key=lambda r: (r["delta"]["originality"] + r["delta"]["flexibility"] / 10.0,
                                    r["lens"])) if rows else None
    return {"idea_words": len(_tokens(text)), "baseline": baseline, "lenses": rows,
            "best_lens": best["lens"] if best else None,
            "formulas": {"fluency": "count of generated candidate texts",
                         "flexibility": "distinct category buckets hit across candidates",
                         "originality": "mean word rarity vs built-in common-word baseline (rare=1.0, common=0.35)",
                         "elaboration": "mean content-word count per candidate"},
            "disclaimer": DISCLAIMER,
            "scope": policy.scope(
                ["per-lens text operators with inspectable transformations",
                 "measured baseline-vs-lens deltas over a documented battery"],
                ["clinical meaning - refused and disclaimed",
                 "human cognitive measurement - scores compare generated texts only"],
                "supplied idea text")}
