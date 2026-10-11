"""P69|L58 prohibited-bio-content rule pack. Pure stdlib, no I/O, no network, no ML.

Contract text verbatim: "Do not produce wet-lab protocols, pathogen enhancement,
harmful biological instructions, or anything that could cause harm."

Lexical exact-phrase screen over a closed pattern list seeded from the three
enumerable categories. "Anything that could cause harm" is deliberately NOT a
catch-all: only the listed patterns block. A clear verdict means only that no
listed pattern matched.
"""
from __future__ import annotations

from typing import Any

# Closed prohibited-pattern list in documented category order. Extending it is
# a contract change (see docs/INSTINCT_P69_L58_PROHIBITED_BIO_CONTRACT.md).
PROHIBITED_PATTERNS = (
    ('wet_lab_protocol', ('incubate at', 'centrifuge', 'pipette', 'culture medium', 'inoculate')),
    ('pathogen_enhancement', ('gain of function', 'enhance transmissibility', 'increase virulence')),
    ('harm_instruction', ('how to synthesize', 'how to culture', 'weaponiz')),
)

KINDS = ('protocol', 'instruction', 'claim', 'other')
MAX_ID_LENGTH = 64
MAX_TEXT_LENGTH = 4096
_FIELDS = {'id', 'kind', 'text'}


def _refuse(code: str) -> None:
    raise ValueError(code)


def _validate(document: Any) -> dict:
    if type(document) is not dict:
        _refuse('P69:bad_type:document')
    if set(document) != _FIELDS:
        _refuse('P69:unknown_fields:document')
    doc_id, kind, text = document['id'], document['kind'], document['text']
    if type(doc_id) is not str:
        _refuse('P69:bad_type:id')
    if not doc_id.strip():
        _refuse('P69:empty_field:id')
    if len(doc_id) > MAX_ID_LENGTH:
        _refuse('P69:id_too_long:id')
    if type(kind) is not str:
        _refuse('P69:bad_type:kind')
    if kind not in KINDS:
        _refuse(f'P69:bad_kind:{kind}')
    if type(text) is not str:
        _refuse('P69:bad_type:text')
    if not text.strip():
        _refuse('P69:empty_field:text')
    if len(text) > MAX_TEXT_LENGTH:
        _refuse('P69:text_too_long:text')
    return {'id': doc_id, 'kind': kind, 'text': text}


def _lowered_with_index(text: str) -> tuple[str, list[int]]:
    """Lowercase per character, keeping a map from each lowered position back to
    the originating index in the caller's text. Per-character lowering preserves
    text.lower() semantics for every ASCII pattern while tracking length-expanding
    characters (U+0130 lowers to two codepoints), so reported offsets always index
    the caller's original text."""
    parts: list[str] = []
    index: list[int] = []
    for position, char in enumerate(text):
        lowered = char.lower()
        parts.append(lowered)
        index.extend([position] * len(lowered))
    return ''.join(parts), index


def screen(document: dict) -> dict:
    """Screen one document; returns a verdict dict. Blocked content is a verdict,
    never a refusal. Matching is case-insensitive exact-phrase (substring) search
    over the caller's text; the offset indexes the caller's original text."""
    doc = _validate(document)
    lowered, index = _lowered_with_index(doc['text'])
    for category, patterns in PROHIBITED_PATTERNS:
        for pattern in patterns:
            lowered_offset = lowered.find(pattern)
            if lowered_offset != -1:
                return {'id': doc['id'], 'verdict': f'blocked:{category}', 'category': category,
                        'matched_pattern': pattern, 'offset': index[lowered_offset]}
    return {'id': doc['id'], 'verdict': 'clear', 'category': None,
            'matched_pattern': None, 'offset': None}


def screen_batch(documents: list) -> list:
    """Screen in sorted-id order; refuses the batch on the first malformed
    document encountered in that order. Blocked content stays a verdict."""
    if type(documents) is not list:
        _refuse('P69:bad_type:documents')

    def sort_key(document: Any) -> str:
        if type(document) is dict and type(document.get('id')) is str:
            return document['id']
        return ''

    return [screen(document) for document in sorted(documents, key=sort_key)]
