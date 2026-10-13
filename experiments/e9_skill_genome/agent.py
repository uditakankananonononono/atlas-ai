"""Search agent with a skill library, acquisition operators (induce/rewrite/combine), trust gate."""
from __future__ import annotations
import random
from ops import OPS, NAMES
from genome import Skill, make_skill
from tasks import feedback

MAXLEN = 4

class Unit:
    __slots__ = ("name", "fn", "skill")
    def __init__(self, name, fn, skill=None):
        self.name, self.fn, self.skill = name, fn, skill

BASE_UNITS = [Unit(n, OPS[n]) for n in NAMES]

def solve(task, library, budget):
    """BFS over unit sequences with observational-equivalence pruning. Budget = unit executions.
    Library skills are tried first, are skipped when their precondition fails on the actual inputs
    they would receive, and are pruned when their expected-output contract is violated.
    Returns (units_path, apps) or (None, apps). First program fitting the train examples wins."""
    units = [Unit(s.sid, s.fn, s) for s in library] + BASE_UNITS
    root = tuple(task.train_inputs)
    target = tuple(task.train_outputs)
    seen = {root}
    frontier = [(root, ())]
    apps = 0
    for _ in range(MAXLEN):
        nxt = []
        for state, path in frontier:
            for u in units:
                sk = u.skill
                if sk is not None and not all(sk.applicable(x) for x in state):
                    continue
                if apps >= budget:
                    return None, apps
                apps += 1
                try:
                    out = tuple(tuple(u.fn(x)) for x in state)
                except Exception:
                    continue
                if sk is not None and not all(sk.contract_ok(i, o) for i, o in zip(state, out)):
                    continue
                if out == target:
                    return path + (u,), apps
                if out not in seen:
                    seen.add(out); nxt.append((out, path + (u,)))
        frontier = nxt
    return None, apps

def flatten(path):
    prog = []
    for u in path:
        prog.extend(u.skill.program if u.skill else (u.name,))
    return tuple(prog)

def run_path(path, x):
    for u in path:
        x = u.fn(x)
    return x

def evaluate(tasks, library, budget):
    """-> list of bool (solved = fits examples AND passes all hidden inputs)."""
    res = []
    for t in tasks:
        p, _ = solve(t, library, budget)
        res.append(bool(p) and feedback(t, lambda x: run_path(p, x))[0])
    return res

def rewrite(program, examples):
    """Single-edit repairs (delete, insert, substitute) of `program`; first that fits all examples
    (train examples + the counterexample) wins. Deterministic order."""
    def fits(p):
        try:
            for i, o in examples:
                x = i
                for n in p:
                    x = OPS[n](x)
                if tuple(x) != tuple(o):
                    return False
            return True
        except Exception:
            return False
    n = len(program)
    cands = []
    for i in range(n):
        cands.append(program[:i] + program[i + 1:])
    for i in range(n + 1):
        for name in NAMES:
            cands.append(program[:i] + (name,) + program[i:])
    for i in range(n):
        for name in NAMES:
            if name != program[i]:
                cands.append(program[:i] + (name,) + program[i + 1:])
    for c in cands:
        if 1 <= len(c) <= 5 and c != program and fits(c):
            return c
    return None

class Agent:
    def __init__(self, mode, budget, val_tasks, margin=2, use_rewrite=True, use_combine=True):
        assert mode in ("nolib", "admit_all", "gated")
        self.mode, self.budget, self.val, self.margin = mode, budget, val_tasks, margin
        self.use_rewrite, self.use_combine = use_rewrite, use_combine
        self.library = []
        self.log = []                  # candidate decisions
        self._base = None              # cached validation results for the current library
        self.pair_counts = {}
        self.n_id = 0

    def _sid(self, tag):
        self.n_id += 1
        return f"{tag}{self.n_id}"

    def _val_results(self, lib):
        return evaluate(self.val, lib, self.budget)

    def consider(self, cand, task_id):
        """Admission decision. Own tests are necessary in every mode; only the gate asks for unseen gain."""
        rec = {"task": task_id, "origin": cand.origin, "program": list(cand.program)}
        if any(s.program == cand.program for s in self.library):
            rec.update(decision="duplicate"); self.log.append(rec); return False
        rec["own_tests_pass"] = cand.run_tests()
        if not rec["own_tests_pass"]:
            rec.update(decision="reject_own_tests"); self.log.append(rec); return False
        if self.mode == "admit_all":
            self.library.append(cand); rec.update(decision="admit"); self.log.append(rec); return True
        if self._base is None:
            self._base = self._val_results(self.library)
        with_c = self._val_results(self.library + [cand])
        wins = sum(1 for a, b in zip(self._base, with_c) if b and not a)
        losses = sum(1 for a, b in zip(self._base, with_c) if a and not b)
        rec.update(val_wins=wins, val_losses=losses)
        if wins - losses >= self.margin:
            self.library.append(cand); self._base = with_c; rec.update(decision="admit")
            self.log.append(rec); return True
        rec.update(decision="reject_no_unseen_gain"); self.log.append(rec); return False

    def step(self, task):
        """One acquisition task: solve, get feedback, propose candidates, decide admission."""
        path, _ = solve(task, self.library, self.budget)
        if path is None:
            return {"solved": None}
        ok, cx = feedback(task, lambda x: run_path(path, x))
        flat = flatten(path)
        for u in path:
            if u.skill and not ok:
                u.skill.failure_cases.append({"task": task.tid, "input": cx[0], "expected": cx[1], "got": cx[2]})
        if self.mode == "nolib":
            return {"solved": ok}
        tests = list(zip(task.train_inputs, task.train_outputs))
        if len(flat) >= 2:
            fcs = [] if ok else [{"task": task.tid, "input": cx[0], "expected": cx[1], "got": cx[2]}]
            self.consider(make_skill(self._sid("s"), flat, "induced", tests, failure_cases=fcs), task.tid)
        if not ok and self.use_rewrite:
            fixed = rewrite(flat, tests + [(cx[0], cx[1])])
            if fixed is not None and len(fixed) >= 2:
                self.consider(make_skill(self._sid("s"), fixed, "rewritten", tests + [(cx[0], cx[1])],
                                         parent=None), task.tid)
        for a, b in zip(path, path[1:]):
            k = (flatten((a,)), flatten((b,)))
            self.pair_counts[k] = self.pair_counts.get(k, 0) + 1
        return {"solved": ok}

    def combine_round(self):
        if not self.use_combine or self.mode == "nolib":
            return
        ranked = sorted(self.pair_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        done = 0
        for (a, b), _ in ranked:
            prog = a + b
            if not (3 <= len(prog) <= 5) or any(s.program == prog for s in self.library):
                continue
            # tests: snapshot of the combined procedure on inputs from the parents' tests (regression snapshots)
            ins = [i for s in self.library for i, _ in s.tests[:2]][:6]
            if not ins:
                continue
            outs = []
            for i in ins:
                x = i
                for n in prog:
                    x = OPS[n](x)
                outs.append(x)
            self.consider(make_skill(self._sid("s"), prog, "combined", list(zip(ins, outs))), "combine")
            done += 1
            if done >= 2:
                break
