"""E1: journal retrieval, shipped lexical ranking vs supersession + recency.

Synthetic, seeded. 5 seeds x 100 queries. Usage: python run_experiment.py [out_dir]
"""
import json
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rankers as R  # noqa: E402
from sqlalchemy import create_engine, update  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

NOUNS = ["catering", "venue", "printer", "laptop", "insurance", "hosting", "courier", "storage", "payroll",
         "legal", "design", "travel", "security", "cleaning", "internet", "furniture"]
QUALS = ["office", "event", "backup", "annual", "emergency", "remote", "retail", "premium", "student", "pilot"]
VENDORS = ["Acme", "Birch", "Cobalt", "Dunmore", "Ember", "Fjord", "Garnet", "Halcyon", "Ironwood", "Juniper",
           "Kestrel", "Lumen", "Marlow", "Nimbus", "Orchid", "Pinnacle", "Quill", "Rowan", "Sable", "Tundra"]
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
K = 3


def build(seed):
    rnd = random.Random(seed)
    engine = create_engine("sqlite://")
    sessions = sessionmaker(bind=engine)
    j = R.pj.PersistentJournal("t", "a", sessions)
    queries = []  # (query, truth_text, stale_texts, kind)
    dated = []  # (id, age_days)

    def dec(topic, vendor, age):
        n, q = topic
        text = f"Use {vendor} for {q} {n}"
        out = j.capture(text, f"{vendor} fit the {q} {n} budget", f"owner chose after comparing {n} options", "owner:chat")
        dated.append((out["id"], age))
        return text, out

    plan = ["S1"] * 40 + ["S2"] * 30 + ["S3"] * 30
    rnd.shuffle(plan)
    pool = [(n, q) for n in NOUNS for q in QUALS]
    rnd.shuffle(pool)
    # distractors: topics NOT used by any target (so no same-topic confound); they share words with targets
    for n, q in pool[100:]:
        dec((n, q), rnd.choice(VENDORS), rnd.randint(1, 365))
    for kind, topic in zip(plan, pool):
        n, q = topic
        phr = f"which {q} {n} vendor did I pick"
        v1, v2 = rnd.sample(VENDORS, 2)
        if kind == "S1":
            t, _ = dec(topic, v1, rnd.randint(1, 365))
            queries.append((phr, t, [], kind))
        elif kind == "S2":
            age = rnd.randint(60, 365)
            t, out = dec(topic, v1, age)
            corrected = f"Use {v2} for {q} {n}"
            c = j.correction(t, corrected, f"owner corrected the {q} {n} choice", "owner:chat")
            dated.append((c["id"], rnd.randint(1, age - 1)))
            queries.append((phr, corrected, [t], kind))
        else:
            old_age = rnd.randint(150, 365)
            new_age = rnd.randint(1, 60)
            t_old, _ = dec(topic, v1, old_age)
            t_new, _ = dec(topic, v2, new_age)
            queries.append((phr, t_new, [t_old], kind))
    with sessions.begin() as db:
        for rid, age in dated:
            db.execute(update(R.pj.JournalEntry).where(R.pj.JournalEntry.id == rid)
                       .values(created_at=NOW - timedelta(days=age)))
    return j, queries


def evaluate(seed):
    j, queries = build(seed)
    res = {}
    for name, fn in R.RANKERS.items():
        by = {"S1": [], "S2": [], "S3": []}
        for q, truth, stale, kind in queries:
            top = fn(j, q, K, NOW)
            hit = truth in top
            rr = 1 / (top.index(truth) + 1) if hit else 0.0
            st = any(s in top and (not hit or top.index(s) < top.index(truth)) for s in stale)
            by[kind].append((hit, rr, st, bool(top) and top[0] == truth))
        res[name] = {k: dict(n=len(v), hit3=sum(x[0] for x in v) / len(v), mrr=sum(x[1] for x in v) / len(v),
                             stale_above=sum(x[2] for x in v) / len(v), top1=sum(x[3] for x in v) / len(v)) for k, v in by.items()}
    return res


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    seeds = [11, 12, 13, 14, 15]
    allres = {s: evaluate(s) for s in seeds}
    agg = {}
    for name in R.RANKERS:
        agg[name] = {}
        for kind in ("S1", "S2", "S3"):
            for m in ("hit3", "mrr", "top1", "stale_above"):
                xs = [allres[s][name][kind][m] for s in seeds]
                agg[name][f"{kind}.{m}"] = (round(statistics.mean(xs), 3), round(statistics.pstdev(xs), 3))
    (out / "results.json").write_text(json.dumps(dict(seeds=seeds, k=K, per_seed=allres, aggregate=agg), indent=1))
    for name, a in agg.items():
        print(name, {k: v[0] for k, v in a.items()})


if __name__ == "__main__":
    main()
