"""Group 73: asyncio fleet dispatcher that really runs N jobs in flight at once.

run() launches every job as an asyncio task, gated by a semaphore of
`concurrency`; it MEASURES peak in-flight count and wall time. The report
sets simultaneous_1000_achieved only when measured peak >= 1000. These are
in-process tasks, not 1,000 independent builder agents/accounts - that is
stated in the report scope.
"""
from __future__ import annotations
import asyncio, time

FLEET_SIZE = 1000


async def _run(jobs, worker, concurrency, budget):
    sem = asyncio.Semaphore(concurrency)
    state = {"inflight": 0, "peak": 0, "spent": 0}
    results = {}
    state["target"] = min(concurrency, len(jobs))
    started = asyncio.Event()

    async def one(job):
        async with sem:
            if state["spent"] + job["cost"] > budget:
                results[job["id"]] = {"status": "skipped_budget"}
                state["target"] -= 1
                if state["inflight"] >= state["target"] > 0:
                    started.set()
                return
            state["spent"] += job["cost"]
            state["inflight"] += 1
            state["peak"] = max(state["peak"], state["inflight"])
            if state["inflight"] >= state["target"]:
                started.set()
            try:
                # hold until the full cohort is in flight, proving simultaneity
                await asyncio.wait_for(started.wait(), 30)
                results[job["id"]] = {"status": "ok", "value": await worker(job)}
            except Exception as e:
                results[job["id"]] = {"status": "error", "error": "%s: %s" % (type(e).__name__, e)}
            finally:
                state["inflight"] -= 1
    t0 = time.perf_counter()
    await asyncio.gather(*(one(j) for j in jobs))
    return results, state, time.perf_counter() - t0


def run(jobs, worker, concurrency=FLEET_SIZE, budget=10**9):
    if not isinstance(jobs, list) or not jobs or len(jobs) > FLEET_SIZE:
        raise ValueError("FLEET_REFUSED_JOBS")
    ids = [j.get("id") for j in jobs]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("FLEET_REFUSED_IDS")
    jobs = [{"id": j["id"], "cost": int(j.get("cost", 1)), **{k: v for k, v in j.items() if k not in ("id", "cost")}} for j in jobs]
    if not isinstance(concurrency, int) or concurrency < 1:
        raise ValueError("FLEET_REFUSED_CONCURRENCY")
    results, st, secs = asyncio.run(_run(jobs, worker, concurrency, budget))
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    return {"jobs": len(jobs), "ok": ok, "errors": sum(1 for r in results.values() if r["status"] == "error"),
            "skipped_budget": sum(1 for r in results.values() if r["status"] == "skipped_budget"),
            "peak_inflight_measured": st["peak"], "spent": st["spent"], "seconds": round(secs, 3),
            "simultaneous_1000_achieved": st["peak"] >= FLEET_SIZE and ok == len(jobs),
            "results": results,
            "scope": {"implemented": ["measured in-process simultaneous dispatch", "budget cap"],
                      "not_implemented": ["1,000 independent builder agents or accounts",
                                          "cross-machine workers"]}}
