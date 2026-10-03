"""Student-authored essay critique (scoped, unaudited). Coaching only: it never writes or rewrites essay text.

Every item carries an EXACT quote copied from the student's draft plus either a measurement we computed ourselves
(source "verified_measure") or a question built from a fixed template around a span the local model picked
(source "model_selected_span"). The model only chooses a span and a type from a closed list; the question text is
ours, so no model-written prose reaches the student. Whether a chosen span is the best one is NOT verified.
If no usable local model answers, only the verified measures are returned and the response says so.
"""
from __future__ import annotations

import dataclasses
import json
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from instinct_models import ProviderError, ProviderUnavailable, Router, Task, load_config
from instinct_models.router import RouteAttempt, RoutedResult

MODEL_SPAN = "model_selected_span"
VERIFIED = "verified_measure"
HEURISTIC = "keyword_heuristic"
MAX_DRAFT = 6000        # model sees at most this many characters (explicitly reported); measures use the full draft
MAX_MEASURE = 100000
STEP_BUDGET_S = 12.0
CALL_TIMEOUT_S = 20.0
_SLOTS = threading.BoundedSemaphore(2)

SPAN_SYSTEM = (
    "You coach a student on their own college essay draft. Pick up to 2 phrases (4 to 14 words each) that are worth "
    "asking the student about, and copy each EXACTLY from the draft. For each pick TYPE: scene (ask for one concrete "
    "moment), evidence (ask what example proves a claim), reason (why it mattered) or change (what changed). "
    "Output one line per phrase: TYPE | copied phrase. Output nothing else."
)
SPAN_EXAMPLE_USER = ("Draft:\nI have always been a hard worker. Last year I coached the junior swim team every Saturday "
                     "because I wanted kids who were scared of water to feel safe.")
SPAN_EXAMPLE_REPLY = "evidence | I have always been a hard worker\nreason | kids who were scared of water to feel safe"
TEMPLATES = {
    "scene": 'You wrote "{q}". Can you describe one specific moment when that happened, in your own words?',
    "evidence": 'You wrote "{q}". What is one example from your life that shows this?',
    "reason": 'You wrote "{q}". Why did that matter to you?',
    "change": 'You wrote "{q}". What changed for you after that?',
}
ABSTRACT = ("passionate", "hardworking", "hard worker", "dedicated", "determined", "natural leader", "team player",
            "always been", "love to learn")
_SENT = re.compile(r"(?<=[.!?])\s+")
_STOP = set("that this with from have what when where which would could about your their there them they then than been "
            "were will just into over some more very also because while after before again being".split())


def _sentences(draft: str) -> list[str]:
    return [s.strip() for s in _SENT.split(draft.strip()) if s.strip()]


def _ws(t: str) -> str:
    return " ".join((t or "").split())


def _word_re(w: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)", re.I)


def verified_measures(draft: str) -> list[dict]:
    """long_sentence and repeated_word are exact counts (VERIFIED). trait_word is only a KEYWORD HEURISTIC: it can
    flag a sentence that already contains a good example, and says so. Quotes are exact sentences of the draft."""
    out, sents = [], _sentences(draft[:MAX_MEASURE])
    for s in sents:
        n = len(s.split())
        if n > 40:
            out.append({"type": "long_sentence", "source": VERIFIED, "quote": s,
                        "observation": f"This sentence has {n} words (over 40).",
                        "question": "Which one idea in this sentence matters most to you?"})
    counts: dict[str, int] = {}
    for w in re.findall(r"[A-Za-z']+", draft[:MAX_MEASURE].lower()):
        w = w.strip("'")
        if len(w) > 4 and w not in _STOP:
            counts[w] = counts.get(w, 0) + 1
    for w, n in sorted(counts.items(), key=lambda kv: -kv[1])[:2]:
        if n >= 4:
            first = next((s for s in sents if _word_re(w).search(s)), None)
            if first:
                out.append({"type": "repeated_word", "source": VERIFIED, "quote": first,
                            "observation": f'The whole word "{w}" appears {n} times in the draft (case-insensitive); '
                                           "the first sentence containing it is quoted.",
                            "question": "Where could a different, more specific word or detail say what you mean?"})
    for s in sents:
        hit = next((a for a in ABSTRACT if _word_re(a).search(s)), None)
        if hit:
            out.append({"type": "trait_word", "source": HEURISTIC, "quote": s,
                        "observation": f'Keyword heuristic only: this sentence contains the trait phrase "{hit}". '
                                       "It may already include a specific example; you decide.",
                        "question": "Is there one specific moment that shows this about you?"})
    return out[:8]


def parse_spans(text: str, draft: str) -> tuple[list[dict], list[dict]]:
    kept, rejected, seen = [], [], set()
    for raw in (text or "").splitlines():
        parts = [p.strip() for p in raw.strip().lstrip("-*0123456789.) ").split("|")]
        if len(parts) != 2 or parts[0].lower() not in TEMPLATES:
            if raw.strip():
                rejected.append({"line": raw.strip()[:200], "reason": "not TYPE | phrase with an allowed type"})
            continue
        span = parts[1].strip(" \"'")
        if not 4 <= len(span.split()) <= 14 or not re.search(r"(?<!\w)" + re.escape(span) + r"(?!\w)", draft):
            rejected.append({"line": raw.strip()[:200],
                             "reason": "phrase is not an exact raw substring of the draft at word boundaries"})
        elif span in seen:
            rejected.append({"line": raw.strip()[:200], "reason": "duplicate"})
        else:
            seen.add(span)
            kept.append({"type": parts[0].lower(), "source": MODEL_SPAN, "quote": span,
                         "question": TEMPLATES[parts[0].lower()].format(q=span), "span_quality": "unverified"})
    return kept[:2], rejected


def _post_loopback(url: str, body: dict, headers: dict, timeout: float) -> dict:
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
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(req, timeout=limit) as resp:
            buf = b""
            while chunk := resp.read1(16384):
                buf += chunk
                if len(buf) > 2_000_000 or time.monotonic() > deadline:
                    raise ProviderUnavailable("local model response too large or too slow")
        return json.loads(buf.decode())
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"HTTP {exc.code} from local model") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError) as exc:
        raise ProviderUnavailable(f"cannot reach local model: {exc}") from exc


def _loopback(url: str | None) -> bool:
    return bool(url) and (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def router_from_env(env: dict | None = None) -> Router | None:
    import os
    e = dict(os.environ if env is None else env)
    e.setdefault("INSTINCT_PRODUCT", "atlas")
    cfg = load_config(e)
    urls = [u for u in (cfg.ornith_url, cfg.inkling_local_url, cfg.hermes_url) if u]
    if not urls or not all(_loopback(u) for u in urls):
        return None
    router = Router.from_config(dataclasses.replace(cfg, allow_hosted=False))
    for p in router.providers:
        if hasattr(p, "transport"):
            p.transport, p.timeout = _post_loopback, CALL_TIMEOUT_S
    return router


def _ask(router: Router, draft: str) -> RoutedResult:
    task = Task(messages=[{"role": "system", "content": SPAN_SYSTEM},
                          {"role": "user", "content": SPAN_EXAMPLE_USER}, {"role": "assistant", "content": SPAN_EXAMPLE_REPLY},
                          {"role": "user", "content": f"Draft:\n{draft}"}], private=True, max_tokens=90)
    if not _SLOTS.acquire(blocking=False):
        return RoutedResult(None, [RouteAttempt("local", "busy", "2 model calls already in flight")])
    box: dict = {}

    def work():
        try:
            box["r"] = router.run(task)
        except Exception as exc:  # noqa: BLE001
            box["e"] = exc
        finally:
            _SLOTS.release()
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(STEP_BUDGET_S)
    if t.is_alive():
        return RoutedResult(None, [RouteAttempt("local", "timeout", f"abandoned after {STEP_BUDGET_S:g}s")])
    if "e" in box:
        return RoutedResult(None, [RouteAttempt("local", "error", type(box["e"]).__name__)])
    return box["r"]


def critique(draft: str, router: Router | None) -> dict:
    draft = draft.strip()
    seen_by_model = draft[:MAX_DRAFT]
    items = verified_measures(draft)
    mode, detail, rejected, model = "verified_measures_only_no_model", "", [], None
    if router is None:
        detail = "no local model configured; only verified measures returned"
    else:
        routed = _ask(router, seen_by_model)
        if routed.ok:
            spans, rejected = parse_spans(routed.result.text, seen_by_model)
            items += spans
            model = routed.result.model
            mode = "model_selected_spans_plus_verified_measures" if spans else "verified_measures_only_model_spans_rejected"
            if not spans:
                detail = "model gave no usable span; only verified measures returned"
        else:
            a = routed.attempts[0] if routed.attempts else None
            detail = (f"model call {a.outcome}" if a and a.outcome in ("busy", "timeout", "error")
                      else "no local model reachable") + "; only verified measures returned"
    return {"mode": mode, "detail": detail, "model": model, "items": items, "rejected_model_lines": rejected,
            "processed": {"draft_chars": len(draft), "measures_chars": min(len(draft), MAX_MEASURE),
                          "model_chars_considered": len(seen_by_model), "model_truncated": len(draft) > MAX_DRAFT},
            "student_authored_final": True, "generated_essay_prose": None, "revised_draft": None,
            "limits": "span choice and question relevance are not verified; this is coaching, not a rewrite"}
