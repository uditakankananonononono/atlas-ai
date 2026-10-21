"""Deterministic extractive section summarization for M04.

Spec: Module 4 - "New papers are summarised, embedded, and clustered" and the
hypothesis agent "extracts methods and findings". This is a heuristic
sentence-level classifier over the supplied abstract only: cue-word matching,
specific-to-general ordering (limitations, findings, methods, objective), no
network, no model calls. Output is labelled heuristic wherever consumed; it is
not LLM-quality summarization and does not claim verification.
"""
from __future__ import annotations

import re

SECTIONS = ("objective", "methods", "findings", "limitations")

_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("limitations", ("limitation", "however", "caution", "small sample", "future work", "limited", "bias", "confound")),
    ("findings", ("found", "showed", "increased", "reduced", "decreased", "associated",
                  "significant", "observed", "improved", "no effect", "correlated", "result")),
    ("methods", ("measured", "method", "assay", "protocol", "cohort", "randomized", "randomised",
                 "model", "sample", "workflow", "sequenc", "pipeline", "we used", "we performed")),
    ("objective", ("we investigate", "aim", "objective", "purpose", "hypothes", "we ask", "goal", "whether")),
)


def extract_sections(abstract: str) -> dict[str, str]:
    """Classify abstract sentences into objective/methods/findings/limitations.

    Deterministic and heuristic: each sentence goes to the first matching bucket
    in specific-to-general order; a leading sentence with no cues is treated as
    objective context when no sentence has been classified as objective yet
    (not necessarily the first sentence); later no-cue sentences are dropped
    (documented heuristic truth). Raises ValueError on a non-string or empty abstract (fail closed);
    non-string input is reachable over the mounted HTTP route, which passes a
    raw dict payload without schema validation.
    """
    if not isinstance(abstract, str):
        raise ValueError("abstract must be a string for extractive section derivation")
    if not abstract or not abstract.strip():
        raise ValueError("abstract is required for extractive section derivation")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", abstract.strip()) if s]
    buckets: dict[str, list[str]] = {key: [] for key in SECTIONS}
    for sentence in sentences:
        low = sentence.lower()
        for key, cues in _CUES:
            if any(cue in low for cue in cues):
                buckets[key].append(sentence)
                break
        else:
            if not buckets["objective"]:
                buckets["objective"].append(sentence)
    return {key: " ".join(parts) for key, parts in buckets.items()}
