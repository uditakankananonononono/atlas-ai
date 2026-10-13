"""v2 agent: adds batch/joint admission and a retirement audit on top of agent.Agent (v1 untouched)."""
from __future__ import annotations
from agent import Agent, evaluate

class Agent2(Agent):
    def __init__(self, mode, budget, val_tasks, margin=2, audit=False, joint=False, pend_cap=20, **kw):
        super().__init__("gated" if joint else mode, budget, val_tasks, margin=margin, **kw)
        self.real_mode, self.audit, self.joint, self.pend_cap = mode, audit, joint, pend_cap
        self.pending, self.propose_count, self.retired = [], {}, []
        if mode == "nolib":
            self.mode = "nolib"
        if mode == "admit_all":
            self.mode = "admit_all"

    def consider(self, cand, task_id):
        if not self.joint:
            return super().consider(cand, task_id)
        rec = {"task": task_id, "origin": cand.origin, "program": list(cand.program)}
        if any(s.program == cand.program for s in self.library):
            rec.update(decision="duplicate"); self.log.append(rec); return False
        rec["own_tests_pass"] = cand.run_tests()
        if not rec["own_tests_pass"]:
            rec.update(decision="reject_own_tests"); self.log.append(rec); return False
        self.propose_count[cand.program] = self.propose_count.get(cand.program, 0) + 1
        if all(p.program != cand.program for p in self.pending):
            self.pending.append(cand)
        rec.update(decision="pending"); self.log.append(rec)
        return False

    def joint_round(self):
        """Gate the pending pool as a SET: admit only if the whole set gains >= margin on validation, then
        backward-eliminate members whose removal does not lower the validation solved count."""
        if not self.joint or not self.pending:
            return
        pend = sorted(self.pending, key=lambda s: -self.propose_count[s.program])[: self.pend_cap]
        self.pending = []
        base = sum(self._val_results(self.library))
        cur = list(pend)
        s_all = sum(self._val_results(self.library + cur))
        rec = {"task": "joint", "pool": len(pend), "val_base": base, "val_all": s_all}
        if s_all - base < self.margin:
            rec.update(decision="reject_set"); self.log.append(rec); return
        for c in sorted(list(cur), key=lambda s: self.propose_count[s.program]):
            s_wo = sum(self._val_results(self.library + [x for x in cur if x is not c]))
            if s_wo >= s_all:
                cur.remove(c); s_all = s_wo
        if s_all - base >= self.margin:
            self.library += cur
            rec.update(decision="admit_set", admitted=[list(c.program) for c in cur], val_after=s_all)
        else:
            rec.update(decision="reject_after_elimination")
        self.log.append(rec)

    def audit_round(self):
        """Retire skills whose removal does not reduce validation solved count (leave-one-out)."""
        if not self.audit or self.mode in ("nolib", "admit_all") or not self.library:
            return
        cur = sum(self._val_results(self.library))
        for s in list(self.library):
            rest = [x for x in self.library if x is not s]
            w = sum(self._val_results(rest))
            if w >= cur:
                self.library = rest; self.retired.append(list(s.program)); cur = w
        self._base = None
