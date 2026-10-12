"""Group 73: asyncio fleet dispatcher with a counted peak of concurrently
executing workers.

run() launches every job as an asyncio task gated by a semaphore of
`concurrency`. A counter goes up when a worker coroutine starts and down when
it finishes, so peak_inflight_measured is the peak number of workers
executing at once (workers must await for overlap to show). The report sets
simultaneous_1000_achieved only from that counter. These are in-process
tasks, not 1,000 independent builder agents or accounts.
"""
from __future__ import annotations
import asyncio, time

FLEET_SIZE = 1000


async def _run(jobs, worker, concurrency, budget):
    sem = asyncio.Semaphore(concurrency)
    st = {"running": 0, "peak": 0, "spent": 0}
    results = {}

    async def one(job):
        async with sem:
            if st["spent"] + job["cost"] > budget:
                results[job["id"]] = {"status": "skipped_budget"}
                return
            st["spent"] += job["cost"]
            st["running"] += 1
            st["peak"] = max(st["peak"], st["running"])
            try:
                results[job["id"]] = {"status": "ok", "value": await worker(job)}
            except Exception as e:
                results[job["id"]] = {"status": "error", "error": "%s: %s" % (type(e).__name__, e)}
            finally:
                st["running"] -= 1
    t0 = time.perf_counter()
    await asyncio.gather(*(one(j) for j in jobs))
    return results, st, time.perf_counter() - t0


def run(jobs, worker, concurrency=FLEET_SIZE, budget=10**9):
    if not isinstance(jobs, list) or not jobs or len(jobs) > FLEET_SIZE:
        raise ValueError("FLEET_REFUSED_JOBS")
    ids = [j.get("id") for j in jobs]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("FLEET_REFUSED_IDS")
    clean = []
    for j in jobs:
        cost = j.get("cost", 1)
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise ValueError("FLEET_REFUSED_COST:%s" % j["id"])
        clean.append({**j, "cost": cost})
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise ValueError("FLEET_REFUSED_CONCURRENCY")
    results, st, secs = asyncio.run(_run(clean, worker, concurrency, budget))
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    return {"jobs": len(clean), "ok": ok,
            "errors": sum(1 for r in results.values() if r["status"] == "error"),
            "skipped_budget": sum(1 for r in results.values() if r["status"] == "skipped_budget"),
            "peak_inflight_measured": st["peak"], "spent": st["spent"], "seconds": round(secs, 3),
            "simultaneous_1000_achieved": st["peak"] >= FLEET_SIZE and ok == len(clean),
            "results": results,
            "scope": {"implemented": ["concurrent in-process dispatch with a running-worker counter", "budget cap"],
                      "not_implemented": ["1,000 independent builder agents or accounts",
                                          "cross-machine workers"]}}
