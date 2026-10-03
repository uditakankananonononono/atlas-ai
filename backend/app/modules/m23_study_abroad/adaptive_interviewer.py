"""Adaptive, model-backed student interviewer with quote-verified extraction.

Truth labels (never merged):
- question_source "adaptive_local_model": a local model wrote the next question from the
  student's own last answer and it passed the shape checks below.
- question_source "fixed_script_fallback": the model was unavailable or its output failed
  the checks, so the fixed script question was used. This is a fallback, not the feature.
- extraction items are PROPOSED and UNVERIFIED: the quote must be an exact copy from the student's answer and the
  label's words must appear in it, but meaning is never checked and the student must confirm before BrandID uses it.

The model never writes essay prose here: questions only, short labels plus student quotes.
Routing is private=True, so no hosted route is ever used.
"""
from __future__ import annotations

import dataclasses
import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from instinct_models import ProductConfig, ProviderError, ProviderUnavailable, Router, Task, load_config

CALL_TIMEOUT_S = 8.0   # per model call; one answer makes at most 2 calls
_SLOTS = threading.BoundedSemaphore(2)  # at most 2 concurrent model calls; extra requests fall back instead of queueing

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


_STOP = set("that this with from have what when where which would could about your their there them they then than been were will just into over some more very also because while after before again being does did how why who whom whose".split())
# Words a coach may use without the student having said them.
_COACH = set("tell more about felt feel think thought moment specific example describe happen happened first next like change changed mean meant make made choose chose learn learned important matter matters story part part look looking help helped decide decided experience experiences".split())
_LEADING = ("inspire you", "inspired you", "lead you to", "led you to", "motivate you", "motivated you", "make you want",
            "made you want", "pursue a career", "pursue your career", "career in", "passion for", "how did that shape")
_NOT_WORD = re.compile(r"[^a-z0-9']+")


def _words(text: str) -> list[str]:
    return [w.strip("'") for w in _NOT_WORD.split((text or "").lower()) if len(w.strip("'")) > 3]


def _content(text: str) -> set[str]:
    return {w[:5] for w in _words(text) if w not in _STOP}


def _ws(text: str) -> str:
    return " ".join((text or "").split())


def check_question(text: str, previous: list[str], conversation: str | None = None) -> str | None:
    """Return the cleaned single question, or None if it fails these LEXICAL checks.

    With `conversation` (every student answer + prior question so far) it also rejects questions that introduce
    content words the student never said, and questions that use leading templates ("inspire you to ...").
    This is lexical hygiene, not proof that a question is semantically grounded or good.
    """
    line = next((x.strip() for x in (text or "").strip().splitlines() if x.strip()), "")
    line = re.sub(r"^(question\s*:|\d+[.)]\s*|[-*]\s*)", "", line, flags=re.I).strip().strip('"')
    if not line or not line.endswith("?") or line.count("?") != 1 or len(line) > 260 or len(line.split()) < 4:
        return None
    if any(m in line.lower() for m in _DRAFT_MARKERS) or _norm(line) in {_norm(p) for p in previous}:
        return None
    if conversation is not None:
        low = line.lower()
        if any(m in low for m in _LEADING):
            return None
        known = _content(conversation)
        novel = {w for w in _words(line) if w not in _STOP and w not in _COACH and w[:5] not in known}
        if novel:
            return None
    return line


def parse_extraction(text: str, answer: str) -> tuple[list[dict], list[dict]]:
    """Keep items whose quote is copied EXACTLY (case and punctuation; whitespace collapsed only) from the answer
    and whose label words all appear in the answer. Kept items are PROPOSED and UNVERIFIED: the label is only
    lexically supported, never checked for meaning, and the student has not confirmed it."""
    kept, rejected, seen = [], [], set()
    hay, hay_words = _ws(answer), _content(answer)
    for raw in (text or "").splitlines():
        parts = [p.strip() for p in raw.strip().lstrip("-*0123456789.) ").split("|")]
        if len(parts) != 3:
            if raw.strip():
                rejected.append({"line": raw.strip()[:200], "reason": "not KIND | label | quote"})
            continue
        kind, label, quote = parts[0].lower(), parts[1].strip(" \"'"), parts[2].strip(" \"'")
        quote = _ws(quote)
        if kind not in KINDS or not label or len(label.split()) > 6:
            rejected.append({"line": raw.strip()[:200], "reason": "bad kind or label"})
        elif len(quote.split()) < 3 or quote not in hay:
            rejected.append({"line": raw.strip()[:200], "reason": "quote is not an exact copy from the student's answer"})
        elif not _content(label) or not _content(label) <= hay_words:
            rejected.append({"line": raw.strip()[:200], "reason": "label uses words the student did not say"})
        elif (kind, label.lower()) in seen:
            rejected.append({"line": raw.strip()[:200], "reason": "duplicate"})
        else:
            seen.add((kind, label.lower()))
            kept.append({"kind": kind, "label": label, "quote": quote, "status": "proposed_unverified",
                         "quote_exact": True, "label_check": "lexical_only_not_semantic", "student_confirmed": False})
    return kept[:3], rejected


def _post_loopback(url: str, body: dict, headers: dict, timeout: float) -> dict:
    """Loopback-only JSON POST with NO redirects and a hard timeout."""
    u = urlparse(url)
    if u.scheme != "http" or u.hostname not in {"127.0.0.1", "localhost", "::1"} or u.username or u.password:
        raise ProviderUnavailable("refusing non-loopback model endpoint")

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            raise ProviderError(f"model endpoint redirected (HTTP {code}); refusing to follow")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=min(timeout, CALL_TIMEOUT_S)) as resp:
            return json.loads(resp.read(2_000_000).decode())
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"HTTP {exc.code} from local model") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError) as exc:
        raise ProviderUnavailable(f"cannot reach local model: {exc}") from exc


def _harden(router: Router) -> Router:
    for p in router.providers:
        if hasattr(p, "transport"):
            p.transport, p.timeout = _post_loopback, CALL_TIMEOUT_S
    return router


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
        """turns: [{question, student_response}] so far, newest last. Never raises: any failure is a labeled fallback."""
        step = InterviewStep(question=fixed_next, question_source=FALLBACK)
        if not _SLOTS.acquire(blocking=False):
            step.detail = "local model busy; fixed script question used, no extraction"
            return step
        try:
            return self._step(step, track, turns, want_question)
        except Exception as exc:  # noqa: BLE001 - provider/JSON/shape errors must not 500 a saved turn
            step.question, step.extraction, step.rejected = step.question, [], []
            step.question_source, step.extraction_mode, step.provider, step.model = FALLBACK, "none_no_model", None, None
            step.detail = f"interviewer error ({type(exc).__name__}); fixed script question used, no extraction"
            return step
        finally:
            _SLOTS.release()

    def _step(self, step: InterviewStep, track: str, turns: list[dict], want_question: bool) -> InterviewStep:
        transcript = "\n".join(f"Coach: {t['question']}\nStudent: {t['student_response']}" for t in turns)
        conversation = " ".join(t["student_response"] + " " + t["question"] for t in turns)
        latest = turns[-1]["student_response"]
        asked = [t["question"] for t in turns]
        details: list[str] = []
        if want_question:
            routed = self._ask(QUESTION_SYSTEM, f"Track: {track}.\n{transcript}\nCoach:", self.question_tokens)
            if routed.ok:
                q = check_question(routed.result.text, asked, conversation)
                if q and _content(q) & _content(latest):
                    step.question, step.question_source = q, ADAPTIVE
                    step.provider, step.model = routed.result.provider, routed.result.model
                else:
                    details.append("model question failed lexical grounding checks; fixed script question used")
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
    urls = [u for u in (cfg.ornith_url, cfg.inkling_local_url, cfg.hermes_url) if u]
    if not urls or not all(_loopback(u) for u in urls):
        return None
    cfg = dataclasses.replace(cfg, allow_hosted=False)
    return AdaptiveInterviewer(_harden(Router.from_config(cfg)))
