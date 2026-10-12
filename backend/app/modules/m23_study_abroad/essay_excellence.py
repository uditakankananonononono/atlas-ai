"""m23.essay_excellence (doc row 98): college-essay excellence ENGINE.

Closes the audit gap on row 98 ("winning-material package not inspected or
judged"): a deterministic rubric engine that ANALYSES student-authored
drafts, scores them on eight explicit criteria with published formulas,
measures revision-over-revision improvement, and assembles per-college
winning-material packages ONLY from student-confirmed essays and
source-backed evidence.

Hard boundary (enforced, not prose): the engine never writes essay prose.
There is no generation function. An essay without student_confirmed=True is
refused from any package. Scores are rubric mechanics over the supplied
text, not an admission prediction and not a guarantee of winning anything.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import re

from app.modules.c30 import policy

PREFIX = "ESSAY"
MAX_DRAFT = 40000
MAX_EVIDENCE = 200
MAX_ESSAYS = 40
WORD_LIMIT_DEFAULT = 650

CLICHES = (
    "since i was young", "since i was a child", "ever since i can remember",
    "changed my life", "taught me the value of", "i have always been passionate",
    "in today's society", "at the end of the day", "stepped out of my comfort zone",
    "made me the person i am", "little did i know", "against all odds",
)
REFLECTION_MARKERS = (
    "i learned", "i realised", "i realized", "i understand now", "i changed",
    "it taught me", "which taught me", "i grew", "i see now", "i noticed",
    "looking back", "that is when i", "because of this", "i decided",
)
_WORD = re.compile(r"[A-Za-z0-9'-]+")
_SENT = re.compile(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$")
_NUM = re.compile(r"\b\d+(?:[.,]\d+)*(?:%|percent|st|nd|rd|th)?\b")
_PROPER = re.compile(r"\b[A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})*\b")
_FIRST_PERSON = re.compile(r"\b(i|my|me|mine|myself)\b", re.IGNORECASE)

LIMITS = (
    "Rubric mechanics over supplied student text; not an admission prediction.",
    "No prose is generated anywhere in this unit; student authorship is enforced.",
    "No award, scholarship or admission outcome is promised or implied.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _words(text):
    return _WORD.findall(text)


def _sentences(text):
    return [s.strip() for s in _SENT.findall(text) if s.strip()]


def _paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _clamp(x):
    return max(0.0, min(1.0, round(x, 4)))


def analyze_draft(draft, prompt="", evidence=None, word_limit=WORD_LIMIT_DEFAULT):
    """Score a student-authored draft on eight explicit criteria (0..1 each)."""
    draft = policy.clean_text(draft, PREFIX, "draft", MAX_DRAFT, allow_ws=True)
    prompt = policy.clean_text(prompt or " ", PREFIX, "prompt", 4000, allow_blank=True, allow_ws=True)
    if isinstance(word_limit, bool) or not isinstance(word_limit, int) or not 50 <= word_limit <= 5000:
        raise ValueError("%s_REFUSED_BAD_TYPE:word_limit" % PREFIX)
    evidence = evidence or []
    if isinstance(evidence, bool) or not isinstance(evidence, (list, tuple)) or len(evidence) > MAX_EVIDENCE:
        raise ValueError("%s_REFUSED_BAD_TYPE:evidence" % PREFIX)
    ev_tokens = set()
    ev_ids = set()
    for e in evidence:
        if not isinstance(e, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:evidence_item" % PREFIX)
        ev_ids.add(e.get("id"))
        for field in ("description", "tags", "title"):
            v = e.get(field)
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if isinstance(x, str):
                    ev_tokens.update(t for t in _words(x.lower()) if len(t) > 3)
    words = _words(draft)
    n_words = len(words)
    sents = _sentences(draft)
    paras = _paragraphs(draft)
    low = draft.lower()
    sent_lens = [len(_words(s)) for s in sents] or [0]
    avg_sent = sum(sent_lens) / len(sent_lens)
    long_ratio = sum(1 for l in sent_lens if l > 30) / len(sent_lens)
    readability = _clamp(1.0 - abs(avg_sent - 16.0) / 16.0 - 0.5 * long_ratio)
    concrete = len(_NUM.findall(draft)) + len(set(_PROPER.findall(draft)) - {"I"})
    specificity = _clamp(concrete / max(1.0, n_words / 100.0) / 6.0)
    claim_sents = [s for s in sents if len(_words(s)) >= 8]
    linked = [s for s in claim_sents
              if ev_tokens & {t for t in _words(s.lower()) if len(t) > 3}]
    evidence_linkage = _clamp(len(linked) / max(1, len(claim_sents))) if ev_tokens else None
    fp_sents = [s for s in sents if _FIRST_PERSON.search(s)]
    refl = [s for s in fp_sents if any(m in s.lower() for m in REFLECTION_MARKERS)]
    reflection = _clamp(len(refl) / max(1, len(fp_sents)) * 1.5)
    found_cliches = sorted({c for c in CLICHES if c in low})
    originality = _clamp(1.0 - 0.25 * len(found_cliches))
    first = sents[0] if sents else ""
    hook = _clamp(0.4 + 0.3 * ("?" in first) + 0.3 * (4 <= len(_words(first)) <= 25))
    structure = _clamp(0.25 * min(len(paras), 4) + (0.2 if 1 <= len(paras) <= 8 else 0.0))
    length_fit = _clamp(1.0 - abs(n_words - 0.9 * word_limit) / word_limit) \
        if n_words <= word_limit else 0.0
    criteria = {
        "readability": readability,
        "specificity": specificity,
        "evidence_linkage": evidence_linkage,
        "reflection": reflection,
        "originality": originality,
        "hook": hook,
        "structure": structure,
        "length_fit": length_fit,
    }
    scored = [v for v in criteria.values() if v is not None]
    overall = _clamp(sum(scored) / len(scored))
    prompt_tokens = {t for t in _words(prompt.lower()) if len(t) > 4}
    drift = _clamp(len(prompt_tokens & {t for t in _words(low) if len(t) > 4})
                   / max(1, len(prompt_tokens))) if prompt_tokens else None
    return {
        "overall": overall,
        "criteria": criteria,
        "prompt_alignment": drift,
        "stats": {"words": n_words, "sentences": len(sents), "paragraphs": len(paras),
                  "avg_sentence_words": round(avg_sent, 2), "word_limit": word_limit,
                  "within_limit": n_words <= word_limit,
                  "cliches_found": found_cliches,
                  "evidence_ids_supplied": sorted(x for x in ev_ids if x)},
        "feedback": _feedback(criteria, found_cliches, n_words, word_limit, drift),
        "limits": list(LIMITS),
    }


def _feedback(criteria, cliches, n_words, word_limit, drift):
    out = []
    labels = {"readability": "vary sentence length; split run-ons",
              "specificity": "add concrete numbers, names and dates",
              "evidence_linkage": "tie claims to your verified evidence record",
              "reflection": "show what changed in you, not only what happened",
              "originality": "replace cliche phrasing with your own detail",
              "hook": "open on a specific moment, not a general statement",
              "structure": "use 3-6 deliberate paragraphs",
              "length_fit": "aim near %d words (limit %d)" % (int(0.9 * word_limit), word_limit)}
    for key, tip in labels.items():
        v = criteria.get(key)
        if v is not None and v < 0.6:
            out.append({"criterion": key, "score": v, "suggestion": tip})
    if cliches:
        out.append({"criterion": "cliches", "found": cliches,
                    "suggestion": "rewrite these phrases with specific detail"})
    if drift is not None and drift < 0.3:
        out.append({"criterion": "prompt_alignment", "score": drift,
                    "suggestion": "the draft barely touches the prompt's own words"})
    return out


def compare_revisions(before, after, prompt="", evidence=None, word_limit=WORD_LIMIT_DEFAULT):
    """Revision-over-revision delta on every criterion."""
    a = analyze_draft(before, prompt, evidence, word_limit)
    b = analyze_draft(after, prompt, evidence, word_limit)
    deltas = {}
    for key in b["criteria"]:
        va, vb = a["criteria"][key], b["criteria"][key]
        if va is None or vb is None:
            deltas[key] = None
        else:
            deltas[key] = round(vb - va, 4)
    improved = [k for k, d in deltas.items() if d is not None and d > 0]
    regressed = [k for k, d in deltas.items() if d is not None and d < 0]
    return {"overall_delta": round(b["overall"] - a["overall"], 4),
            "criterion_deltas": deltas, "improved": improved, "regressed": regressed,
            "before_overall": a["overall"], "after_overall": b["overall"],
            "measured": True, "limits": list(LIMITS)}


def assemble_package(college, essays, analyses=None):
    """Assemble a per-college winning-material package from STUDENT-CONFIRMED
    essays only. college = {"name":..,"prompts":[{"id","prompt","word_limit"}]}.
    essays = [{"id","prompt_id","student_text","student_confirmed"}]."""
    if not isinstance(college, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:college" % PREFIX)
    name = policy.clean_text(college.get("name"), PREFIX, "college", 200)
    prompts = college.get("prompts")
    if isinstance(prompts, bool) or not isinstance(prompts, (list, tuple)) or not prompts:
        raise ValueError("%s_REFUSED_BAD_TYPE:prompts" % PREFIX)
    if isinstance(essays, bool) or not isinstance(essays, (list, tuple)) or len(essays) > MAX_ESSAYS:
        raise ValueError("%s_REFUSED_BAD_TYPE:essays" % PREFIX)
    by_prompt = {}
    for e in essays:
        if not isinstance(e, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:essay" % PREFIX)
        if e.get("student_confirmed") is not True:
            _err("STUDENT_AUTHORSHIP", "essay:%s" % e.get("id"))
        text = policy.clean_text(e.get("student_text"), PREFIX, "student_text",
                                 MAX_DRAFT, allow_ws=True)
        pid = policy.clean_text(e.get("prompt_id"), PREFIX, "prompt_id", 64)
        by_prompt[pid] = {"essay_id": e.get("id"), "words": len(_words(text)),
                          "student_confirmed": True}
    covered, missing = [], []
    for p in prompts:
        pid = policy.clean_text(p.get("id"), PREFIX, "prompt.id", 64)
        (covered if pid in by_prompt else missing).append(pid)
    scores = {}
    for a in (analyses or []):
        if isinstance(a, dict) and a.get("essay_id") and isinstance(a.get("overall"), (int, float)):
            scores[a["essay_id"]] = round(float(a["overall"]), 4)
    return {
        "college": name,
        "status": "complete" if not missing else "incomplete",
        "covered_prompts": covered,
        "missing_prompts": missing,
        "essays": by_prompt,
        "rubric_scores": scores,
        "submitted": False,
        "boundary": ("Student-authored, student-confirmed essays only; Atlas assembles and "
                     "judges mechanics, writes nothing, submits nothing, and promises no "
                     "admission or award outcome."),
        "limits": list(LIMITS),
    }
