import sys, json, time, signal, multiprocessing as mp
from lh_tasks import Project
from lh_agents import run_agent
AS = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "0,1").split(",")]
KINDS = ["S_uniform", "S_fl", "M", "M_noslow", "M_nomed"]
def job(a):
    seed, k, kind, aseed = a
    P = Project(seed, k); t = time.time(); r = run_agent(P, kind, aseed, maxb=1000)
    r.update(seed=seed, k=k, kind=kind, aseed=aseed, secs=time.time() - t, nedits=len(P.edit_space())); return r
if __name__ == "__main__":
    split = sys.argv[1]; kinds = sys.argv[2].split(",") if len(sys.argv) > 2 else KINDS
    if split == "dev": seeds = [(s, 3) for s in range(20)]
    elif split == "test": seeds = [(1000 + i, 1 + i % 3) for i in range(48)]
    else: seeds = [(s, 3) for s in range(3)]
    if split == "test2": seeds = [(2000 + i, 1 + i % 3) for i in range(48)]
    jobs = [(s, k, kd, a) for (s, k) in seeds for kd in kinds for a in AS]
    t = time.time()
    out = sys.argv[4] if len(sys.argv) > 4 else f"rows_{split}.jsonl"  # opened with "w": replaces, never appends
    with mp.Pool(2) as p, open(out, "w") as fo:
        for r in p.imap_unordered(job, jobs, chunksize=1): fo.write(json.dumps(r) + "\n"); fo.flush()
    print("secs", time.time() - t)
