"""Adaptive, model-backed student interviewer with quote-verified extraction.

Truth labels (never merged):
- question_source "adaptive_local_model": a local model wrote the next question from the
  student's own last answer and it passed the shape checks below.
- question_source "fixed_script_fallback": the model was unavailable or its output failed
  the checks, so the fixed script question was used. This is a fallback, not the feature.
- extraction items are kept only when their quote is a verbatim substring of the student's
  answer. Items that fail are returned in `rejected`, never stored as BrandID evidence.

The model never writes essay prose here: questions only, short labels plus student quotes.
Routing is private=True, so no hosted route is ever used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from instinct_models import ProductConfig, Router, Task, load_config

ADAPTIVE = "adaptive_local_model"
FALLBACK = "fixed_script_fallback"
KINDS = ("value", "strength", "pattern")
_DRAFT_MARKERS = ("dear ", "in conclusion", "here is your", "here's your", "essay:", "sincerely", "personal statement:")

QUESTION_SYSTEM = (
    "You are a warm college-and-career story coach interviewing a student. Ask exactly ONE short "
    "follow-up question that builds on a specific detail the student just said. Do not write any "
    "essay text, advice, praise paragraphs or lists. Output only the question, ending with a question mark."
)
EXTRACT_SYSTEM = (
    "Read the student's latest answer. List up to 3 things it shows about the student. One per line, "
    "in the format: KIND | short label | \"words copied exactly from the answer\". "
    "KIND is value, strength or pattern. Output nothing else."
)
# Worked example (a different, invented student) so small models copy the format, not the placeholder.
EXTRACT_EXAMPLE_USER = ("Student's latest answer:\nI coached the junior swim team every Saturday for two years "
                        "because I wanted kids who were scared of water to feel safe.")
EXTRACT_EXAMPLE_REPLY = ('strength | patient coaching | "coached the junior swim team every Saturday"\n'
                         'value | making others feel safe | "kids who were scared of water to feel safe"')


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'`.,;:!?()\[\]]", " ", text.lower())).strip()


@dataclass
class InterviewStep:
    question: str | None
    question_source: str
    extraction: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    extraction_mode: str = "none_no_model"
    provider: str | None = None
    model: str | None = None
    detail: str = ""

    @property
    def model_backed(self) -> bool:
        return self.question_source == ADAPTIVE or self.extraction_mode == ADAPTIVE

    def as_dict(self) -> dict:
        return {"question": self.question, "question_source": self.question_source, "extraction": self.extraction,
                "rejected": self.rejected, "extraction_mode": self.extraction_mode, "provider": self.provider,
                "model": self.model, "detail": self.detail, "model_backed": self.model_backed}


def check_question(text: str, previous: list[str]) -> str | None:
    """Return the cleaned single question, or None if the model output is not an acceptable question."""
    line = next((x.strip() for x in (text or "").strip().splitlines() if x.strip()), "")
    line = re.sub(r"^(question\s*:|\d+[.)]\s*|[-*]\s*)", "", line, flags=re.I).strip().strip('"')
    if not line or not line.endswith("?") or line.count("?") != 1 or len(line) > 260 or len(line.split()) < 4:
        return None
    if any(m in line.lower() for m in _DRAFT_MARKERS) or _norm(line) in {_norm(p) for p in previous}:
        return None
    return line


def parse_extraction(text: str, answer: str) -> tuple[list[dict], list[dict]]:
    """Keep only items whose quote is a verbatim substring of the student's answer."""
    kept, rejected, seen = [], [], set()
    haystack = _norm(answer)
    for raw in (text or "").splitlines():
        parts = [p.strip() for p in raw.strip().lstrip("-*0123456789.) ").split("|")]
        if len(parts) != 3:
            if raw.strip():
                rejected.append({"line": raw.strip()[:200], "reason": "not KIND | label | quote"})
            continue
        kind, label, quote = parts[0].lower(), parts[1].strip(" \"'"), parts[2].strip(" \"'")
        if kind not in KINDS or not label or len(label.split()) > 6:
            rejected.append({"line": raw.strip()[:200], "reason": "bad kind or label"})
        elif len(_norm(quote).split()) < 2 or _norm(quote) not in haystack:
            rejected.append({"line": raw.strip()[:200], "reason": "quote is not verbatim in the student's answer"})
        elif (kind, label.lower()) in seen:
            rejected.append({"line": raw.strip()[:200], "reason": "duplicate"})
        else:
            seen.add((kind, label.lower()))
            kept.append({"kind": kind, "label": label, "quote": quote})
    return kept[:3], rejected


class AdaptiveInterviewer:
    def __init__(self, router: Router, *, question_tokens: int = 60, extract_tokens: int = 160):
        self.router, self.question_tokens, self.extract_tokens = router, question_tokens, extract_tokens

    def _ask(self, system: str, user: str, max_tokens: int, example: tuple[str, str] | None = None):
        shots = ([{"role": "user", "content": example[0]}, {"role": "assistant", "content": example[1]}]
                 if example else [])
        return self.router.run(Task(messages=[{"role": "system", "content": system}, *shots,
                                              {"role": "user", "content": user}],
                                    private=True, max_tokens=max_tokens))

    def step(self, *, track: str, turns: list[dict], fixed_next: str | None, want_question: bool) -> InterviewStep:
        """turns: [{question, student_response}] so far, newest last. fixed_next: script question to fall back to."""
        transcript = "\n".join(f"Coach: {t['question']}\nStudent: {t['student_response']}" for t in turns)
        latest = turns[-1]["student_response"]
        step = InterviewStep(question=fixed_next, question_source=FALLBACK)
        asked = [t["question"] for t in turns]
        details: list[str] = []
        if want_question:
            routed = self._ask(QUESTION_SYSTEM, f"Track: {track}.\n{transcript}\nCoach:", self.question_tokens)
            if routed.ok:
                q = check_question(routed.result.text, asked)
                if q:
                    step.question, step.question_source = q, ADAPTIVE
                    step.provider, step.model = routed.result.provider, routed.result.model
                else:
                    details.append("model question failed shape checks; fixed script question used")
            else:
                details.append("no local model reachable; fixed script question used: "
                               + "; ".join(f"{a.provider}:{a.outcome}" for a in routed.attempts))
        routed = self._ask(EXTRACT_SYSTEM, f"Student's latest answer:\n{latest}", self.extract_tokens,
                           example=(EXTRACT_EXAMPLE_USER, EXTRACT_EXAMPLE_REPLY))
        if routed.ok:
            step.extraction, step.rejected = parse_extraction(routed.result.text, latest)
            step.extraction_mode = ADAPTIVE
            step.provider, step.model = step.provider or routed.result.provider, step.model or routed.result.model
        else:
            details.append("no local model reachable; no quote extraction")
        step.detail = " | ".join(details)
        return step


def _loopback(url: str | None) -> bool:
    return bool(url) and (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def interviewer_from_env(env: dict | None = None) -> AdaptiveInterviewer | None:
    """Enabled only when a local OpenAI-compatible model server is configured on loopback."""
    import os
    e = dict(os.environ if env is None else env)
    e.setdefault("INSTINCT_PRODUCT", "atlas")
    cfg: ProductConfig = load_config(e)
    urls = [u for u in (cfg.ornith_url, cfg.inkling_local_url) if u]
    if not urls or not all(_loopback(u) for u in urls):
        return None
    return AdaptiveInterviewer(Router.from_config(cfg))
