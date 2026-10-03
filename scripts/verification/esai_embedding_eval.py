"""Held-out comparison: token-overlap topic_finder vs local-embedding topic_finder.
Dataset written once, before any run, and never tuned on. 20 cases x 4 evidence items, one gold item each.
Usage: INSTINCT_EMBED_URL=http://127.0.0.1:8091/v1 INSTINCT_EMBED_MODEL=minilm-l6 PYTHONPATH=backend python this.py
"""
import json
import os
import sys
from app.modules.m23_study_abroad.embedding_matcher import matcher_from_env
from app.modules.m23_study_abroad.essay_tools import EssayToolService

cases = json.load(open(os.path.join(os.path.dirname(__file__), "data/esai_topic_match_heldout.json")))
m = matcher_from_env()
if m is None:
    sys.exit("no loopback embedding server configured")
base, emb = EssayToolService(), EssayToolService(matcher=m)


def order_baseline(r):
    """Token-overlap ranking: most overlapping terms first, ties keep input order (stable)."""
    return [c["evidence_index"] for c in sorted(r["candidates"], key=lambda c: -len(c["prompt_connections"]))]


def order_emb(r):
    return [c["evidence_index"] for c in r["candidates"]]


res = {"token_overlap": [], "embedding": []}
modes = set()
for c in cases:
    rb, re_ = base.topic_finder(c["prompt"], c["evidence"]), emb.topic_finder(c["prompt"], c["evidence"])
    modes.add(re_["match_mode"])
    for k, o in (("token_overlap", order_baseline(rb)), ("embedding", order_emb(re_))):
        res[k].append(o.index(c["gold"]) + 1)
n = len(cases)
for k, ranks in res.items():
    print(f"{k:14s} top1={sum(r == 1 for r in ranks)}/{n} mrr={sum(1 / r for r in ranks) / n:.3f} ranks={ranks}")
print("embedding match_mode seen:", sorted(modes), "| chance top1 = 25%, mrr~0.52")
