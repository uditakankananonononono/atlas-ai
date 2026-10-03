"""NOTE: dev20 and test38 are LENGTH-CONFOUNDED (the longest description is always gold: control 100%), so their numbers\nprove nothing about matching quality. Use the BALANCED17 section.\nDev/test comparison for the essay-topic matcher. Selection (model, hybrid weight) uses ONLY the dev set
(esai_topic_match_dev20.json, already seen). The test set (esai_topic_match_test40.json, 38 cases) was written once
and is evaluated once with the dev-selected setting; its numbers are never used to choose anything.
Usage: python esai_embedding_eval2.py minilm-l6=http://127.0.0.1:8091/v1 bge-small=http://127.0.0.1:8092/v1
"""
import json, os, sys
from app.modules.m23_study_abroad.embedding_matcher import LocalEmbeddingMatcher
from app.modules.m23_study_abroad.essay_tools import EssayToolService

D = os.path.join(os.path.dirname(__file__), "data")
dev = json.load(open(f"{D}/esai_topic_match_dev20.json"))
test = json.load(open(f"{D}/esai_topic_match_test40.json"))
tok = EssayToolService()
ms = {a.split("=")[0]: LocalEmbeddingMatcher(a.split("=", 1)[1], a.split("=")[0]) for a in sys.argv[1:]}


def doc(e):
    return e["description"] + " " + " ".join(e.get("values", []))


def feats(cases):
    out = []
    for c in cases:
        r = tok.topic_finder(c["prompt"], c["evidence"])
        overlap = [len(x["prompt_connections"]) for x in r["candidates"]]
        row = {"gold": c["gold"], "overlap": overlap, "length": [len(e["description"].split()) for e in c["evidence"]]}
        for name, m in ms.items():
            row[name] = m.rank(c["prompt"], [doc(e) for e in c["evidence"]])
            assert row[name] is not None, f"{name} returned no embeddings"
        out.append(row)
    return out


def rank_of(scores, gold):  # ties keep input order (stable), same as the shipped token-overlap path
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return order.index(gold) + 1


def hybrid(row, name, a):
    e = row[name]; mx = max(row["overlap"]) or 1
    return [a * e[i] + (1 - a) * 0.3 * row["overlap"][i] / mx for i in range(len(e))]  # overlap term scaled to ~embedding spread


def report(label, rows, scorer):
    ranks = [rank_of(scorer(r), r["gold"]) for r in rows]
    n = len(rows)
    print(f"  {label:28s} top1={sum(x == 1 for x in ranks):2d}/{n} mrr={sum(1 / x for x in ranks) / n:.3f}")
    return sum(1 / x for x in ranks) / n


bal = json.load(open(f"{D}/esai_topic_match_balanced17.json"))
FB = feats(bal)
print("BALANCED17 (length-controlled, written after the dev/test length confound was found; evaluated once)")
report("token_overlap", FB, lambda r: r["overlap"])
report("CONTROL longest_description", FB, lambda r: r["length"])
for name in ms:
    report(name, FB, lambda r, n=name: r[n])
    for a in (0.5, 0.7, 0.85):
        report(f"{name}+overlap a={a}", FB, lambda r, n=name, a=a: hybrid(r, n, a))
