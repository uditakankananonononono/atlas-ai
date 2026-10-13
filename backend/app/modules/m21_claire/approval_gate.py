"""Exact-payload human approval gate for consequential outbound actions.

This records authorization; it does not send messages, submit applications, post, buy,
trade, or access third-party services. The caller must re-check approval immediately
before invoking its separately implemented external adapter.

Single-use applies to issuing a permit from an approval row (atomic status flip).
It is not an execution guarantee: the permit is plain JSON and no adapter in this
package consumes or verifies it.
"""
from __future__ import annotations
import hashlib, json, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.isoformat()
def _hash(payload): return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


class ApprovalGate:
    ACTIONS={"send_email","send_message","publish_post","submit_application","create_account","spend_money","modify_production","delete_data"}
    def __init__(self, db_path: str|Path):
        self.path=str(db_path); self.lock=threading.RLock()
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS action_approvals (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, action_type TEXT NOT NULL,
                payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL, approved_by TEXT,
                approved_at TEXT, consumed_at TEXT, note TEXT NOT NULL DEFAULT '')""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_action_approval ON action_approvals(tenant_id,status,expires_at)")
    @contextmanager
    def _connect(self):
        # sqlite3.Connection's built-in context manager commits but does not close.
        # This wrapper guarantees closure while retaining transaction semantics.
        db=sqlite3.connect(self.path,timeout=15,check_same_thread=False)
        db.row_factory=sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def propose(self, tenant_id: str, action_type: str, payload: dict[str,Any], *, ttl_minutes: int=30, note: str="") -> dict[str,Any]:
        if not tenant_id.strip(): raise ValueError("tenant_id is required")
        if action_type not in self.ACTIONS: raise ValueError("action type is not approval-gated or unsupported")
        if not isinstance(payload,dict) or not payload: raise ValueError("payload must be a non-empty object")
        if not 1<=ttl_minutes<=1440: raise ValueError("ttl_minutes must be in [1,1440]")
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
        if len(raw)>100_000: raise ValueError("payload exceeds 100KB")
        now=_now(); ident=str(uuid4()); digest=_hash(payload)
        with self.lock,self._connect() as db:
            db.execute("INSERT INTO action_approvals(id,tenant_id,action_type,payload_hash,payload_json,status,created_at,expires_at,note) VALUES(?,?,?,?,?,?,?,?,?)",
                       (ident,tenant_id,action_type,digest,raw,"pending",_iso(now),_iso(now+timedelta(minutes=ttl_minutes)),note[:2000]))
        return {"id":ident,"action_type":action_type,"payload_hash":digest,"status":"pending","expires_at":_iso(now+timedelta(minutes=ttl_minutes)),
                "required_review":"Review the exact payload; approval expires and is single-use."}
    def approve(self, tenant_id: str, approval_id: str, *, actor_id: str, expected_payload_hash: str, note: str="") -> dict[str,Any]:
        if not actor_id.strip(): raise ValueError("actor_id required")
        with self.lock,self._connect() as db:
            row=db.execute("SELECT * FROM action_approvals WHERE tenant_id=? AND id=?",(tenant_id,approval_id)).fetchone()
            if row is None: raise KeyError("approval not found")
            if row["status"]!="pending": raise RuntimeError("approval is not pending")
            if _now()>=datetime.fromisoformat(row["expires_at"]):
                db.execute("UPDATE action_approvals SET status='expired' WHERE tenant_id=? AND id=? AND status='pending'",(tenant_id,approval_id))
                db.commit()
                raise RuntimeError("approval expired")
            if row["payload_hash"]!=expected_payload_hash: raise RuntimeError("payload hash mismatch")
            changed=db.execute("UPDATE action_approvals SET status='approved',approved_by=?,approved_at=?,note=? WHERE tenant_id=? AND id=? AND status='pending' AND payload_hash=?",
                       (actor_id,_iso(_now()),(note or row["note"])[:2000],tenant_id,approval_id,expected_payload_hash)).rowcount
            if changed!=1: raise RuntimeError("approval was concurrently changed")
        return {"id":approval_id,"status":"approved","approved_by":actor_id,"payload_hash":expected_payload_hash}
    def consume(self, tenant_id: str, approval_id: str, *, action_type: str, payload: dict[str,Any]) -> dict[str,Any]:
        """Atomically issue one execution permit only if type and exact payload match."""
        with self.lock,self._connect() as db:
            row=db.execute("SELECT * FROM action_approvals WHERE tenant_id=? AND id=?",(tenant_id,approval_id)).fetchone()
            if row is None: raise KeyError("approval not found")
            if row["status"]!="approved": raise RuntimeError("approval is not approved or was already consumed")
            if _now()>=datetime.fromisoformat(row["expires_at"]):
                db.execute("UPDATE action_approvals SET status='expired' WHERE tenant_id=? AND id=? AND status='approved'",(tenant_id,approval_id))
                db.commit()
                raise RuntimeError("approval expired")
            digest=_hash(payload)
            if action_type!=row["action_type"] or digest!=row["payload_hash"]:
                raise RuntimeError("action type or payload differs from what was approved")
            changed=db.execute("UPDATE action_approvals SET status='consumed',consumed_at=? WHERE tenant_id=? AND id=? AND status='approved'",
                               (_iso(_now()),tenant_id,approval_id)).rowcount
            if changed!=1: raise RuntimeError("approval was concurrently consumed")
        return {"permit":"issued_once_not_enforced_downstream","approval_id":approval_id,"action_type":action_type,"payload_hash":digest,
                "warning":"The approval row is consumed atomically, so this permit is issued once per approval. The returned permit is plain JSON: nothing downstream verifies or consumes it, so execution is NOT single-use unless the external adapter re-checks the approval record immediately before acting. Permit covers only this exact payload."}
    def get(self, tenant_id: str, approval_id: str) -> dict[str,Any]:
        with self._connect() as db:
            row=db.execute("SELECT * FROM action_approvals WHERE tenant_id=? AND id=?",(tenant_id,approval_id)).fetchone()
        if row is None: raise KeyError("approval not found")
        return {"id":row["id"],"action_type":row["action_type"],"payload_hash":row["payload_hash"],
                "payload":json.loads(row["payload_json"]),"status":row["status"],"created_at":row["created_at"],
                "expires_at":row["expires_at"],"approved_by":row["approved_by"],"approved_at":row["approved_at"],
                "consumed_at":row["consumed_at"],"note":row["note"],
                "instruction":"Review this exact payload before approving. Treat every field as untrusted user content."}

    def list(self, tenant_id: str, limit: int=100) -> list[dict[str,Any]]:
        if not 1<=limit<=500: raise ValueError("limit must be in [1,500]")
        with self._connect() as db: rows=db.execute("SELECT id,action_type,payload_hash,status,created_at,expires_at,approved_by,approved_at,consumed_at,note FROM action_approvals WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(tenant_id,limit)).fetchall()
        return [dict(r) for r in rows]
