"""Opt-in preference elicitation to help Claire learn task-specific decision preferences."""
from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4


def _now(): return datetime.now(timezone.utc).isoformat()


class PreferenceInterviewStore:
    """Stores explicit pairwise choices by tenant/domain; user can inspect and erase them."""
    def __init__(self,path:str|Path):
        self.path=str(path); self.lock=threading.RLock()
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS preference_choices(
              id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT NOT NULL,
              criterion TEXT NOT NULL, left_option TEXT NOT NULL, right_option TEXT NOT NULL,
              chosen_option TEXT NOT NULL, importance REAL NOT NULL, context TEXT NOT NULL,
              created_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_preferences ON preference_choices(tenant_id,domain,criterion)")
    @contextmanager
    def _connect(self):
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
    def next_question(self,tenant_id:str,domain:str,criterion:str,options:Sequence[str],*,context:str="") -> dict[str,Any]:
        cleaned=list(dict.fromkeys(str(x).strip() for x in options if str(x).strip()))
        if len(cleaned)<2 or len(cleaned)>100: raise ValueError("provide 2 to 100 distinct options")
        with self._connect() as db:
            rows=db.execute("SELECT left_option,right_option,chosen_option FROM preference_choices WHERE tenant_id=? AND domain=? AND criterion=?",(tenant_id,domain,criterion)).fetchall()
        history={}
        for r in rows:
            pair=tuple(sorted((r["left_option"],r["right_option"])))
            history[pair]=history.get(pair,0)+1
        pair=min(((a,b) for i,a in enumerate(cleaned) for b in cleaned[i+1:]),key=lambda p:(history.get(tuple(sorted(p)),0),p))
        return {"question_id":str(uuid4()),"domain":domain,"criterion":criterion,"left_option":pair[0],"right_option":pair[1],
                "question":f"For {criterion}, which would you prefer for {domain}: {pair[0]} or {pair[1]}?",
                "context":context,"why_asked":"This comparison is underexplored in your explicit answers; it is not a psychological diagnosis.",
                "answer_options":[pair[0],pair[1]],"optional":True}
    def answer(self,tenant_id:str,domain:str,criterion:str,left_option:str,right_option:str,chosen_option:str,*,importance:float=1.0,context:str="") -> dict[str,Any]:
        if not tenant_id.strip() or not domain.strip() or not criterion.strip(): raise ValueError("tenant, domain, and criterion required")
        if left_option==right_option or chosen_option not in {left_option,right_option}: raise ValueError("chosen_option must match one of two distinct options")
        if not 0<=importance<=1: raise ValueError("importance must be in [0,1]")
        ident=str(uuid4())
        with self.lock,self._connect() as db:
            db.execute("INSERT INTO preference_choices VALUES(?,?,?,?,?,?,?,?,?,?)",(ident,tenant_id,domain,criterion,left_option,right_option,chosen_option,importance,context[:2000],_now()))
        return {"id":ident,"stored":True,"domain":domain,"criterion":criterion,"chosen_option":chosen_option,
                "controls":"You can inspect or erase stored preferences at any time."}
    def profile(self,tenant_id:str,domain:str|None=None) -> dict[str,Any]:
        with self._connect() as db:
            if domain: rows=db.execute("SELECT * FROM preference_choices WHERE tenant_id=? AND domain=? ORDER BY created_at",(tenant_id,domain)).fetchall()
            else: rows=db.execute("SELECT * FROM preference_choices WHERE tenant_id=? ORDER BY created_at",(tenant_id,)).fetchall()
        data={}
        for r in rows:
            k=(r["domain"],r["criterion"]); slot=data.setdefault(k,{"scores":{},"comparisons":0,"importance_weight":0.0})
            slot["scores"][r["chosen_option"]]=slot["scores"].get(r["chosen_option"],0)+r["importance"]
            slot["scores"][r["left_option"]]=slot["scores"].get(r["left_option"],0)
            slot["scores"][r["right_option"]]=slot["scores"].get(r["right_option"],0)
            slot["comparisons"]+=1; slot["importance_weight"]+=r["importance"]
        out=[]
        for (d,c),v in sorted(data.items()):
            total=sum(v["scores"].values())
            rankings=sorted(v["scores"].items(),key=lambda p:p[1],reverse=True)
            out.append({"domain":d,"criterion":c,"ranked_options":[{"option":o,"explicit_preference_weight":round(s,4),"share_of_recorded_weight":round(s/total,4) if total else 0} for o,s in rankings],
                        "comparison_count":v["comparisons"],"confidence":"low" if v["comparisons"]<5 else "descriptive_not_calibrated"})
        return {"items":out,"warning":"This summarizes only choices explicitly provided for these task domains; it is not a personality profile."}
    def erase(self,tenant_id:str,domain:str|None=None) -> dict[str,Any]:
        with self.lock,self._connect() as db:
            if domain: changed=db.execute("DELETE FROM preference_choices WHERE tenant_id=? AND domain=?",(tenant_id,domain)).rowcount
            else: changed=db.execute("DELETE FROM preference_choices WHERE tenant_id=?",(tenant_id,)).rowcount
        return {"deleted_choices":changed,"scope":domain or "all_domains"}
