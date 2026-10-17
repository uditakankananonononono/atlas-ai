import os, sys
sys.path.insert(0, os.environ["M19_TREE"])
os.environ.setdefault("ATLAS_AUTO_CREATE_SCHEMA", "1")
for f in ("/tmp/m19/ua_probe.db",):
    if os.path.exists(f): os.remove(f)
os.environ["ATLAS_DATABASE_URL"] = "sqlite:////tmp/m19/ua_probe.db"
import json
from app.modules.m19_idea_incubator.service import Service, Stage
from app.modules.m19_idea_incubator.schemas import IntakeIn, PreviewIn
from app.modules.m19_idea_incubator.run_store import SqlRunStore
CANVAS = {"problem": ["p"], "customer_segments": ["c"], "unique_value_proposition": "u", "solution": ["s"], "channels": ["ch"], "revenue_streams": ["r"], "cost_structure": ["c"], "key_metrics": ["k"], "unfair_advantage": None, "riskiest_assumptions": ["a"]}
async def fg(p, pr, m): return ("", json.dumps(CANVAS))
class FlakyApprovals:
    def put(self, item): raise ConnectionError("approval store outcome unknown")
import asyncio
svc = Service(generate=fg, approval_store=FlakyApprovals(), run_store=SqlRunStore())
async def main():
    run = await svc.intake(IntakeIn(one_liner="unknown approval probe", budget_cap=50), "tenant-a")
    try:
        await svc.request_preview(run.id, PreviewIn(artifacts=["a"], estimated_cost=7), "tenant-a")
        print("FAIL: preview unexpectedly succeeded")
        return None
    except ConnectionError:
        return run.id
run_id = asyncio.run(main())
store = svc._store
got = store.get("tenant-a", run_id)
res = got.reserved if got else None
print("run state after unknown approval:", got.state if got else None)
print("reserved after unknown approval:", res)
print("PROBE", "PASS reservation kept" if res == 7 else f"FAIL reserved={res}")
