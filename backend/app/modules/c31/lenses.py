"""S1.5 / c31.lenses - cognitive-style lenses.

Source excerpt (verbatim): "mimic humans disease and thinking process...
savant syndrome, autism intelligence, depression creativity".

Named cognitive-style lenses as divergent-THINKING strategies applied to a
supplied idea. A disclaimer is mandatory in every output. No clinical claims:
diagnosing or imitating a condition as a medical claim is refused.
Substitute for X13. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
LENSES = {
    "hyperfocus": "single out the one detail everything else orbits and go deeper than reasonable on it",
    "pattern-first": "state the repeating pattern before any instance of it",
    "systemizing": "rewrite the idea as inputs, rules and outputs of an explicit system",
    "melancholic-depth": "ask what is lost, missing or mourned in the idea and let that drive a variation",
    "lateral-jump": "force an analogy from a distant field and import one mechanism back",
    "constraint-flip": "invert the strongest constraint and see what the idea becomes",
}
DISCLAIMER = ("Style lenses are divergent-thinking strategies named after cognitive styles. "
              "They are not diagnoses, not imitations of any condition, and carry no clinical "
              "or medical meaning.")
MAX_IDEA = 20000


def apply(idea, lenses=None, diagnose=False):
    """Run a supplied idea through the named lenses; returns one angle each."""
    if diagnose:
        raise ValueError("FLEET_REFUSED_CLINICAL")  # no diagnosis, no medical claims
    text = policy.clean_text(idea, PREFIX, "idea", MAX_IDEA)
    if lenses is None:
        chosen = sorted(LENSES)
    else:
        if not isinstance(lenses, (list, tuple)) or not lenses:
            raise ValueError("FLEET_REFUSED_BAD_TYPE:lenses")
        chosen = []
        for l in lenses:
            if l not in LENSES:
                raise ValueError("FLEET_REFUSED_BAD_LENS:" + str(l)[:64])
            if l in chosen:
                raise ValueError("FLEET_REFUSED_DUPLICATE:" + l)
            chosen.append(l)
    angles = [{"lens": l, "angle": "[%s] %s: %s" % (l, LENSES[l], text)} for l in chosen]
    return {"idea": text, "angles": angles, "lens_count": len(angles),
            "disclaimer": DISCLAIMER,
            "scope": policy.scope(
                ["divergent-thinking lenses", "mandatory disclaimer"],
                ["diagnosis", "clinical or medical claims", "mimicking a condition"],
                "supplied idea text")}


def report(idea, lenses=None):
    return apply(idea, lenses)
