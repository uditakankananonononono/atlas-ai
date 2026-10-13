"""Tenant-scoped persistence for research runs, model outcomes and public signals."""
from __future__ import annotations
import json, sqlite3, threading, hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from .research_lab import EpistemicCartographer
from .approval_gate import ApprovalGate


def _now(): return datetime.now(timezone.utc).isoformat()


class ResearchWorkspaceStore:
    def __init__(self, path: str|Path):
        self.path=str(path); self.lock=threading.RLock()
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS research_runs(
              id TEXT NOT NULL, tenant_id TEXT NOT NULL, payload TEXT NOT NULL,
              content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(tenant_id,id));
            CREATE INDEX IF NOT EXISTS ix_research_runs ON research_runs(tenant_id,created_at);
            CREATE TABLE IF NOT EXISTS research_outcomes(
              id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
              domain TEXT NOT NULL, task_type TEXT NOT NULL, complexity REAL NOT NULL,
              passed INTEGER NOT NULL, predicted_confidence REAL, model_id TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_research_outcomes ON research_outcomes(tenant_id,domain,task_type);
            CREATE TABLE IF NOT EXISTS research_signals(
              tenant_id TEXT NOT NULL, content_hash TEXT NOT NULL, source_domain TEXT NOT NULL,
              body TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(tenant_id,content_hash));
            CREATE INDEX IF NOT EXISTS ix_research_signals ON research_signals(tenant_id,created_at);
            """)
        self.approvals=ApprovalGate(self.path)

    @contextmanager
    def _connect(self):
        # Close each connection deterministically; sqlite3's connection context
        # manager alone commits/rolls back but does not close the descriptor.
        db=sqlite3.connect(self.path,timeout=20,check_same_thread=False)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save_run(self, tenant_id: str, report: dict[str,Any]) -> dict[str,Any]:
        if not tenant_id.strip() or not report.get("id"): raise ValueError("tenant and run id are required")
        payload=json.dumps(report,sort_keys=True,separators=(",",":"),default=str)
        import hashlib
        digest=hashlib.sha256(payload.encode()).hexdigest(); created=report.get("finished_at",_now())
        with self.lock,self._connect() as db:
            db.execute("INSERT INTO research_runs VALUES(?,?,?,?,?)",(report["id"],tenant_id,payload,digest,created))
        return {"id":report["id"],"content_hash":digest,"created_at":created}

    def list_runs(self, tenant_id: str, limit: int=50) -> list[dict[str,Any]]:
        if not 1<=limit<=200: raise ValueError("limit must be in [1,200]")
        with self._connect() as db: rows=db.execute("SELECT payload,content_hash,created_at FROM research_runs WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(tenant_id,limit)).fetchall()
        return [{"report":json.loads(r["payload"]),"content_hash":r["content_hash"],"created_at":r["created_at"]} for r in rows]

    def record_outcome(self, tenant_id: str, *, domain: str, task_type: str, complexity: float,
                       passed: bool, predicted_confidence: float|None, model_id: str) -> dict[str,Any]:
        if not tenant_id.strip(): raise ValueError("tenant is required")
        if not 0<=complexity<=1: raise ValueError("complexity must be in [0,1]")
        if predicted_confidence is not None and not 0<=predicted_confidence<=1: raise ValueError("confidence must be in [0,1]")
        with self.lock,self._connect() as db:
            cur=db.execute("INSERT INTO research_outcomes(tenant_id,domain,task_type,complexity,passed,predicted_confidence,model_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                           (tenant_id,domain,task_type,complexity,int(passed),predicted_confidence,model_id,_now()))
        return {"id":cur.lastrowid,"stored":True}

    def epistemic_report(self, tenant_id: str, limit: int=5000) -> dict[str,Any]:
        if not 1<=limit<=50000: raise ValueError("limit must be in [1,50000]")
        with self._connect() as db: rows=db.execute("SELECT domain,task_type,complexity,passed,predicted_confidence,model_id,created_at FROM research_outcomes WHERE tenant_id=? ORDER BY id DESC LIMIT ?",(tenant_id,limit)).fetchall()
        cart=EpistemicCartographer(max_records=limit)
        for r in reversed(rows):
            cart.record(domain=r["domain"],task_type=r["task_type"],complexity=r["complexity"],passed=bool(r["passed"]),
                        predicted_confidence=r["predicted_confidence"],model_id=r["model_id"])
        result=cart.report(); result["persistence"]="sqlite-backed outcomes; interpretation limited to recorded cases"; return result

    def add_signals(self, tenant_id: str, signals: list[dict[str,Any]]) -> dict[str,Any]:
        if not tenant_id.strip(): raise ValueError("tenant is required")
        if len(signals)>500: raise ValueError("at most 500 signals per request")
        new=0; duplicates=0
        with self.lock,self._connect() as db:
            for original in signals:
                signal=dict(original)
                title=str(signal.get("title", ""))[:500]
                summary=str(signal.get("summary", ""))[:2000]
                domain=str(signal.get("source_domain", "unknown")).strip().lower()[:255] or "unknown"
                if not title and not summary: raise ValueError("each signal needs a title or summary")
                # Do not trust caller-provided hashes; bind dedupe identity to normalized
                # content and its source domain so syndicated copies retain provenance.
                ch=hashlib.sha256((domain+"\n"+title+"\n"+summary).encode()).hexdigest()
                signal["title"]=title; signal["summary"]=summary; signal["source_domain"]=domain; signal["content_hash"]=ch
                body=json.dumps(signal,sort_keys=True,separators=(",",":"),default=str)
                try:
                    db.execute("INSERT INTO research_signals VALUES(?,?,?,?,?)",(tenant_id,ch,domain,body,_now())); new+=1
                except sqlite3.IntegrityError: duplicates+=1
        return {"new":new,"duplicates":duplicates}

    def list_signals(self, tenant_id: str, limit: int=500) -> list[dict[str,Any]]:
        if not 1<=limit<=5000: raise ValueError("limit must be in [1,5000]")
        with self._connect() as db: rows=db.execute("SELECT body FROM research_signals WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(tenant_id,limit)).fetchall()
        return [json.loads(r["body"]) for r in rows]
