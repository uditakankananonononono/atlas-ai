"""S2.8-delta / c32.thought_chains - evidence-bearing reasoning-move analyzer.

Extends c32.thought (which stays untouched) with auditable cue evidence,
per-1000-word normalization, sentence-based move chains and transitions,
speaker turns, chapter segments, negation and quote exclusion. Rule and
word-list based over SUPPLIED text only: it tags surface cues, it does not
model thought. Audio is not transcribed (no bundled ASR). Stdlib only,
offline, deterministic.
"""
from __future__ import annotations

import bisect
import copy
import math
import re
import unicodedata

from app.modules.c30 import policy
from app.modules.c32 import thought as _legacy

PREFIX = "TREND"
MAX_TEXTS = 10000
MAX_TEXT = 200000
MAX_SPEAKER = 64
MAX_ANNOTATIONS = 1000
MAX_TOTAL_ANNOTATIONS = 20000
MAX_TOTAL_TEXT = 5000000
MAX_KEYS = 16
_REQUEST_KEYS = frozenset({"docs"})
_DOC_KEYS = frozenset({"id", "kind", "medium", "text", "turns", "segments"})
_TURN_KEYS = frozenset({"speaker", "text", "t_start"})
_SEGMENT_KEYS = frozenset({"label", "text"})
_ECHO_FORBIDDEN = frozenset({"Cc", "Cf", "Zl", "Zp"})
MEDIA = ("podcast", "audiobook", "book", "article", "essay", "speech", "lecture",
         "interview", "lyrics", "poem", "other")
KINDS = ("transcript", "text", "lyrics")
CUES = {
    "analogy": ("like a", "like an", "as if", "similar to", "reminds", "reminded", "reminding"),
    "first_principles": ("first principles", "first principle", "fundamental", "fundamentals",
                         "from scratch", "why is", "why are"),
    "heuristic": ("rule of thumb", "rules of thumb", "usually", "tends to", "tend to",
                  "tended to", "as a rule"),
    "inversion": ("opposite", "opposites", "in reverse", "instead", "backwards"),
    "narrative": ("story", "stories", "journey", "journeys", "once", "chapter", "chapters"),
    "systems": ("feedback", "loop", "loops", "system", "systems", "emerges", "emerge",
                "emerging", "network", "networks"),
}
MOVE_NAMES = tuple(sorted(CUES))
_CUE_WORDS = {mv: tuple(tuple(c.split()) for c in cues) for mv, cues in CUES.items()}
_NEG = frozenset({"not", "no", "never"})
_NEG_WINDOW = 3
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")
MAX_EVIDENCE = 5
REPORT_CAVEAT_TEMPLATE = (
    "This analyzer tags reasoning-move cues using a fixed word list. Counts show where cues appear in the "
    "supplied text, not whether anyone reasoned well or originally. Precision and recall are agreement with "
    "synthetic labels written for this fixture, not validation of human thinking. Audio is not transcribed. "
    "Only the media supplied are covered: {media}.")
VALIDITY_METRIC_NAME = "labeled-fixture agreement metrics"
FIXTURE_FILE = "c32_thought_chains_120.json"
FIXTURE_SENTENCES = 123
FIXTURE_AGREEMENT = {
    'analogy': {'tp': 17, 'fp': 0, 'fn': 3, 'precision': 1.0, 'recall': 0.85},
    'first_principles': {'tp': 14, 'fp': 1, 'fn': 2, 'precision': 0.933333, 'recall': 0.875},
    'heuristic': {'tp': 13, 'fp': 0, 'fn': 2, 'precision': 1.0, 'recall': 0.866667},
    'inversion': {'tp': 10, 'fp': 1, 'fn': 3, 'precision': 0.909091, 'recall': 0.769231},
    'narrative': {'tp': 14, 'fp': 2, 'fn': 2, 'precision': 0.875, 'recall': 0.875},
    'systems': {'tp': 14, 'fp': 3, 'fn': 2, 'precision': 0.823529, 'recall': 0.875},
}


def _sentences(text):
    """(start, end) spans: '.', '!' or '?' followed by whitespace/end, or any newline."""
    spans = []
    n = len(text)
    start = 0
    i = 0
    while i < n:
        c = text[i]
        if c == "\n":
            spans.append((start, i))
            start = i + 1
        elif c in ".!?" and (i + 1 == n or text[i + 1].isspace()):
            spans.append((start, i + 1))
            start = i + 1
        i += 1
    spans.append((start, n))
    out = []
    for a, b in spans:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            out.append((a, b))
    return out


def _quotes(text):
    spans = []
    unmatched = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c in '"\u201c':
            j = text.find('"' if c == '"' else "\u201d", i + 1)
            if j < 0:
                unmatched += 1
                i += 1
            else:
                spans.append((i, j))
                i = j + 1
        else:
            if c == "\u201d":
                unmatched += 1
            i += 1
    return spans, unmatched


def _in_span(pos, spans):
    return any(a < pos < b for a, b in spans)


def _rate(n, words):
    return round(n * 1000 / words, 6) if words else 0.0


def _bad(name):
    raise ValueError("TREND_REFUSED_BAD_TYPE:" + name)


def _oversize(name):
    raise ValueError("TREND_REFUSED_OVERSIZE:" + name)


def _raw_text(value, name, limit=None):
    if type(value) is not str:
        _bad(name)
    if limit is not None and len(value) > limit:
        _oversize(name)
    return value


def _mapping(value, name, keys):
    if type(value) is not dict:
        _bad(name)
    if len(value) > MAX_KEYS:
        _oversize(name)
    if any(type(k) is not str or k not in keys for k in value):
        _bad(name)


def _list(value, name, limit):
    if type(value) is not list:
        _bad(name)
    if len(value) > limit:
        _oversize(name)


def _preflight(request):
    """Bound the whole request before scans, partition comparisons or analysis.

    Repeated document strings count repeatedly: this budget bounds analysis
    workload, not distinct Python allocations. Annotation counts are separate
    per-kind budgets. No incoming object is copied or normalized.
    """
    _mapping(request, "request", _REQUEST_KEYS)
    docs = request.get("docs")
    _list(docs, "docs", MAX_TEXTS)
    if not docs:
        raise ValueError("TREND_REFUSED_EMPTY:docs")
    total_text = total_turns = total_segments = 0
    for d in docs:
        _mapping(d, "docs", _DOC_KEYS)
        text = _raw_text(d.get("text"), "text", MAX_TEXT)
        total_text += len(text)
        if total_text > MAX_TOTAL_TEXT:
            _oversize("docs")
        _raw_text(d.get("id"), "id", 64)
        _raw_text(d.get("kind", "text"), "kind")
        _raw_text(d.get("medium"), "medium")
        for name, allowed in (("turns", _TURN_KEYS), ("segments", _SEGMENT_KEYS)):
            parts = d.get(name)
            if parts is None:
                continue
            _list(parts, name, MAX_ANNOTATIONS)
            if name == "turns":
                total_turns += len(parts)
                count = total_turns
            else:
                total_segments += len(parts)
                count = total_segments
            if count > MAX_TOTAL_ANNOTATIONS:
                _oversize(name)
            offset = 0
            for part in parts:
                _mapping(part, name, allowed)
                field = "speaker" if name == "turns" else "label"
                _raw_text(part.get(field), field, MAX_SPEAKER if name == "turns" else 64)
                chunk = _raw_text(part.get("text"), "turn_text" if name == "turns" else "segment_text")
                offset += len(chunk)
                if offset > len(text):
                    raise ValueError("TREND_REFUSED_BAD_SEGMENT")
                if name == "turns":
                    ts = part.get("t_start")
                    if ts is not None and (type(ts) not in (int, float)
                            or (type(ts) is float and not math.isfinite(ts)) or ts < 0):
                        _bad("t_start")
    return docs


def _echo_hygiene(value, name):
    if any(unicodedata.category(c) in _ECHO_FORBIDDEN for c in value):
        _bad(name)


def _bounded_text(value, name, limit, *, allow_ws=False):
    _raw_text(value, name, limit)
    if name in ("id", "label", "speaker"):
        _echo_hygiene(value, name)
    return policy.clean_text(value, PREFIX, name, limit, allow_ws=allow_ws)


def _text_field(value, name):
    return _bounded_text(value, name, MAX_TEXT, allow_ws=True)


def _partition_part(part, text, offset):
    if len(part) > len(text) - offset or not text.startswith(part, offset):
        raise ValueError("TREND_REFUSED_BAD_SEGMENT")
    return offset + len(part)


def _legacy_counts(text):
    """Per-move counts exactly as c32.thought.analyze() computes them (same MOVES table and
    substring count). analyze() itself refuses newlines, so its counting expression is applied
    here directly, which keeps lyrics comparable."""
    low = text.lower()
    return {move: sum(low.count(k) for k in keys) for move, keys in _legacy.MOVES.items()}


def _check_turns(turns, text):
    _list(turns, "turns", MAX_ANNOTATIONS)
    prev = None
    offset = 0
    for t in turns:
        _mapping(t, "turns", _TURN_KEYS)
        sp = _raw_text(t.get("speaker"), "speaker", MAX_SPEAKER)
        _echo_hygiene(sp, "speaker")
        if not sp.strip():
            raise ValueError("TREND_REFUSED_NOSPEAKER")
        _bounded_text(sp, "speaker", MAX_SPEAKER)
        _raw_text(t.get("text"), "turn_text")
        ts = t.get("t_start")
        if ts is not None:
            if type(ts) not in (int, float) or (type(ts) is float and not math.isfinite(ts)) or ts < 0:
                raise ValueError("TREND_REFUSED_BAD_TYPE:t_start")
            if prev is not None and ts < prev:
                raise ValueError("TREND_REFUSED_BAD_SEGMENT")
            prev = ts
        offset = _partition_part(t["text"], text, offset)
    if offset != len(text):
        raise ValueError("TREND_REFUSED_BAD_SEGMENT")


def _check_segments(segments, text):
    _list(segments, "segments", MAX_ANNOTATIONS)
    offset = 0
    for s in segments:
        _mapping(s, "segments", _SEGMENT_KEYS)
        _bounded_text(s.get("label"), "label", 64)
        _raw_text(s.get("text"), "segment_text")
        offset = _partition_part(s["text"], text, offset)
    if offset != len(text):
        raise ValueError("TREND_REFUSED_BAD_SEGMENT")


def _analyze_doc(d):
    _mapping(d, "docs", _DOC_KEYS)
    kind = d.get("kind", "text")
    if kind == "audio":
        raise ValueError("TREND_REFUSED_AUDIO")  # offline: no bundled ASR
    if kind not in KINDS:
        _bad("kind")
    did = _bounded_text(d.get("id"), "id", 64)
    text = _text_field(d.get("text"), "text")
    medium = d.get("medium")
    if type(medium) is not str or medium not in MEDIA:
        _bad("medium")
    turns = d.get("turns")
    segments = d.get("segments")
    if turns is not None:
        _check_turns(turns, text)
    if segments is not None:
        _check_segments(segments, text)

    spans, unmatched = _quotes(text)
    sentences = _sentences(text)
    hits = {k: 0 for k in MOVE_NAMES}
    sws = {k: 0 for k in MOVE_NAMES}
    evidence = {k: [] for k in MOVE_NAMES}
    excluded = {"negated": 0, "quoted": 0}
    chains = []
    cue_events = []  # (char position, move) of surviving cues, for turns/segments
    words_total = 0
    for sidx, (a, b) in enumerate(sentences):
        sent = text[a:b]
        found = [(m.start(), m.group().lower()) for m in _WORD.finditer(sent)]
        words = [w for _, w in found]
        words_total += len(words)
        occ = []
        for mv in MOVE_NAMES:
            for cw in _CUE_WORDS[mv]:
                n = len(cw)
                for i in range(len(words) - n + 1):
                    if tuple(words[i:i + n]) != cw:
                        continue
                    pos = a + found[i][0]
                    if _in_span(pos, spans):
                        excluded["quoted"] += 1
                    elif any(w in _NEG or w.endswith("n't") for w in words[max(0, i - _NEG_WINDOW):i]):
                        excluded["negated"] += 1
                    else:
                        occ.append((i, mv, pos))
        if not occ:
            continue
        occ.sort()
        order = []
        for i, mv, pos in occ:
            hits[mv] += 1
            cue_events.append((pos, mv))
            if mv not in order:
                order.append(mv)
        for mv in order:
            sws[mv] += 1
            if len(evidence[mv]) < MAX_EVIDENCE:
                evidence[mv].append({"doc": did, "offset": a, "sentence": sent})
        chains.append({"sentence": sidx, "offset": a, "moves": order})

    transitions = {}

    def link(x, y):
        transitions.setdefault(x, {})
        transitions[x][y] = transitions[x].get(y, 0) + 1

    for c in chains:
        for x, y in zip(c["moves"], c["moves"][1:]):
            link(x, y)
    for c, nxt in zip(chains, chains[1:]):
        link(c["moves"][-1], nxt["moves"][0])
    longest = run_len = prev_idx = 0
    for c in chains:
        run_len = run_len + 1 if prev_idx is not None and c["sentence"] == prev_idx + 1 and run_len else 1
        prev_idx = c["sentence"]
        longest = max(longest, run_len)

    out = {"id": did, "kind": kind, "medium": medium, "word_count": words_total,
           "sentence_count": len(sentences),
           "moves": {k: {"hits": hits[k], "sentences_with_move": sws[k],
                         "per_1000_words": _rate(hits[k], words_total)} for k in MOVE_NAMES},
           "move_total": sum(hits.values()), "evidence": evidence, "chains": chains,
           "transitions": transitions, "longest_run": longest, "excluded_hits": excluded,
           "unmatched_quote_marks": unmatched,
           "legacy_comparison": _legacy_counts(text)}

    def attribute(parts):
        starts, acc = [], 0
        for p in parts:
            starts.append(acc)
            acc += len(p)
        per = [dict() for _ in parts]
        for pos, mv in cue_events:
            k = bisect.bisect_right(starts, pos) - 1
            per[k][mv] = per[k].get(mv, 0) + 1
        return per

    if turns is not None:
        per = attribute([t["text"] for t in turns])
        out["turns"] = []
        speakers = {}
        for t, mv in zip(turns, per):
            sp = t["speaker"].strip()
            row = {"speaker": sp, "moves": mv}
            if t.get("t_start") is not None:
                row["t_start"] = t["t_start"]
            out["turns"].append(row)
            tot = speakers.setdefault(sp, {})
            for k, v in mv.items():
                tot[k] = tot.get(k, 0) + v
        out["speakers"] = speakers
    if segments is not None:
        per = attribute([s["text"] for s in segments])
        out["segments"] = [{"label": s["label"], "moves": mv} for s, mv in zip(segments, per)]
    return out


def run(request):
    """Analyze supplied docs; returns per-doc evidence, chains, rates and the honesty blocks."""
    docs_in = _preflight(request)
    docs = [_analyze_doc(d) for d in docs_in]
    docs.sort(key=lambda d: (-d["move_total"], d["id"]))
    totals = {k: 0 for k in MOVE_NAMES}
    excluded = {"negated": 0, "quoted": 0}
    unmatched = words = 0
    transitions = {}
    groups = {"by_kind": {}, "by_medium": {}}
    for d in docs:
        words += d["word_count"]
        unmatched += d["unmatched_quote_marks"]
        for k in excluded:
            excluded[k] += d["excluded_hits"][k]
        for k in MOVE_NAMES:
            totals[k] += d["moves"][k]["hits"]
        for x, row in d["transitions"].items():
            for y, n in row.items():
                transitions.setdefault(x, {})
                transitions[x][y] = transitions[x].get(y, 0) + n
        for gname, key in (("by_kind", d["kind"]), ("by_medium", d["medium"])):
            g = groups[gname].setdefault(key, {"docs": 0, "word_count": 0, "moves": {k: {"hits": 0} for k in MOVE_NAMES}})
            g["docs"] += 1
            g["word_count"] += d["word_count"]
            for k in MOVE_NAMES:
                g["moves"][k]["hits"] += d["moves"][k]["hits"]
    for g in (x for grp in groups.values() for x in grp.values()):
        for k in MOVE_NAMES:
            g["moves"][k]["per_1000_words"] = _rate(g["moves"][k]["hits"], g["word_count"])
    media = sorted({d["medium"] for d in docs})
    caveat = REPORT_CAVEAT_TEMPLATE.replace("{media}", ", ".join(media))
    return {"docs": docs, "doc_count": len(docs), "word_count": words, "move_totals": totals,
            "excluded_hits": excluded, "unmatched_quote_marks": unmatched, "transitions": transitions,
            "by_kind": groups["by_kind"], "by_medium": groups["by_medium"], "media": media,
            "report_caveat": caveat,
            "validity": {"metric_name": VALIDITY_METRIC_NAME, "labels": "synthetic, builder-written",
                         "fixture_file": FIXTURE_FILE, "fixture_sentences": FIXTURE_SENTENCES,
                         "per_move": copy.deepcopy(FIXTURE_AGREEMENT), "caveat": caveat},
            "scope": policy.scope(
                ["reasoning-move cue tagging with evidence spans over supplied transcripts/text/lyrics",
                 "per-1000-word normalization by kind and medium",
                 "sentence-based move chains and transitions",
                 "speaker turns and chapter segments, negation and quote exclusion"],
                ["audio transcription (no bundled ASR offline)", "all forms of media",
                 "validation of human thinking"],
                "supplied transcripts/text/lyrics")}


analyze_v2 = run
