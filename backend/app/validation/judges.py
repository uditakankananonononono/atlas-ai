"""G115 / validation.judges - external validation harness wiring.

Source request (instinct doc; the provider label is rendered
"external evaluation providers" for publication): "Please use external
validation with your external evaluation providers (chatgpt, deepseek,
claude, perplexity) to check whether it adds every essence of my word into
working code."

What evidence_harness_p83 was missing (audit G115): it recorded caller claims
and never called a judge. This unit WIRES the judges: four provider adapters
(ChatGPT, DeepSeek, Claude, Perplexity) over a transport protocol, with
judge-packet construction from requirement text + code evidence, verdict
parsing (PASS/FAIL/FACADE + quoted criticism), SHA-256 receipts binding
provider/prompt/response, cross-provider aggregation with disagreement
flags, and a mechanical facade scan beside the judge verdicts.

Transports: BrowserSessionTransport drives the owner's login-session browser
agent (m13) at human speed through the provider's own web UI - the owner's
accounts, per the standing rule; FixtureTransport replays recorded responses
for offline tests and is labeled as such. A receipt proves a judge answered;
it never proves the underlying claim. Stdlib only; network lives behind the
injected transport.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from app.modules.c30 import policy

PREFIX = "JUDGE"
PROVIDERS = ("chatgpt", "deepseek", "claude", "perplexity")
PROVIDER_URLS = {"chatgpt": "https://chatgpt.com/", "deepseek": "https://chat.deepseek.com/",
                 "claude": "https://claude.ai/", "perplexity": "https://www.perplexity.ai/"}
VERDICTS = ("PASS", "FAIL", "FACADE")
MAX_REQUIREMENT = 4000
MAX_CODE = 200000
MAX_RESPONSE = 100000
STUB_PATTERNS = (
    re.compile(r"\bpass\s*(#.*)?$", re.M), re.compile(r"\bTODO\b"), re.compile(r"\bFIXME\b"),
    re.compile(r"TO_WRITE"), re.compile(r"NotImplementedError"), re.compile(r"\.\.\.\s*(#.*)?$", re.M),
    re.compile(r'return\s+\{\s*\}\s*$', re.M),
)


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _text(value, field, limit):
    if type(value) is not str:
        _refuse("BAD_TYPE", field)
    if len(value) > limit:
        _refuse("TEXT_TOO_LONG", field)
    if not value.strip():
        _refuse("EMPTY", field)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") and c not in "\n\t" for c in value):
        _refuse("CONTROL_CHARS", field)
    return value


def build_packet(requirement, code_evidence, provider):
    """The exact judge prompt sent to a provider."""
    req = _text(requirement, "requirement", MAX_REQUIREMENT)
    code = _text(code_evidence, "code_evidence", MAX_CODE)
    if provider not in PROVIDERS:
        _refuse("BAD_PROVIDER", str(provider)[:32])
    return (
        "You are an uncompromising external evaluator for code the owner asked to be built.\n"
        "REQUIREMENT (owner's words):\n\"\"\"\n%s\n\"\"\"\n\n"
        "CODE EVIDENCE (the implementation claiming to fulfill it):\n\"\"\"\n%s\n\"\"\"\n\n"
        "Judge whether the code adds every essence of the requirement into WORKING code.\n"
        "Rules: facade, stubs, placeholders, renamed shells or thin stand-ins are FACADE.\n"
        "Answer with EXACTLY one first line: VERDICT: PASS or VERDICT: FAIL or VERDICT: FACADE.\n"
        "Then up to 10 lines of criticism, each quoting the code or requirement it attacks."
    ) % (req, code)


class BrowserSessionTransport:
    """Live transport through the owner's login-session browser driver.

    The injected driver callable does the actual page work
    (driver(provider_url, prompt) -> response_text); m13's browser agent
    supplies it in production. This class owns pacing and validation."""

    def __init__(self, driver, min_interval_s=5):
        if not callable(driver):
            _refuse("BAD_TYPE", "driver")
        if isinstance(min_interval_s, bool) or not isinstance(min_interval_s, (int, float)) \
                or min_interval_s < 1:
            _refuse("BAD_TYPE", "min_interval_s")
        self._driver = driver
        self._min_interval = float(min_interval_s)
        self._last_call = {"t": None}

    def kind(self):
        return "live_browser_session"

    def complete(self, provider, prompt, now=None):
        import time
        t = time.monotonic() if now is None else now
        if self._last_call["t"] is not None and t - self._last_call["t"] < self._min_interval:
            _refuse("PACED", provider)  # human speed: refuse bursty judge traffic
        self._last_call["t"] = t
        response = self._driver(PROVIDER_URLS[provider], prompt)
        return _text(response, "response", MAX_RESPONSE)


class FixtureTransport:
    """Offline recorded-response transport, labeled; tests and dry runs only."""

    def __init__(self, responses):
        if type(responses) is not dict:
            _refuse("BAD_TYPE", "responses")
        self._responses = dict(responses)
        self.calls = []

    def kind(self):
        return "recorded_fixture"

    def complete(self, provider, prompt, now=None):
        self.calls.append(provider)
        if provider not in self._responses:
            _refuse("NO_FIXTURE", provider)
        return _text(self._responses[provider], "response", MAX_RESPONSE)


def parse_verdict(response):
    """Extract the verdict and criticism lines from a judge response."""
    text = _text(response, "response", MAX_RESPONSE)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        _refuse("EMPTY", "response")
    m = re.match(r"^VERDICT:\s*(PASS|FAIL|FACADE)\b", lines[0], re.I)
    if not m:
        _refuse("NO_VERDICT", lines[0][:80])
    verdict = m.group(1).upper()
    criticism = [l for l in lines[1:] if not l.upper().startswith("VERDICT")][:10]
    return {"verdict": verdict, "criticism": criticism}


def _receipt(provider, prompt, response, transport_kind):
    h = hashlib.sha256()
    h.update(provider.encode())
    h.update(b"\x00")
    h.update(prompt.encode())
    h.update(b"\x00")
    h.update(response.encode())
    return {"provider": provider, "sha256": h.hexdigest(), "transport": transport_kind,
            "provider_url": PROVIDER_URLS[provider],
            "proves": "this exact judge answered this exact prompt - not that the claim is true"}


def facade_scan(code):
    """Mechanical stub-pattern scan beside judge verdicts."""
    text = _text(code, "code_evidence", MAX_CODE)
    hits = []
    for pat in STUB_PATTERNS:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append({"pattern": pat.pattern, "line": line})
    return {"stub_markers": hits[:50], "marker_count": len(hits), "facade_suspect": bool(hits)}


def judge_requirement(requirement, code_evidence, transport, providers=PROVIDERS, now=None):
    """Run the full panel over one requirement; returns verdicts + receipts."""
    req = _text(requirement, "requirement", MAX_REQUIREMENT)
    code = _text(code_evidence, "code_evidence", MAX_CODE)
    if isinstance(providers, bool) or not isinstance(providers, (list, tuple)) or not providers:
        _refuse("BAD_TYPE", "providers")
    if not hasattr(transport, "complete") or not callable(transport.complete):
        _refuse("BAD_TYPE", "transport")
    rows = []
    for provider in providers:
        if provider not in PROVIDERS:
            _refuse("BAD_PROVIDER", str(provider)[:32])
        prompt = build_packet(req, code, provider)
        response = transport.complete(provider, prompt, now=now)
        parsed = parse_verdict(response)
        rows.append({"provider": provider, "verdict": parsed["verdict"],
                     "criticism": parsed["criticism"],
                     "receipt": _receipt(provider, prompt, response, transport.kind())})
    verdicts = [r["verdict"] for r in rows]
    counts = {v: verdicts.count(v) for v in VERDICTS}
    if len(set(verdicts)) == 1:
        consensus = verdicts[0]
    elif counts["FACADE"] > 0:
        consensus = "FACADE"  # any facade call from any judge poisons the claim
    else:
        consensus = "SPLIT"
    scan = facade_scan(code)
    return {
        "consensus": consensus, "counts": counts,
        "disagreement": len(set(verdicts)) > 1,
        "judges": rows, "facade_scan": scan,
        "mechanical_facade_suspect": scan["facade_suspect"],
        "final": "FACADE" if (consensus == "FACADE" or scan["facade_suspect"] and consensus != "PASS")
                 else consensus,
        "scope": policy.scope(
            ["four provider adapters with prompt construction and verdict parsing",
             "SHA-256 receipts binding provider/prompt/response",
             "cross-provider aggregation with facade-poisoning and disagreement flags",
             "mechanical stub scan reported beside judge verdicts"],
            ["proof of truth - a receipt proves a judge answered, never that code works",
             "live calls offline - FixtureTransport is labeled recorded_fixture",
             "provider account state - the browser session belongs to the owner"],
            "supplied requirement, code evidence and transport",
            "supplied-input"),
    }
