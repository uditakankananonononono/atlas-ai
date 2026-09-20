"""Validation pipeline for collected documents.

Runs before anything reaches the LLM or the blueprint repository:
1. rights/platform legality (defense in depth after collectors)
2. URL canonicalization (tracking params stripped, stable identity)
3. exact dedup (content hash) and near-dup (5-gram shingle Jaccard)
4. scam-signal detection (expands the skeleton's five-term list)
5. prompt-injection detection - scraped text is prompt input, so hostile
   instructions inside it are quarantined, never passed through
6. basic quality gates (title, length, excerpt bound)

Every decision is a ValidationReport with reasons; nothing is silently dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .lane_models import PROHIBITED_PLATFORMS, PUBLIC_PAGE_EXCERPT_CHARS, RawDocument, RightsClass, SourceKind, sha256_text

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid", "si", "ref",
    "ref_src", "spm", "scid", "oly_anon_id", "oly_enc_id", "_hsenc", "_hsmi",
}

SCAM_PATTERNS: Sequence[tuple[str, str]] = (
    (r"guaranteed (income|money|profit|returns?)", "guaranteed_income"),
    (r"risk[ -]free", "risk_free_claim"),
    (r"pay (a )?(fee|deposit) to (unlock|start|join)", "pay_to_unlock"),
    (r"(double|triple) your (crypto|money|bitcoin)", "crypto_doubling"),
    (r"no work (required|needed)", "no_work_required"),
    (r"\$\s?\d[\d,]*\s?(/\s?|per )(day|hour|week)\b.*(effortless|easy|passive)", "effortless_daily_income"),
    (r"passive income while you sleep", "sleep_income"),
    (r"(recruit|downline|upline|mlm|multi[- ]level)", "mlm_signal"),
    (r"(limited spots|act now|only \d+ (spots|slots) left)", "urgency_pressure"),
    (r"(dm|message|whatsapp|telegram) me (for|to) (details|start|join)", "contact_lure"),
    (r"wire (transfer|money)|gift cards? (only|payment)", "payment_lure"),
    (r"1000%|10x your money|turn \$?\d+ into \$?\d{4,}", "absurd_returns"),
)

INJECTION_PATTERNS: Sequence[tuple[str, str]] = (
    (r"ignore (all |any )?(previous|prior|above) instructions?", "ignore_instructions"),
    (r"system prompt|developer (mode|message)|jailbreak", "system_prompt_probe"),
    (r"you are now |act as (a |an )?(dan|unfiltered)", "persona_override"),
    (r"(reveal|print|output|show) (your|the) (prompt|instructions|api key|secrets?)", "secret_exfiltration"),
    (r"do not (tell|inform) the user", "concealment"),
    (r"<\s*(script|iframe)\b", "markup_injection"),
    (r"\bexec(ute)?\s+(this|the following) (command|code)", "command_injection"),
)

RIGHTS_FOR_KIND: Mapping[SourceKind, frozenset[RightsClass]] = {
    SourceKind.REDDIT_JSON: frozenset({RightsClass.OFFICIAL_API}),
    SourceKind.YOUTUBE_DATA_API: frozenset({RightsClass.OFFICIAL_API}),
    SourceKind.HACKER_NEWS: frozenset({RightsClass.OFFICIAL_API}),
    SourceKind.DEV_TO: frozenset({RightsClass.OFFICIAL_API}),
    SourceKind.RSS: frozenset({RightsClass.RSS_FEED}),
    SourceKind.PUBLIC_WEB: frozenset({RightsClass.PUBLIC_PAGE}),
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def canonicalize_url(url: str) -> str:
    """Stable identity for dedup: lowercase host, no tracking params, no
    fragment, sorted query, no default port, single trailing-slash form."""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    host = parts.hostname.lower() if parts.hostname else ""
    if not host:
        raise ValueError(f"cannot canonicalize url without host: {url!r}")
    port = parts.port
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if k.lower() not in TRACKING_PARAMS))
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, query, ""))


def shingles(text: str, n: int = 5) -> frozenset[str]:
    words = _WORD_RE.findall(text.lower())
    if len(words) < n:
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class ValidationReport:
    accepted: bool
    canonical_url: str
    content_hash: str
    reasons: tuple[str, ...] = ()
    scam_signals: tuple[str, ...] = ()
    injection_flags: tuple[str, ...] = ()
    duplicate_of: Optional[str] = None      # content_hash of the surviving doc
    near_duplicate_of: Optional[str] = None
    similarity: float = 0.0
    quality_score: float = 0.0              # 0..1, feeds ranking's evidence_quality


@dataclass
class ValidatorConfig:
    min_text_chars: int = 80
    near_dup_threshold: float = 0.7
    max_scam_signals: int = 1               # >= this many distinct signals rejects
    reject_on_injection: bool = True
    min_quality: float = 0.15


class DocumentValidator:
    def __init__(self, config: ValidatorConfig | None = None):
        self.config = config or ValidatorConfig()
        self._scam = [(re.compile(p, re.IGNORECASE), name) for p, name in SCAM_PATTERNS]
        self._inject = [(re.compile(p, re.IGNORECASE), name) for p, name in INJECTION_PATTERNS]

    def scan_scam(self, text: str) -> tuple[str, ...]:
        return tuple(name for rx, name in self._scam if rx.search(text))

    def scan_injection(self, text: str) -> tuple[str, ...]:
        return tuple(name for rx, name in self._inject if rx.search(text))

    def quality(self, doc: RawDocument) -> float:
        """Heuristic evidence quality: structure beats vibes. Blueprints need
        steps, tools and monetisation hints; engagement and metadata help."""
        score = 0.0
        text = f"{doc.title}\n{doc.text}"
        words = len(_WORD_RE.findall(text))
        score += min(0.35, words / 400.0)                       # substantive content
        step_hits = len(re.findall(r"\b(step \d|first|then|next|finally)\b", text, re.IGNORECASE))
        score += min(0.25, step_hits * 0.05)                    # procedural structure
        if re.search(r"\b(tool|app|platform|software|site)\b", text, re.IGNORECASE):
            score += 0.1
        if re.search(r"\$|price|charge|revenue|income|sell", text, re.IGNORECASE):
            score += 0.1                                        # monetisation evidence
        if doc.engagement.get("comments", 0) > 0:
            score += 0.1                                        # community scrutiny
        if doc.published_at is not None:
            score += 0.1                                        # datable evidence
        return round(min(1.0, score), 4)

    def validate(
        self,
        doc: RawDocument,
        *,
        known_hashes: Optional[Mapping[str, str]] = None,      # content_hash -> doc_id
        known_shingles: Optional[Mapping[str, frozenset[str]]] = None,  # content_hash -> shingles
    ) -> ValidationReport:
        reasons: list[str] = []
        canonical = canonicalize_url(doc.url)
        content_hash = doc.content_hash or sha256_text(doc.title + "\n" + doc.text)

        # 1. legality, defense in depth
        if doc.platform in PROHIBITED_PLATFORMS:
            reasons.append(f"prohibited_platform:{doc.platform}")
        allowed_rights = RIGHTS_FOR_KIND.get(doc.kind)
        if allowed_rights is not None and doc.rights not in allowed_rights:
            reasons.append(f"rights_mismatch:{doc.kind.value}+{doc.rights.value}")
        if doc.rights is RightsClass.PROHIBITED:
            reasons.append("rights_prohibited")
        if doc.rights is RightsClass.PUBLIC_PAGE and len(doc.text) > PUBLIC_PAGE_EXCERPT_CHARS:
            reasons.append("excerpt_bound_exceeded")

        # 2. scam + injection
        full_text = f"{doc.title}\n{doc.text}"
        scam = self.scan_scam(full_text)
        injection = self.scan_injection(full_text)
        if len(scam) >= self.config.max_scam_signals + 1:
            reasons.append(f"scam_signals_exceeded:{len(scam)}")
        if injection and self.config.reject_on_injection:
            reasons.append("prompt_injection_detected")

        # 3. quality gates
        if not doc.title.strip():
            reasons.append("missing_title")
        if len(full_text.strip()) < self.config.min_text_chars:
            reasons.append("thin_content")
        quality = self.quality(doc)
        if quality < self.config.min_quality:
            reasons.append(f"low_quality:{quality:.2f}")

        # 4. dedup
        duplicate_of = None
        near_dup_of = None
        similarity = 0.0
        if known_hashes and content_hash in known_hashes:
            duplicate_of = known_hashes[content_hash]
            reasons.append("exact_duplicate")
        elif known_shingles:
            mine = shingles(full_text)
            best = (0.0, None)
            for other_hash, other_shingles in known_shingles.items():
                sim = jaccard(mine, other_shingles)
                if sim > best[0]:
                    best = (sim, other_hash)
            if best[0] >= self.config.near_dup_threshold:
                near_dup_of = best[1]
                similarity = round(best[0], 4)
                reasons.append(f"near_duplicate:{similarity:.2f}")

        return ValidationReport(
            accepted=not reasons,
            canonical_url=canonical,
            content_hash=content_hash,
            reasons=tuple(reasons),
            scam_signals=scam,
            injection_flags=injection,
            duplicate_of=duplicate_of,
            near_duplicate_of=near_dup_of,
            similarity=similarity,
            quality_score=quality,
        )

    def validate_batch(self, docs: Iterable[RawDocument]) -> list[tuple[RawDocument, ValidationReport]]:
        """Dedups within the batch as well as reporting per-doc decisions."""
        results: list[tuple[RawDocument, ValidationReport]] = []
        hashes: dict[str, str] = {}
        shingle_map: dict[str, frozenset[str]] = {}
        for doc in docs:
            report = self.validate(doc, known_hashes=hashes, known_shingles=shingle_map)
            results.append((doc, report))
            if report.accepted:
                hashes[report.content_hash] = doc.id
                shingle_map[report.content_hash] = shingles(doc.title + "\n" + doc.text)
        return results
