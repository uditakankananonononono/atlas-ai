"""Adaptive, model-backed student interviewer with quote-verified extraction.

Truth labels (never merged):
- question_source "adaptive_span_anchored": the model only chose an exact span of the student's answer and a type from a
  closed list; the question text is OURS around that span, so it cannot invent student facts (span choice quality unverified).
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
import time
import json
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from instinct_models import ProductConfig, ProviderError, ProviderUnavailable, Router, Task, load_config
from instinct_models.router import RouteAttempt, RoutedResult

import os as _os
CALL_TIMEOUT_S = float(_os.environ.get("INSTINCT_INTERVIEW_CALL_TIMEOUT", "20"))  # per model call; an answer makes at most 2 calls
_SLOTS = threading.BoundedSemaphore(2)  # at most 2 model calls in flight (held until the call thread really ends)
STEP_BUDGET_S = float(_os.environ.get("INSTINCT_INTERVIEW_STEP_BUDGET", "12"))  # wall-clock cap for ALL model work in one answer

ADAPTIVE = "adaptive_local_model"          # model wrote the whole question (strict lexical guards)
ANCHORED = "adaptive_span_anchored"        # model chose a span + type; WE wrote the question around the exact span
FALLBACK = "fixed_script_fallback"
KINDS = ("value", "strength", "pattern")
_DRAFT_MARKERS = ("dear ", "in conclusion", "here is your", "here's your", "essay:", "sincerely", "personal statement:")

QUESTION_SYSTEM = (
    "You are a warm college-and-career story coach interviewing a student. Ask exactly ONE short "
    "follow-up question that builds on a specific detail the student just said. Do not write any "
    "essay text, advice, praise paragraphs or lists. Output only the question, ending with a question mark."
)
SPAN_SYSTEM = (
    "Read the student's latest answer. Pick the ONE phrase (4 to 12 words) that is most worth asking about and "
    "copy it EXACTLY from the answer. Then pick TYPE: scene (ask for a concrete moment), feeling, reason (why it "
    "mattered) or change (what changed afterwards). Output one line only: TYPE | copied phrase"
)
SPAN_EXAMPLE_USER = ("Student's latest answer:\nI coached the junior swim team every Saturday for two years "
                     "because I wanted kids who were scared of water to feel safe.")
SPAN_EXAMPLE_REPLY = "reason | kids who were scared of water to feel safe"
SPAN_TYPES = {
    "scene": 'You mentioned "{span}". Can you walk me through one specific moment when that happened?',
    "feeling": 'You mentioned "{span}". How did that feel for you at the time?',
    "reason": 'You mentioned "{span}". Why did that matter to you?',
    "change": 'You mentioned "{span}". What changed for you after that?',
}
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
    anchor: dict | None = None

    @property
    def model_backed(self) -> bool:
        return self.question_source in (ADAPTIVE, ANCHORED) or self.extraction_mode == ADAPTIVE

    def as_dict(self) -> dict:
        return {"question": self.question, "question_source": self.question_source, "extraction": self.extraction,
                "rejected": self.rejected, "extraction_mode": self.extraction_mode, "provider": self.provider,
                "model": self.model, "detail": self.detail, "anchor": self.anchor, "model_backed": self.model_backed}


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


def parse_span(text: str, answer: str, asked: list[str]) -> tuple[str, str] | None:
    """(type, exact_span) when the model's span is an exact 3-14 word copy of the answer and the type is allowed."""
    line = next((x.strip() for x in (text or "").strip().splitlines() if x.strip()), "")
    parts = [p.strip() for p in line.lstrip("-*0123456789.) ").split("|")]
    if len(parts) != 2 or parts[0].lower() not in SPAN_TYPES:
        return None
    span = _ws(parts[1].strip(" \"'"))
    if not 3 <= len(span.split()) <= 14 or span not in _ws(answer):
        return None
    q = SPAN_TYPES[parts[0].lower()].format(span=span)
    return None if _norm(q) in {_norm(a) for a in asked} else (parts[0].lower(), span)


_REASONS = {"budget_exhausted": "step time budget used up", "timeout": "model call timed out and was abandoned",
            "busy": "2 model calls already in flight"}


def _why(routed: RoutedResult, consequence: str) -> str:
    """Reason-specific detail: budget/timeout/busy are NOT 'unreachable'."""
    for a in routed.attempts:
        if a.outcome in _REASONS:
            return f"{_REASONS[a.outcome]}; {consequence}"
    return ("no local model reachable (" + "; ".join(f"{a.provider}:{a.outcome}" for a in routed.attempts)
            + f"); {consequence}")


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
        limit = min(timeout, CALL_TIMEOUT_S)
        deadline = time.monotonic() + limit
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open(req, timeout=limit) as resp:
            buf = b""
            while True:  # total wall-clock deadline, so a trickling server cannot hold the call open
                chunk = resp.read1(16384)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 2_000_000 or time.monotonic() > deadline:
                    raise ProviderUnavailable("local model response too large or too slow")
            return json.loads(buf.decode())
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
    def __init__(self, router: Router, *, question_tokens: int = 60, extract_tokens: int = 160, freeform: bool = False):
        # freeform=True additionally tries a model-written question (strict lexical guards); off by default because
        # real small-model runs failed those guards on every turn (see docs).
        self.router, self.question_tokens, self.extract_tokens, self.freeform = router, question_tokens, extract_tokens, freeform
        self._tl = threading.local()

    def _ask(self, system: str, user: str, max_tokens: int, example: tuple[str, str] | None = None):
        """One model call under the step's wall-clock budget, in a daemon thread (hard cap on request latency).
        A call that outlives the budget is abandoned for this request; it keeps its slot until it really ends."""
        shots = ([{"role": "user", "content": example[0]}, {"role": "assistant", "content": example[1]}]
                 if example else [])
        task = Task(messages=[{"role": "system", "content": system}, *shots, {"role": "user", "content": user}],
                    private=True, max_tokens=max_tokens)
        remaining = getattr(self._tl, "deadline", time.monotonic() + STEP_BUDGET_S) - time.monotonic()
        if remaining < 1.0:
            return RoutedResult(None, [RouteAttempt("local", "budget_exhausted", f"{STEP_BUDGET_S:g}s step budget used")])
        if not _SLOTS.acquire(blocking=False):
            return RoutedResult(None, [RouteAttempt("local", "busy", "2 model calls already in flight")])
        box: dict = {}

        def work():
            try:
                box["r"] = self.router.run(task)
            except Exception as exc:  # noqa: BLE001
                box["e"] = exc
            finally:
                _SLOTS.release()
        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(remaining)
        if t.is_alive():
            return RoutedResult(None, [RouteAttempt("local", "timeout", f"abandoned after {remaining:.1f}s; generation may continue locally")])
        if "e" in box:
            raise box["e"]
        return box["r"]

    def step(self, *, track: str, turns: list[dict], fixed_next: str | None, want_question: bool) -> InterviewStep:
        """turns: [{question, student_response}] so far, newest last. Never raises: any failure is a labeled fallback."""
        step = InterviewStep(question=fixed_next, question_source=FALLBACK)
        self._tl.deadline = time.monotonic() + STEP_BUDGET_S  # thread-local: safe if one interviewer serves several threads
        try:
            return self._step(step, track, turns, want_question)
        except Exception as exc:  # noqa: BLE001 - provider/JSON/shape errors must not 500 a saved turn
            step.question, step.extraction, step.rejected = fixed_next, [], []
            step.question_source, step.extraction_mode, step.provider, step.model = FALLBACK, "none_no_model", None, None
            step.anchor = None
            step.detail = f"interviewer error ({type(exc).__name__}); fixed script question used, no extraction"
            return step

    def _step(self, step: InterviewStep, track: str, turns: list[dict], want_question: bool) -> InterviewStep:
        transcript = "\n".join(f"Coach: {t['question']}\nStudent: {t['student_response']}" for t in turns)
        conversation = " ".join(t["student_response"] + " " + t["question"] for t in turns)
        latest = turns[-1]["student_response"]
        asked = [t["question"] for t in turns]
        details: list[str] = []
        if want_question:
            routed = self._ask(SPAN_SYSTEM, f"Student's latest answer:\n{latest}", 40,
                               example=(SPAN_EXAMPLE_USER, SPAN_EXAMPLE_REPLY))
            if routed.ok:
                picked = parse_span(routed.result.text, latest, asked)
                if picked:
                    step.question = SPAN_TYPES[picked[0]].format(span=picked[1])
                    step.question_source = ANCHORED
                    step.provider, step.model = routed.result.provider, routed.result.model
                    step.anchor = {"type": picked[0], "span": picked[1]}
                else:
                    details.append("model span was not an exact copy / allowed type; fixed script question used")
            else:
                details.append(_why(routed, "fixed script question used"))
            if step.question_source == FALLBACK and self.freeform:
                routed = self._ask(QUESTION_SYSTEM, f"Track: {track}.\n{transcript}\nCoach:", self.question_tokens)
                if routed.ok:
                    q = check_question(routed.result.text, asked, conversation)
                    if q and _content(q) & _content(latest):
                        step.question, step.question_source = q, ADAPTIVE
                        step.provider, step.model = routed.result.provider, routed.result.model
                    else:
                        details.append("model question failed lexical grounding checks; fixed script question used")
        routed = self._ask(EXTRACT_SYSTEM, f"Student's latest answer:\n{latest}", self.extract_tokens,
                           example=(EXTRACT_EXAMPLE_USER, EXTRACT_EXAMPLE_REPLY))
        if routed.ok:
            step.extraction, step.rejected = parse_extraction(routed.result.text, latest)
            step.extraction_mode = ADAPTIVE
            step.provider, step.model = step.provider or routed.result.provider, step.model or routed.result.model
        else:
            details.append(_why(routed, "no quote extraction"))
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
