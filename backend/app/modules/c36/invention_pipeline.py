"""c36.invention_pipeline (doc row 106): literature -> cross-domain concept
graph -> product/algorithm invention briefs, with full provenance.

Closes the audit gap on m25.pipeline/c36.concepts ("finite local ingestion and
supplied concept graph; universal knowledge coverage/invention unverified"):
an end-to-end pipeline over a SUPPLIED corpus that extracts concepts per
document, builds a co-occurrence graph, finds CROSS-DOCUMENT concept pairs,
and emits ranked invention briefs (product or algorithm hypotheses) where
every claim traces to document ids and character spans.

Honest bounds, reported every run: the corpus is exactly what was supplied
(coverage counts included); briefs are hypotheses for owner review, not
verified inventions; no code is generated or executed. Stdlib only, offline,
deterministic.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from app.modules.c30 import policy

PREFIX = "INVENT"
MAX_DOCS = 1000
MAX_DOC_CHARS = 200000
MAX_CONCEPTS_PER_DOC = 40
MAX_BRIEFS = 100

_WORD = re.compile(r"[A-Za-z][a-z]{3,}")
_PHRASE = re.compile(r"\b[A-Z][a-z]{3,}(?: [A-Z][a-z]{2,}){1,2}\b")
_STOP = frozenset((
    "this that with from have been were will would could should their there these "
    "those which when where what into about over under more most other some such "
    "only also than then them they your yours ours each very just like make made "
    "many much between through during before after above below both same while "
    "because until against within without upon toward towards among along across").split())

LIMITS = (
    "Corpus is exactly the supplied documents; coverage counts are reported, "
    "never implied universal.",
    "Briefs are hypotheses for owner review; nothing is prototyped, tested or "
    "validated by this unit.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _concepts(doc):
    text = doc["text"]
    counts = Counter(w.lower() for w in _WORD.findall(text))
    terms = [(w, c) for w, c in counts.items() if w not in _STOP and c >= 2]
    terms.sort(key=lambda x: (-x[1], x[0]))
    concepts = []
    seen = set()
    for w, c in terms[:MAX_CONCEPTS_PER_DOC]:
        idx = text.lower().find(w)
        concepts.append({"concept": w, "kind": "term", "frequency": c,
                         "span": {"doc": doc["id"], "start": idx, "end": idx + len(w)}})
        seen.add(w)
    for m in _PHRASE.finditer(text):
        phrase = m.group(0)
        key = phrase.lower()
        if key in seen or len(concepts) >= MAX_CONCEPTS_PER_DOC:
            continue
        concepts.append({"concept": phrase, "kind": "phrase", "frequency": 1,
                         "span": {"doc": doc["id"], "start": m.start(), "end": m.end()}})
        seen.add(key)
    return concepts


def run(body):
    """body = {"as_of", "documents": [{"id","title","text","source_url"?}],
    "max_briefs"?}. Returns the concept graph, coverage and ranked briefs."""
    if isinstance(body, bool) or not isinstance(body, dict) \
            or not {"as_of", "documents"} <= set(body):
        raise ValueError("%s_REFUSED_BAD_TYPE:body" % PREFIX)
    docs = body["documents"]
    if isinstance(docs, bool) or not isinstance(docs, (list, tuple)) \
            or not docs or len(docs) > MAX_DOCS:
        raise ValueError("%s_REFUSED_BAD_TYPE:documents" % PREFIX)
    max_briefs = body.get("max_briefs", 20)
    if isinstance(max_briefs, bool) or not isinstance(max_briefs, int) \
            or not 1 <= max_briefs <= MAX_BRIEFS:
        raise ValueError("%s_REFUSED_BAD_TYPE:max_briefs" % PREFIX)
    parsed = []
    for d in docs:
        if not isinstance(d, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:document" % PREFIX)
        did = policy.clean_text(d.get("id"), PREFIX, "doc.id", 64)
        title = policy.clean_text(d.get("title"), PREFIX, "doc.title", 300)
        text = policy.clean_text(d.get("text"), PREFIX, "doc.text", MAX_DOC_CHARS,
                                 allow_ws=True)
        parsed.append({"id": did, "title": title, "text": text,
                       "source_url": d.get("source_url")})
    per_doc = {d["id"]: _concepts(d) for d in parsed}
    df = Counter()
    edges = Counter()
    for did, concepts in per_doc.items():
        keys = sorted({c["concept"].lower() for c in concepts})
        for k in keys:
            df[k] += 1
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                edges[(keys[i], keys[j])] += 1
    spans = {}
    for did, concepts in per_doc.items():
        for c in concepts:
            spans.setdefault(c["concept"].lower(), []).append(c["span"])
    pairs = []
    concept_list = sorted(df)
    for i in range(len(concept_list)):
        for j in range(i + 1, len(concept_list)):
            a, b = concept_list[i], concept_list[j]
            shared = edges.get((a, b), 0)
            support = df[a] + df[b] - shared
            if df[a] >= 1 and df[b] >= 1:
                pairs.append({"a": a, "b": b, "co_occurrences": shared,
                              "document_support": support,
                              "cross_document": spans.get(a, [{}])[0].get("doc")
                              != spans.get(b, [{}])[0].get("doc")})
    pairs.sort(key=lambda p: (-p["cross_document"], -p["document_support"], p["a"], p["b"]))
    briefs = []
    for rank, p in enumerate([x for x in pairs if x["cross_document"]][:max_briefs]):
        bid = "inv-" + hashlib.sha256(json.dumps([p["a"], p["b"]]).encode()).hexdigest()[:10]
        briefs.append({
            "id": bid, "rank": rank + 1,
            "title": "Product hypothesis: %s x %s" % (p["a"], p["b"]),
            "combines": [p["a"], p["b"]],
            "rationale": ("Both concepts carry independent document support (%d docs "
                          "combined) and their intersection is underexplored in the "
                          "supplied corpus (%d shared docs)." % (p["document_support"],
                                                                 p["co_occurrences"])),
            "provenance": {"spans": {p["a"]: spans[p["a"]][:3], p["b"]: spans[p["b"]][:3]},
                           "documents": sorted({s["doc"] for s in
                                                spans[p["a"]] + spans[p["b"]]})},
            "document_support": p["document_support"],
            "status": "hypothesis_for_owner_review",
        })
    return {
        "as_of": body["as_of"],
        "coverage": {"documents_supplied": len(parsed),
                     "concepts_extracted": sum(len(v) for v in per_doc.values()),
                     "distinct_concepts": len(df),
                     "graph_edges": len(edges),
                     "briefs_emitted": len(briefs),
                     "universal_coverage": False},
        "concept_graph": {"nodes": len(df), "edges": len(edges)},
        "briefs": briefs,
        "limits": list(LIMITS),
        "scope": policy.scope(["concept-extraction", "co-occurrence-graph",
                               "cross-document-invention-briefs", "full-provenance"],
                              ["universal-knowledge", "validated-inventions",
                               "code-generation"],
                              "supplied-corpus", str(body["as_of"])),
    }
