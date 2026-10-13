"""Re-run a few (task, budget) collections and compare to stored records bit for bit.
usage: python check_repro.py WORKDIR"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data, collect as col

work = os.path.expanduser(sys.argv[1])
C = data.build_corpus(os.path.join(work, "cache"))
tasks = data.make_tasks(C["familiar"], C["novel"])
z = np.load(os.path.join(work, "records.npz"))
ok = True
for g, role, tid0, lst in (("fam", 1, 0, tasks["fam"]), ("A", 2, 1000, tasks["A"]), ("B", 2, 2000, tasks["B"])):
    for i in (0, 7, 19):
        for b in (30, 150):
            r = col.run_one(C, lst[i], role, b, 1000 * (tid0 + i) + b)
            sel = (z[g + "_tid"] == tid0 + i) & (z[g + "_budget"] == b)
            disc = all(np.array_equal(r[k], z[g + "_" + k][sel]) for k in ("doc", "agree", "err", "model_err"))
            dF = float(np.abs(r["F"] - z[g + "_F"][sel]).max())
            same = disc and dF < 1e-12
            print(g, i, b, "discrete outputs identical:", disc, "max |dF| = %.2e" % dF)
            ok &= same
print("ALL_REPRODUCED (discrete exact, float features within 1e-12)" if ok else "SOME_DIFFERENT")
sys.exit(0 if ok else 1)
