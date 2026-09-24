"""Evidence completeness for drafted application answers (M02 enhancement).

Every claim (sentence) in a drafted answer must either cite an owner-corpus
source marker ([1], [2] ...) whose text actually supports it, or say
[NEEDS INPUT]. The scorer links each claim to its sources and flags:

- uncited claims (no marker, no [NEEDS INPUT]);
- dangling markers ([4] when only 3 sources were retrieved);
- anchor mismatches: numbers, years and capitalised names in the claim that
  appear in none of the cited sources (the usual shape of a fabricated
  metric or award);
- low overlap: the cited sources share almost no content words with the claim.

Deterministic and offline; no model call. The score is supported claims /
claims that need evidence; [NEEDS INPUT] claims count as honest gaps, not
support.
"""
from __future__ import annotations

import re
from typing import Any

NEEDS_INPUT = "[NEEDS INPUT]"
_MARKER = re.compile(r"\[(\d{1,3})\]")
_LEAD = re.compile(r"^((?:\[\d{1,3}\][\s.,;]*)+)")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\"'(])")
_NUM = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?")
_NAME = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*")
_WORD = re.compile(r"[a-z][a-z'-]{3,}")
_STOP = frozenset("""this that with from have were been their there which about would could should
into also because while where when what your yours they them then than these those very more most
such each other only over under after before during being does doing done make made many much some
through within without across between will shall just like""".split())
_SENTENCE_START_OK = frozenset({"I", "My", "We", "Our", "The", "This", "That", "In", "At", "As", "When", "After", "Before", "During", "Through", "With", "For", "It", "A", "An", "One"})


def split_claims(text: str) -> list[str]:
    parts: list[str] = []
    for para in re.split(r"\n\s*\n|\n[-*•]\s*", text.strip()):
        para = " ".join(para.split())
        if not para:
            continue
        for piece in (s.strip() for s in _SENT.split(para) if s.strip()):
            # "... by 20%. [1] Next claim." - leading markers belong to the claim before.
            lead = _LEAD.match(piece)
            if lead and parts:
                parts[-1] = f"{parts[-1]} {lead.group(1).strip()}"
                piece = piece[lead.end():].strip()
            if piece:
                parts.append(piece)
    return parts


def _anchors(claim: str) -> set[str]:
    body = _MARKER.sub(" ", claim).replace(NEEDS_INPUT, " ")
    nums = {n.rstrip("%").replace(",", "") for n in _NUM.findall(body)}
    names = set()
    for m in _NAME.finditer(body):
        phrase = m.group(0)
        words = phrase.split()
        if m.start() == 0 or body[:m.start()].rstrip().endswith((".", "!", "?")):
            words = words[1:] if words and words[0] in _SENTENCE_START_OK else words
        phrase = " ".join(words)
        if phrase and not (len(words) == 1 and phrase in _SENTENCE_START_OK):
            names.add(phrase.lower())
    return nums | names


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def score_answer(field: str, draft: str, sources: list[dict[str, Any]], *, min_overlap: float = 0.15) -> dict[str, Any]:
    """`sources` are the corpus hits in marker order: [1] is sources[0]."""
    claims_out: list[dict[str, Any]] = []
    supported = needs_input = needing = 0
    for claim in split_claims(draft):
        markers = [int(m) for m in _MARKER.findall(claim)]
        row: dict[str, Any] = {"claim": claim, "markers": markers, "sources": [], "issues": []}
        if NEEDS_INPUT in claim:
            row["status"] = "needs_input"
            needs_input += 1
            claims_out.append(row)
            continue
        needing += 1
        if not markers:
            row["status"] = "uncited"
            row["issues"].append("no source marker and no [NEEDS INPUT]")
            claims_out.append(row)
            continue
        cited = []
        for m in markers:
            if 1 <= m <= len(sources):
                src = sources[m - 1]
                cited.append(src)
                row["sources"].append({"marker": m, "id": src.get("id"), "source_type": src.get("source_type"),
                                       "source_id": src.get("source_id"), "locator": src.get("locator")})
            else:
                row["issues"].append(f"marker [{m}] points to no retrieved source")
        text = " ".join(str(s.get("text", "")) for s in cited).lower()
        flat = text.replace(",", "")
        missing = sorted(a for a in _anchors(claim) if a not in flat)
        if missing:
            row["issues"].append("not found in cited sources: " + ", ".join(missing))
        words = _content_words(_MARKER.sub(" ", claim))
        overlap = len(words & _content_words(text)) / len(words) if words else 1.0
        row["overlap"] = round(overlap, 3)
        if cited and overlap < min_overlap:
            row["issues"].append(f"cited sources share little wording with the claim ({overlap:.0%})")
        row["status"] = "supported" if cited and not row["issues"] else "unsupported"
        supported += row["status"] == "supported"
        claims_out.append(row)
    score = round(supported / needing, 4) if needing else (1.0 if claims_out else 0.0)
    return {
        "field": field, "score": score, "claims": claims_out,
        "counts": {"claims": len(claims_out), "supported": supported, "needs_input": needs_input,
                   "unsupported": needing - supported},
        "complete": needing == supported and needs_input == 0 and bool(claims_out),
    }


def score_package(fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """fields: {name: {"draft": str, "sources": [...]}} -> per-field scores + overall."""
    per = {name: score_answer(name, f["draft"], f["sources"]) for name, f in fields.items()}
    need = sum(r["counts"]["supported"] + r["counts"]["unsupported"] for r in per.values())
    sup = sum(r["counts"]["supported"] for r in per.values())
    return {"fields": per, "overall_score": round(sup / need, 4) if need else 0.0,
            "complete": bool(per) and all(r["complete"] for r in per.values()),
            "open_needs_input": sum(r["counts"]["needs_input"] for r in per.values())}
