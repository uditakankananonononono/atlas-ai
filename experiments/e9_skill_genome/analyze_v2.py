import json, random, statistics as st, glob, sys
from collections import Counter
def ci(xs):
    rnd = random.Random(0)   # fresh per call: output independent of call order
    if len(xs) < 2: return (xs[0], float("nan"), float("nan"))
    bs = sorted(st.mean(rnd.choices(xs, k=len(xs))) for _ in range(5000))
    return st.mean(xs), bs[125], bs[4874]
def acc(r, c, cat=None, key="120"):
    v = r["conds"][c]["curve"][key]
    idx = [i for i, k in enumerate(r["test_cat"]) if cat is None or k == cat]
    return sum(v[i] for i in idx) / len(idx)
out = []
for path in sorted(glob.glob("results_v2_B*.json"), key=lambda p: int(p.split("_B")[1].split(".")[0])):
    d = json.load(open(path)); rows = d["rows"]; conds = list(rows[0]["conds"])
    cats = list(dict.fromkeys(rows[0]["test_cat"]))
    out.append(f"\n=== budget {d['budget']}  seeds={len(rows)}  test tasks/seed={rows[0]['n_test']} (20 per category), validation {rows[0]['n_val']} ===")
    out.append("test solved-rate mean [95% CI over seeds]:")
    out.append(f"  {'cond':22s} {'all':>22s} " + " ".join(f"{c:>26s}" for c in cats))
    for c in conds:
        m, lo, hi = ci([acc(r, c) for r in rows])
        out.append(f"  {c:22s} {m:.3f} [{lo:.3f},{hi:.3f}] " + " ".join(f"{st.mean(acc(r,c,k) for r in rows):26.3f}" for k in cats))
    out.append("paired differences, all test tasks (mean [CI], seed wins/ties/losses):")
    pairs = [("admit_all","nolib"),("gated","nolib"),("joint_audit","nolib"),("gated","admit_all"),("joint_audit","admit_all"),
             ("joint_audit","gated"),("gated_audit","gated"),("joint_audit","random_lib_same_size"),("gated","random_lib_same_size")]
    for a, b in pairs:
        if a not in conds or b not in conds: continue
        if b == "random_lib_same_size" and rows[0]["conds"][b].get("matched_to") not in (None, a): continue
        diffs = [acc(r, a) - acc(r, b) for r in rows]; m, lo, hi = ci(diffs)
        out.append(f"  {a} - {b}: {m:+.3f} [{lo:+.3f},{hi:+.3f}] {sum(x>0 for x in diffs)}/{sum(x==0 for x in diffs)}/{sum(x<0 for x in diffs)}")
    out.append("novel_theme paired differences vs nolib (does a library hurt tasks outside its themes?):")
    for a in conds:
        if a in ("nolib", "random_lib_same_size") or "lib_size" not in rows[0]["conds"][a]: continue
        diffs = [acc(r, a, "novel_theme") - acc(r, "nolib", "novel_theme") for r in rows]; m, lo, hi = ci(diffs)
        out.append(f"  {a} - nolib: {m:+.3f} [{lo:+.3f},{hi:+.3f}] {sum(x>0 for x in diffs)}/{sum(x==0 for x in diffs)}/{sum(x<0 for x in diffs)}")
    out.append("library at end (mean): " + "; ".join(
        f"{c} size={st.mean(r['conds'][c]['lib_size'] for r in rows):.1f} aligned={st.mean(r['conds'][c].get('lib_theme_aligned',0) for r in rows):.1f} retired={st.mean(len(r['conds'][c].get('retired',[])) for r in rows):.2f}"
        for c in conds if "lib_theme_aligned" in rows[0]["conds"][c]))
    if "joint_audit" in conds:
        cc = Counter(x["decision"] for r in rows for x in r["conds"]["joint_audit"]["decisions"] if x["task"] == "joint")
        out.append(f"joint rounds: {dict(cc)}")
    if "gated" in conds:
        cc = Counter(x["decision"] for r in rows for x in r["conds"]["gated"]["decisions"])
        out.append(f"gated candidate decisions: {dict(cc)}")
    if "0" in rows[0]["conds"]["admit_all"]["curve"] and "60" in rows[0]["conds"]["admit_all"]["curve"]:
        out.append("curve (all, after 0/60/120): " + "; ".join(
            f"{c}: " + "/".join(f"{st.mean(acc(r,c,None,k) for r in rows):.3f}" for k in ("0","60","120")) for c in conds if len(rows[0]['conds'][c]['curve'])==3))
open("analysis_v2.txt", "w").write("\n".join(out)); print("\n".join(out))

# ablation report (separate results file)
import os
if os.path.exists("results_v2_abl_B1500.json"):
    d = json.load(open("results_v2_abl_B1500.json")); rows = d["rows"]
    o = ["ablation, budget 1500, %d seeds (all test tasks)" % len(rows)]
    for c in ("gated", "gated_no_rewrite", "gated_no_combine"):
        m, lo, hi = ci([acc(r, c) for r in rows])
        o.append(f"  {c:18s} {m:.3f} [{lo:.3f},{hi:.3f}] size={st.mean(r['conds'][c]['lib_size'] for r in rows):.1f}")
    for a in ("gated_no_rewrite", "gated_no_combine"):
        x = [acc(r, "gated") - acc(r, a) for r in rows]; m, lo, hi = ci(x)
        o.append(f"  gated - {a}: {m:+.3f} [{lo:+.3f},{hi:+.3f}] {sum(v>0 for v in x)}/{sum(v==0 for v in x)}/{sum(v<0 for v in x)}")
    open("analysis_v2_ablation.txt", "w").write("\n".join(o)); print("\n".join(o))
