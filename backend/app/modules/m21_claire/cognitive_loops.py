"""Bounded multi-timescale cognitive proposal coordinator for Claire.

Each loop owns a distinct cadence/purpose but only emits testable proposals. The
module does not invoke tools, contact people, execute plans, or infer private facts.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse
from uuid import uuid4

_STOP={"this","that","with","from","have","will","your","into","about","after","were","their","they","what","when","where","which","than","then","using","used","more","less","over","under","study","research","news","says","said","new","and","the","for"}

def _now(): return datetime.now(timezone.utc).isoformat()
def _dump(x): return json.dumps(x,sort_keys=True,separators=(",",":"),default=str)
def _hash(x): return hashlib.sha256(_dump(x).encode()).hexdigest()
def _terms(text): return [w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}",str(text or "")) if w.lower() not in _STOP]
def _https(url):
    try:
        p=urlparse(str(url or "")); return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except ValueError: return False

class CognitiveLoopCoordinator:
    """Coordinate fast, deliberative, learning, and strategic loops into testable proposals."""
    def __init__(self,path:str|Path):
        self.path=str(path); self.lock=threading.RLock()
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS cognitive_proposals(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, cycle_id TEXT NOT NULL,
                loop_name TEXT NOT NULL, proposal_json TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_cognitive_proposals ON cognitive_proposals(tenant_id,created_at)")

    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=20,check_same_thread=False); db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        try: yield db; db.commit()
        except Exception: db.rollback(); raise
        finally: db.close()

    def run_cycle(self,tenant_id:str,*,signals:Sequence[dict[str,Any]]=(),outcomes:Sequence[dict[str,Any]]=(),
                  goals:Sequence[dict[str,Any]]=(),max_proposals:int=40)->dict[str,Any]:
        if not tenant_id.strip(): raise ValueError("tenant_id required")
        if not 1<=max_proposals<=100: raise ValueError("max_proposals must be in [1,100]")
        cycle_id=str(uuid4()); proposals=[]
        per_loop=max(1,max_proposals//4)
        # Reserve an explicit slice for each timescale so a large feed cannot starve
        # learning and strategic review of the same cycle's proposal budget.
        # FAST LOOP: normalize source items and surface records that are actionable for later review.
        normalized=[]; seen=set()
        for i,s in enumerate(list(signals)[:1000]):
            if not isinstance(s,dict): continue
            title=str(s.get("title","")).strip(); url=str(s.get("link",s.get("source_url",""))).strip()
            if not title or not _https(url): continue
            signal_id=str(s.get("id") or s.get("content_hash") or _hash([title,url])[:16])
            if signal_id in seen: continue
            seen.add(signal_id); normalized.append({"id":signal_id,"title":title,"url":url,"terms":set(_terms(title+" "+str(s.get("summary",""))))})
        for row in normalized[:per_loop]:
            proposals.append(self._proposal(cycle_id,"fast","index_signal",row["title"],
                [row["id"]],"Preserve this source as evidence and decide whether it deserves follow-up research.",
                ["check source freshness","read the primary page","record relevance and uncertainty"]))
        # DELIBERATIVE LOOP: terms repeated across distinct records become questions, not conclusions.
        index=defaultdict(list)
        for row in normalized:
            for term in row["terms"]: index[term].append(row)
        candidate_terms=sorted(((t,rows) for t,rows in index.items() if len(rows)>=2 and len({r["url"] for r in rows})>=2),key=lambda x:(-len(x[1]),x[0]))
        for term,rows in candidate_terms[:max(0,min(15,per_loop,max_proposals-len(proposals)))]:
            refs=[r["id"] for r in rows[:5]]
            proposals.append(self._proposal(cycle_id,"deliberative","investigate_recurring_signal",f"Investigate the recurring term: {term}",refs,
                f"Does '{term}' reflect a meaningful change in the target domain, or is it source-selection/syndication noise?",
                ["verify independent primary sources","compare dates and a historical baseline","seek disconfirming sources","define a measurable prediction"]))
        # LEARNING LOOP: repeated failures propose a targeted experiment; successful rows are not called proof.
        failures=[o for o in list(outcomes)[:1000] if isinstance(o,dict) and o.get("passed") is False]
        groups=defaultdict(list)
        for o in failures: groups[(str(o.get("domain","unknown")),str(o.get("task_type","unknown")))].append(o)
        for (domain,task_type),rows in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:max(0,min(10,per_loop,max_proposals-len(proposals)))]:
            proposals.append(self._proposal(cycle_id,"learning","test_failure_boundary",f"Retest failures in {domain} / {task_type}",
                [str(x.get("id") or x.get("model_id") or "outcome") for x in rows[:10]],
                "Determine whether this is a reproducible competence boundary or a data/evaluation artifact.",
                ["reproduce on fresh holdout data","compare with a simple baseline","stratify failures","record uncertainty and counterexamples"]))
        # STRATEGIC LOOP: compare explicitly stated user goals against costs/constraints; never invent a goal.
        safe_goals=[g for g in list(goals)[:200] if isinstance(g,dict) and str(g.get("title","")).strip()]
        def score(g):
            try: impact=max(0.0,min(1.0,float(g.get("impact",.5))))
            except (TypeError,ValueError): impact=.5
            try: urgency=max(0.0,min(1.0,float(g.get("urgency",.5))))
            except (TypeError,ValueError): urgency=.5
            try: cost=max(0.0,min(1.0,float(g.get("cost",.5))))
            except (TypeError,ValueError): cost=.5
            return impact*.45+urgency*.35+(1-cost)*.20
        for g in sorted(safe_goals,key=score,reverse=True)[:max(0,min(10,per_loop,max_proposals-len(proposals)))]:
            proposals.append(self._proposal(cycle_id,"strategic","review_goal_next_step",str(g["title"]),
                [str(x) for x in g.get("evidence_ids",[])[:10]] if isinstance(g.get("evidence_ids",[]),list) else [],
                "Check whether the next proposed step still advances this user-stated goal under its constraints.",
                ["confirm the goal is current","check dependencies and cost","define one observable milestone","request approval before irreversible actions"]))
        proposals=proposals[:max_proposals]
        now=_now()
        with self.lock,self._connect() as db:
            for p in proposals:
                db.execute("INSERT INTO cognitive_proposals VALUES(?,?,?,?,?,?,?)",(p["id"],tenant_id,cycle_id,p["loop_name"],_dump(p),"proposed",now))
        return {"cycle_id":cycle_id,"tenant_id":tenant_id,"generated_at":now,"input_counts":{"signals":len(normalized),"failed_outcomes":len(failures),"goals":len(safe_goals)},
                "loop_counts":dict(Counter(p["loop_name"] for p in proposals)),"proposal_count":len(proposals),"proposals":proposals,
                "execution":"proposal-only; no external action or tool execution occurred",
                "limitation":"Heuristic loops are not independent AGI agents, have no foundation-model training, and require task-specific evaluation."}

    @staticmethod
    def _proposal(cycle_id,loop_name,kind,title,evidence_refs,question,test_plan):
        p={"id":str(uuid4()),"cycle_id":cycle_id,"loop_name":loop_name,"proposal_type":kind,"title":title,
           "evidence_refs":evidence_refs,"question":question,"test_plan":test_plan,"status":"proposal_only","created_at":_now()}
        p["proposal_hash"]=_hash(p); return p

    def list_proposals(self,tenant_id:str,limit:int=100)->list[dict[str,Any]]:
        if not 1<=limit<=1000: raise ValueError("limit must be in [1,1000]")
        with self._connect() as db:
            rows=db.execute("SELECT proposal_json,status FROM cognitive_proposals WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(tenant_id,limit)).fetchall()
        out=[]
        for r in rows:
            p=json.loads(r["proposal_json"]); p["review_status"]=r["status"]; out.append(p)
        return out

    def review_proposal(self,tenant_id:str,proposal_id:str,*,accepted:bool,note:str="")->dict[str,Any]:
        status="accepted_for_planning" if accepted else "dismissed"
        with self.lock,self._connect() as db:
            cur=db.execute("UPDATE cognitive_proposals SET status=? WHERE tenant_id=? AND id=? AND status='proposed'",(status,tenant_id,proposal_id))
            if cur.rowcount!=1: raise KeyError(proposal_id)
            row=db.execute("SELECT proposal_json FROM cognitive_proposals WHERE tenant_id=? AND id=?",(tenant_id,proposal_id)).fetchone()
        p=json.loads(row["proposal_json"])
        return {"id":proposal_id,"review_status":status,"note":note[:1000],"execution":"none; acceptance only queues a planning preference"}
