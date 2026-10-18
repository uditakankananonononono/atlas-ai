"""Row 411 keyword research: deterministic seed expansion with rule-based
intent classification and code-enforced honesty guards.

The previous implementation passed caller seed keywords through mostly
unchanged; this engine does the artifact's actual job deterministically: it
expands each caller-provided seed into 15-30 typed terms via a disclosed
modifier-template table, classifies intent by disclosed rules, and carries
metrics only where the caller supplied them.

Honesty rules enforced in code, not by prompt:

1. No fabricated metrics. ``volume``/``difficulty``/``cpc`` appear only where
   the caller supplied them for that exact term (seed or derived). Derived
   terms the caller never measured always carry null metrics.
2. Intent is derivation metadata. A derived term inherits the intent of the
   modifier template that produced it; a seed's intent comes from the caller
   or, failing that, from a disclosed pattern table. It is a classification
   rule, not observed searcher behavior.
3. No external effects. Pure function over the input mapping; nothing is
   fetched, crawled, stored, or published.
"""

from __future__ import annotations

import re
from typing import Any

_MAX_TERMS = 30
_MIN_TERMS = 15

# Modifier templates grouped by the intent they signal. A derived term's
# intent is the intent of the template that produced it - derivation metadata,
# not observed search behavior.
_INTENT_TEMPLATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "informational",
        (
            "how to {seed}",
            "what is {seed}",
            "{seed} guide",
            "{seed} tutorial",
            "how does {seed} work",
        ),
    ),
    (
        "commercial",
        (
            "best {seed}",
            "{seed} reviews",
            "{seed} comparison",
            "{seed} alternatives",
            "top {seed}",
        ),
    ),
    (
        "transactional",
        (
            "buy {seed}",
            "{seed} pricing",
            "{seed} cost",
            "{seed} discount",
            "{seed} free trial",
        ),
    ),
    (
        "navigational",
        (
            "{seed} login",
            "{seed} support",
            "{seed} documentation",
            "{seed} official site",
        ),
    ),
)

# Pattern table for classifying caller-provided seeds, checked in order.
# First matching needle (substring of the lowercased term) wins.
_SEED_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "transactional",
        ("buy", "price", "pricing", "cost", "discount", "coupon", "deal",
         "order", "free trial"),
    ),
    (
        "navigational",
        ("login", "log in", "sign in", "signin", "support", "documentation",
         "docs", "official", "download"),
    ),
    (
        "commercial",
        ("best", "top", "review", "reviews", "comparison", "compare", "vs",
         "versus", "alternative", "alternatives"),
    ),
    (
        "informational",
        ("how", "what", "why", "guide", "tutorial", "learn", "tips",
         "example", "examples"),
    ),
)

_WHITESPACE = re.compile(r"\s+")

# A term qualifies as a quick win only from caller-provided evidence: the
# caller supplied both a volume and a difficulty below this engine-default
# threshold. The threshold is an engine default, not observed data.
QUICK_WIN_MAX_DIFFICULTY = 40


def _normalize(term: Any) -> str:
    if not isinstance(term, str):
        raise ValueError(f"keyword terms must be strings, got {type(term).__name__}")
    return _WHITESPACE.sub(" ", term.strip())


def _key(term: str) -> str:
    return term.lower()


def _provided_metrics_for(term: str, provided: dict[str, Any]) -> dict[str, Any]:
    """Caller-supplied metrics for an exact term match, or empty.

    Matches on the raw term and on its whitespace-normalized form so a seed
    written with extra spacing still finds its provided row. No fuzzy or
    derived-term inference: the caller must have named this term.
    """
    row = provided.get(term)
    if row is None:
        row = provided.get(_normalize(term))
    if isinstance(row, dict):
        return row
    return {}


def _classify_seed(term: str, provided: dict[str, Any]) -> tuple[str, str]:
    """Intent for a caller-provided seed: caller's value wins, else the
    disclosed pattern table, else honestly unclassified."""
    row = _provided_metrics_for(term, provided)
    if isinstance(row.get("intent"), str) and row["intent"]:
        return row["intent"], "caller-provided"
    low = term.lower()
    for intent, needles in _SEED_INTENT_RULES:
        if any(needle in low for needle in needles):
            return intent, "pattern-rule"
    return "unclassified", "no rule matched"


def research_keywords(inputs: dict[str, Any]) -> dict[str, Any]:
    """Expand caller seed keywords into 15-30 typed terms.

    Deterministic: identical input mapping produces identical output,
    including term order (seeds first in input order, then derived terms in
    seed-major template order).
    """
    facts = inputs.get("facts") or {}
    provided = inputs.get("provided_metrics") or {}

    raw_seeds = facts.get("seed_keywords")
    if not raw_seeds:
        raw_seeds = list(provided)

    seeds: list[str] = []
    seen: set[str] = set()
    for raw in raw_seeds:
        term = _normalize(raw)
        if term and _key(term) not in seen:
            seen.add(_key(term))
            seeds.append(term)

    if not seeds:
        placeholder = {
            "term": "TO BE PROVIDED",
            "intent": "unclassified",
            "intent_basis": "placeholder: no seed keywords provided",
            "origin": "placeholder",
            "volume": None,
            "difficulty": None,
            "cpc": None,
        }
        return {
            "keywords": [placeholder],
            "intent_map": {placeholder["term"]: placeholder["intent"]},
            "quick_wins": [],
            "quick_win_rule": (
                "term has caller-provided volume AND caller-provided "
                f"difficulty < {QUICK_WIN_MAX_DIFFICULTY}; the threshold is "
                "an engine default, not observed data"
            ),
            "notes": [
                "no seed keywords were provided, so there is nothing to "
                "expand; provide facts.seed_keywords",
                "no expansion was attempted on the placeholder term",
            ],
        }

    entries: list[dict[str, Any]] = []

    def _add_entry(term: str, intent: str, basis: str, origin: str) -> None:
        row = _provided_metrics_for(term, provided)
        entries.append(
            {
                "term": term,
                "intent": intent,
                "intent_basis": basis,
                "origin": origin,
                "volume": row.get("volume"),
                "difficulty": row.get("difficulty"),
                "cpc": row.get("cpc"),
            }
        )

    for seed in seeds:
        intent, basis = _classify_seed(seed, provided)
        _add_entry(seed, intent, basis, "seed")

    # Derived terms, seed-major then template-table order, until the cap.
    for seed in seeds:
        if len(entries) >= _MAX_TERMS:
            break
        for intent, templates in _INTENT_TEMPLATES:
            for template in templates:
                if len(entries) >= _MAX_TERMS:
                    break
                term = _normalize(template.format(seed=seed))
                if not term or _key(term) in seen:
                    continue
                seen.add(_key(term))
                _add_entry(term, intent, f"derived from modifier template {template!r}", "derived")

    quick_wins = [
        e["term"]
        for e in entries
        if e["volume"] is not None
        and e["difficulty"] is not None
        and isinstance(e["difficulty"], (int, float))
        and e["difficulty"] < QUICK_WIN_MAX_DIFFICULTY
    ]

    derived_count = sum(1 for e in entries if e["origin"] == "derived")
    return {
        "keywords": entries,
        "intent_map": {e["term"]: e["intent"] for e in entries},
        "quick_wins": quick_wins,
        "quick_win_rule": (
            "term has caller-provided volume AND caller-provided difficulty "
            f"< {QUICK_WIN_MAX_DIFFICULTY}; the threshold is an engine "
            "default, not observed data"
        ),
        "notes": [
            f"{len(seeds)} caller-provided seed(s) expanded to "
            f"{len(entries)} term(s) ({derived_count} derived, capped at "
            f"{_MAX_TERMS}) via a fixed modifier-template table",
            "intent is rule-based classification from the modifier template "
            "or pattern table, not observed searcher behavior",
            "volume/difficulty/cpc appear only where the caller provided "
            "them for the exact term; derived terms carry null metrics "
            "unless the caller provided that exact term",
        ],
    }
