"""Helper run as a separate OS process by test_m21_meemee_adapter_procs.py."""
import asyncio, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from app.core.approvals import ApprovalStore
from app.core.models import ApprovalRequest, ApprovalStatus
from app.modules.m21_claire.meemee_local_client import MeemeeLocalClient
from meemee.devices import DeviceRegistry
from meemee.device_simulator import StatefulDeviceSimulator

d, mode = sys.argv[1], sys.argv[2]
meta_p = os.path.join(d, "meta.json")
reg = DeviceRegistry(__import__("pathlib").Path(d) / "m.db")
ap = ApprovalStore()

def effect(state, cmd):
    with open(os.path.join(d, "effects.log"), "a") as f:
        f.write(cmd + "\n")
    time.sleep(0.2)
    return {"ran": cmd}

def client():
    m = json.load(open(meta_p))
    sim = StatefulDeviceSimulator("dev1", m["secret"], {"run_command": effect})
    crash = os.environ.get("ADAPTER_CRASH_AT")
    def hook(point):
        if point == crash:
            os._exit(137)  # real process death, no cleanup
    return MeemeeLocalClient(reg, "tenant-a", "dev1", sim.execute, ap, os.path.join(d, "m.db"), fault_hook=hook)

async def main():
    if mode == "setup":
        p = reg.create_pairing("tenant-a")
        paired = reg.pair(p["pairing_id"], p["code"], device_id="dev1", name="pc", capabilities={"run_command": {}})
        json.dump({"secret": paired["secret"]}, open(meta_p, "w"))
        cl = client()
        a = {"id": "a1", "kind": "run_command", "arguments": {"cmd": "ls"}, "idempotency_key": "k1"}
        pv = await cl.preview(a)
        r = ap.put(ApprovalRequest(id="x", module_id=21, action_type="claire:run_command", payload={"tenant_id": "tenant-a", "preview": pv}), user_id="tenant-a")
        if os.environ.get("ALSO_Z"):
            rz = ap.put(ApprovalRequest(id="x", module_id=21, action_type="claire:run_command", payload={"tenant_id": "tenant-z", "preview": pv}), user_id="tenant-z")
            ap.decide(rz.id, ApprovalStatus.APPROVED, user_id="tenant-z")
            m0 = json.load(open(meta_p)); m0["approval_z"] = rz.id; json.dump(m0, open(meta_p, "w"))
        ap.decide(r.id, ApprovalStatus.APPROVED, user_id="tenant-a")
        m = json.load(open(meta_p)); m["approval"] = r.id; json.dump(m, open(meta_p, "w"))
        print(r.id)
    else:
        key, cmd = sys.argv[3], sys.argv[4]
        a = {"id": "a1", "kind": "run_command", "arguments": {"cmd": cmd}, "idempotency_key": key}
        try:
            tok = None if os.environ.get("NO_TOKEN") else json.load(open(meta_p))["approval"]
            out = await client().execute(a, tok)
            print(json.dumps({"ok": True, "replayed": out["replayed"], "status": out["status"], "outcome": out.get("outcome")}))
        except Exception as e:
            print(json.dumps({"ok": False, "err": f"{type(e).__name__}: {e}"}))
asyncio.run(main())
