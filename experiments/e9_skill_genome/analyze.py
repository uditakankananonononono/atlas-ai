import json, random, statistics as st
d = json.load(open("results.json")); rows = d["rows"]
rnd = random.Random(0)
def ci(xs):
    bs = sorted(st.mean(rnd.choices(xs, k=len(xs))) for _ in range(5000))
    return st.mean(xs), bs[125], bs[4874]
conds = [c for c in rows[0]["conds"]]
def acc(r, c, subset=None, key="120"):
    v = r["conds"][c]["curve"][key]; meta = r["test_meta"]
    idx = [i for i, (th, rich) in enumerate(meta) if subset is None or subset(th, rich)]
    return sum(v[i] for i in idx) / len(idx)
subs = {"all": None, "seen_themes": lambda th, r: th < 7, "novel_themes": lambda th, r: th >= 7,
        "poor_examples": lambda th, r: not r, "rich_examples": lambda th, r: r}
out = [f"n_seeds={len(rows)} budget={d['budget']}"]
for sn, f in subs.items():
    out.append(f"\n[test solved-rate, {sn}] mean [95% bootstrap CI over seeds]")
    for c in conds:
        m, lo, hi = ci([acc(r, c, f) for r in rows])
        out.append(f"  {c:24s} {m:.3f} [{lo:.3f}, {hi:.3f}]")
out.append("\n[paired difference vs nolib / admit_all, all test tasks]")
for a, b in [("gated", "nolib"), ("admit_all", "nolib"), ("gated", "admit_all"), ("gated_margin1_posthoc", "admit_all"),
             ("gated", "random_lib_same_size"), ("gated", "gated_induced_only"), ("gated_margin1_posthoc", "gated")]:
    diffs = [acc(r, a) - acc(r, b) for r in rows]
    m, lo, hi = ci(diffs)
    out.append(f"  {a} - {b}: {m:+.3f} [{lo:+.3f}, {hi:+.3f}]  wins/ties/losses={sum(x>0 for x in diffs)}/{sum(x==0 for x in diffs)}/{sum(x<0 for x in diffs)}")
out.append("\n[learning curve, all test tasks, mean solved-rate at acquisition tasks seen]")
for c in conds:
    if c == "random_lib_same_size": continue
    out.append(f"  {c:24s} " + "  ".join(f"{k}:{st.mean(acc(r,c,None,k) for r in rows):.3f}" for k in ("0", "60", "120")))
out.append("\n[library composition at end, mean per seed]")
for c in conds:
    if c == "random_lib_same_size": continue
    sz = st.mean(r["conds"][c]["lib_size"] for r in rows); al = st.mean(r["conds"][c]["lib_theme_aligned"] for r in rows)
    og = {o: st.mean(r["conds"][c]["lib_origins"][o] for r in rows) for o in ("induced", "rewritten", "combined")}
    out.append(f"  {c:24s} size={sz:.1f} theme_aligned={al:.1f} ({(al/sz if sz else 0):.0%}) origins={og}")
out.append("\n[candidate decisions pooled over seeds, gated]")
from collections import Counter
cc = Counter(); own_ok_not_admitted = 0
for r in rows:
    for x in r["conds"]["gated"]["decisions"]:
        cc[(x["origin"], x["decision"])] += 1
for k, v in sorted(cc.items()): out.append(f"  {k}: {v}")
# failure-case regression at scale: candidates that pass own tests, and fraction not theme-aligned among admit_all admits
from run_experiment import theme_aligned
na = al_ = 0
for r in rows:
    for p in r["conds"]["admit_all"]["lib_programs"]:
        if theme_aligned(tuple(p)): al_ += 1
        else: na += 1
out.append(f"\n[admit_all admitted skills: all passed own tests by construction] theme_aligned={al_} not_theme_aligned={na}")
g_na = sum(1 for r in rows for p in r["conds"]["gated"]["lib_programs"] if not theme_aligned(tuple(p)))
g_al = sum(1 for r in rows for p in r["conds"]["gated"]["lib_programs"] if theme_aligned(tuple(p)))
out.append(f"[gated admitted skills] theme_aligned={g_al} not_theme_aligned={g_na}")
open("analysis.txt", "w").write("\n".join(out)); print("\n".join(out))
