"""E9 agents. Cost unit = program evaluations (one run of the visible suite on one candidate program; fault-localization
coverage runs are charged 1 evaluation each; cache hits are free). Secondary cost = individual test executions.
All agents are anytime (budget-agnostic), so success at budget B = first visible-pass at evals <= B, scored on hidden tests.
  S_uniform : single loop, greedy hill climb (accept only strictly fewer failing visible tests;), uniform edit proposals.
  S_fl      : single loop, same, proposals weighted by Ochiai suspiciousness computed once at the start.
  M         : three timescales around the same proposer/acceptor: fast = propose/evaluate edits; medium = recompute fault
              localization (charged) after every strict improvement; slow = per-episode operator-kind credit weights and a
              stuck rule (no improvement for STUCK evals -> revert to best state, flatten FL weights, recompute).
  M_noslow / M_nomed : ablations."""
import math, random, sys
from repo_tasks import Project
import signal
STUCK, EPS0, EPS_GROW = 120, 0.05, 2.0


class Ev:
    def __init__(self, P, maxb):
        self.P, self.maxb, self.n, self.tests, self.cache = P, maxb, 0, 0, {}

    def done(self): return self.n >= self.maxb

    def fit(self, state):
        key = tuple(sorted(state.items()))
        if key in self.cache: return self.cache[key]
        self.n += 1; self.tests += len(self.P.vis)
        f = self.P.run(self.P.build(state), self.P.vis)
        self.cache[key] = f; return f

    def fl(self, state):
        """Ochiai suspiciousness per (module, lineno). One charged evaluation."""
        self.n += 1; self.tests += len(self.P.vis)
        ns = self.P.build(state); cov = []; fails = []
        cur = set()
        def tr(frame, ev, arg):
            fn = frame.f_code.co_filename
            if fn.startswith("<m"):
                cur.add((fn, frame.f_lineno)); return tr
            return None
        signal.setitimer(signal.ITIMER_REAL, 2.0)
        for f, xs, exp in self.P.vis:
            cur.clear(); sys.settrace(tr)
            try: ok = ns[f](list(xs)) == exp
            except BaseException: ok = False
            finally: sys.settrace(None)
            cov.append(set(cur)); fails.append(not ok)
        signal.setitimer(signal.ITIMER_REAL, 0)
        F = sum(fails); sus = {}
        if F == 0: return sus
        for ln in set().union(*cov):
            fe = sum(1 for c, b in zip(cov, fails) if b and ln in c); pe = sum(1 for c, b in zip(cov, fails) if not b and ln in c)
            sus[ln] = fe / math.sqrt(F * (fe + pe))
        return sus


def run_agent(P, kind, seed, maxb=3000):
    esc = kind.endswith("_esc"); kind = kind[:-4] if esc else kind  # _esc: when the neighbourhood is exhausted, apply one random edit to `best` and continue; `best` is overwritten on any strict improvement of the kicked state
    rng = random.Random(seed); ev = Ev(P, maxb)
    space = P.edit_space()
    line_of = {}
    for m in range(len(P.trees)):
        for (i, k, ln, vs) in P.sites[m]: line_of[(m, i)] = f"<m{m}>", ln
    orig = {s: P.original_of(s) for (s, v, k) in space}
    state = dict(P.bugs); cur = ev.fit(state); best = (cur, dict(state))
    use_fl = kind != "S_uniform"; med = kind in ("M", "M_noslow"); slow = kind in ("M", "M_nomed")
    sus = ev.fl(state) if use_fl else {}
    tried = set(); eps = EPS0; last_imp = ev.n
    kt, ks = {}, {}  # per-kind tries / successes (slow loop)
    props = 0
    while cur > 0 and not ev.done() and props < maxb * 20:
        cand = [(s, v, k) for (s, v, k) in space if state.get(s, orig[s]) != v and (s, v) not in tried]
        if not cand:
            if not esc: break
            s, v, k = rng.choice([c for c in space if best[1].get(c[0], orig[c[0]]) != c[1]])
            state = dict(best[1]); state[s] = v; cur = ev.fit(state); tried = set(); last_imp = ev.n
            if use_fl and kind != "S_fl": sus = ev.fl(state)
            continue
        w = []
        for (s, v, k) in cand:
            x = (sus.get(line_of[s], 0.0) + eps) if use_fl else 1.0
            if slow: x *= (1 + ks.get(k, 0)) / (2 + kt.get(k, 0))
            w.append(x)
        s, v, k = rng.choices(cand, weights=w)[0]
        tried.add((s, v)); props += 1
        new = dict(state); new[s] = v
        before = ev.n; f = ev.fit(new)
        kt[k] = kt.get(k, 0) + 1
        if f < cur:
            ks[k] = ks.get(k, 0) + 1
            state, cur, tried, last_imp = new, f, set(), ev.n
            best = (cur, dict(state)); eps = EPS0
            if med and cur > 0 and not ev.done(): sus = ev.fl(state)
        if slow and ev.n - last_imp > STUCK and not ev.done():
            state = dict(best[1]); cur = best[0]; tried = set(); eps = min(1.0, eps * EPS_GROW); last_imp = ev.n
            sus = ev.fl(state)
    hid = P.run(P.build(state), P.hid) if cur == 0 else None
    return dict(solved_vis=cur == 0, evals=ev.n, tests=ev.tests, hid_fail=hid, left=cur)
