"""P68|L57 in-silico-only biology guardrail: a lexical gate over caller-supplied domain terms.

Pure stdlib. No I/O, no network, no clock, no ML, no external lists. It never judges biosafety, never
authenticates or resolves an approval reference and never emits a safe claim. See
docs/INSTINCT_P68_L57_INSILICO_GUARD_CONTRACT.md.
"""
from __future__ import annotations

from typing import Any

CONTRACT_ID = "P68|L57"
BIO_TERMS = frozenset({"biological", "medical", "crispr", "biohacking", "phage", "mosquito", "xenobot", "vaccine", "enviropig", "organoid",
                       "microbiome", "clinical"})
MODES = ("computational", "physical")
FIELDS = ("id", "domain_terms", "execution_mode", "approval_ref")
REQUIRED = ("id", "domain_terms", "execution_mode")
MAX_ID = 64
MAX_TERMS = 32
MAX_TERM = 64
MAX_REF = 128
LIMITS = (
    "lexical gate on caller-supplied domain terms only; it is not a biosafety, ethics or legal review",
    "a flagged_physical_with_review_ref verdict only flags physical work for human review; approval_ref is recorded verbatim and never authenticated, resolved or treated as an approval",
    "never emits a safe claim: allowed_in_silico means only that no physical execution was declared for a matched item",
    "the closed term set is exactly the 12 contract terms with exact whole-term lowercase matching; synonyms, variants, uppercase and substrings are not matched, and widening it is a contract change",
)


def _fail(code: str):
    raise ValueError("P68:" + code)


def _text(value: Any, name: str, limit: int, *, blank_code: bool) -> str:
    if type(value) is not str:
        _fail(f"bad_type:{name}")
    if blank_code and not value.strip():
        _fail(f"empty_field:{name}")
    if len(value) > limit:
        _fail(f"text_too_long:{name}")
    return value


def classify(item: Any) -> dict:
    """Return the verdict record for one item. Raises ValueError('P68:<code>') on a bad item."""
    if type(item) is not dict:
        _fail("bad_type:item")
    if any(type(k) is not str or k not in FIELDS for k in item):
        _fail("unknown_fields:item")
    for name in REQUIRED:
        if name not in item:
            _fail(f"empty_field:{name}")
    ident = _text(item["id"], "id", MAX_ID, blank_code=True)
    terms = item["domain_terms"]
    if type(terms) is not list:
        _fail("bad_type:domain_terms")
    if len(terms) > MAX_TERMS:
        _fail("limit_exceeded:domain_terms")
    for t in terms:
        _text(t, "domain_terms", MAX_TERM, blank_code=False)
    mode = item["execution_mode"]
    if type(mode) is not str:
        _fail("bad_type:execution_mode")
    if mode not in MODES:
        _fail(f"bad_mode:{mode}")
    ref = item.get("approval_ref")
    if ref is not None:
        ref = _text(ref, "approval_ref", MAX_REF, blank_code=True)
    matched = sorted({t for t in terms if t in BIO_TERMS})
    if not matched:
        verdict = "not_bio_scoped"
    elif mode == "computational":
        verdict = "allowed_in_silico"
    elif ref is not None:
        verdict = "flagged_physical_with_review_ref"
    else:
        verdict = "refused_physical_without_review"
    return {"contract": CONTRACT_ID, "id": ident, "verdict": verdict, "execution_mode": mode, "matched_terms": matched, "approval_ref": ref,
            "approval_validated": False, "biosafety_review_performed": False, "safe_claim": False, "limits": list(LIMITS)}


def classify_batch(items: Any) -> list:
    """Verdicts in sorted-id order. The batch is refused on the first bad item in that order; no partial results."""
    if type(items) is not list:
        _fail("bad_type:items")

    def key(pair):
        i, it = pair
        ident = it.get("id") if type(it) is dict else None
        return (0, ident, i) if type(ident) is str else (1, "", i)

    seen = set()
    out = []
    for _, it in sorted(enumerate(items), key=key):
        record = classify(it)
        if record["id"] in seen:
            _fail(f"duplicate_id:{record['id']}")
        seen.add(record["id"])
        out.append(record)
    return out
