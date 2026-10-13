"""E9 cognitive multiverse: a population of heterogeneous minds over the E7
program-induction harness, with a shared macro pool, representation
invention, cross-lineage transfer credit and four selection rules.

Comparability contract with E7 (experiments/e7_library_transfer): same
PRIMS, same apply_prog/verify semantics, same task objects, same budget
unit (programs evaluated, macro = 1 depth), same max_depth=4, same
train(8)/test(8) accept-then-verify split. A bfs+short mind with no dropped
primitives and an empty personal library reproduces e7's solve() exactly
(pinned by test_multiverse.py). Population arms differ from e7 search only
by the mind parameters described here; the e7-lib arm reruns e7's exact
library.learn + solve as the anchored baseline.

Mind heterogeneity: strategy (bfs / beam / rand), per-task budget
(strong=1000 like e7's main budget, weak=300 like e7's loop budget),
episodic memory (replay own verified programs first), tiebreak objective
(short = e7 canonical order, macro = macro-heavy candidates first, novel =
population-rare primitives first), representation (2 dropped list
primitives + a personal macro library).

Macro invention: from a verified solve, all new-behaviour windows (length 2
or 3, like e7's candidates) of the flat program, published to the pool
with provenance. Adoption: usage-weighted, own-lineage excluded, personal
library capped. Credit: a verified solve using another lineage's macro
gives that lineage 1 usage credit. Selection value: own window solves
(+ lam * lineage credit for the multiverse rule). Spammer minds publish
random windows; credit_mode 'publication' counts publications instead of
usages (the naive rule the guard must beat).
"""
from __future__ import annotations

import hashlib
import itertools
import pathlib
import random
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                      / 'e7_library_transfer'))
import dsl  # noqa: E402  e7 harness
from dsl import PRIMS, LISTFNS, INTFNS, safe_apply, verify, flat  # noqa: E402

MAX_DEPTH = 4  # e7 default


def _rng(seed_material):
    """Process- and version-stable RNG: int seed from sha256 of the material.
    (random.Random(tuple) is PYTHONHASHSEED-dependent and rejected on 3.12.)"""
    digest = hashlib.sha256(str(seed_material).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], 'big'))
PROBES = ((1, 2, 3), (-2, 0, 2), (5,), (3, 1, 2, 4), (0, 0, 1), (-1, -2, -3))
_SIG_CACHE = {}


def signature(expansion):
    """Behavioural signature of a flat base-primitive window on fixed probes."""
    key = tuple(expansion)
    if key not in _SIG_CACHE:
        out = []
        for p in PROBES:
            r = safe_apply(tuple(key), list(p), {})
            out.append(r if isinstance(r, int) else (tuple(r) if r is not None else None))
        _SIG_CACHE[key] = tuple(out)
    return _SIG_CACHE[key]


IDENTITY_SIG = tuple(list(p) and tuple(p) or tuple(p) for p in PROBES)
IDENTITY_SIG = tuple(tuple(p) for p in PROBES)


class Mind:
    def __init__(self, mind_id, lineage, strategy, budget, memory_on,
                 tiebreak, prims, rng, spammer=False):
        self.id = mind_id
        self.lineage = lineage
        self.strategy = strategy
        self.budget = budget
        self.memory_on = memory_on
        self.tiebreak = tiebreak
        self.prims = list(prims)          # base primitives this mind can use
        self.lib = {}                     # personal macro library (name -> expansion)
        self.cache = []                   # own verified programs (name tuples)
        self.rng = rng
        self.spammer = spammer
        self.window_solves = 0
        self.total_solves = 0

    def names(self):
        return list(self.prims) + list(self.lib)

    def _train_sig(self, prog, train):
        out = []
        for ins, _ in train:
            r = safe_apply(prog, list(ins), self.lib)
            out.append(r if isinstance(r, int) else (tuple(r) if r is not None else None))
        return tuple(out)

    def _accept(self, prog, task):
        return all(safe_apply(prog, list(i), self.lib) == o for i, o in task['train'])

    def solve(self, task, beam_width, cache_replay, pop_usage):
        """e7-budget semantics: returns (program or None, programs evaluated).
        A program counts as a solve only if it also passes verify() (held-out
        test examples); the caller does that via _verified below."""
        nodes = 0
        target = tuple((o if isinstance(o, int) else tuple(o)) for _, o in task['train'])
        seen = set()

        def check(prog):
            nonlocal nodes
            nodes += 1
            sig = self._train_sig(prog, task['train'])
            if sig in seen:
                return None
            seen.add(sig)
            if sig == target and verify(task, prog, self.lib):
                return prog
            return None

        if self.memory_on and self.cache:
            for prog in self.cache[-cache_replay:]:
                if nodes >= self.budget:
                    return None, nodes
                got = check(prog)
                if got is not None:
                    return got, nodes

        if self.strategy == 'beam':
            beam = [()]
            for _ in range(1, MAX_DEPTH + 1):
                children = []
                for prog in beam:
                    for name in self.names():
                        if nodes >= self.budget:
                            break
                        nodes += 1
                        cand = prog + (name,)
                        sig = self._train_sig(cand, task['train'])
                        if sig in seen:
                            continue
                        seen.add(sig)
                        if sig == target and verify(task, cand, self.lib):
                            return cand, nodes
                        children.append((sum(1 for a, b in zip(sig, target)
                                             if a == b and a is not None), cand))
                children.sort(key=lambda sc: (-sc[0], sc[1]))
                beam = [c for _, c in children[:beam_width]]
                if not beam:
                    break
            return None, nodes

        if self.strategy == 'rand':
            while nodes < self.budget:
                prog = tuple(self.rng.choice(self.names())
                             for _ in range(self.rng.randint(1, MAX_DEPTH)))
                got = check(prog)
                if got is not None:
                    return got, nodes
            return None, nodes

        # bfs: e7 enumeration order, optionally re-ordered per tiebreak
        for depth in range(1, MAX_DEPTH + 1):
            combos = [tuple(c) for c in itertools.product(self.names(), repeat=depth)]
            if self.tiebreak == 'macro':
                combos.sort(key=lambda c: (-sum(1 for s in c if s in self.lib), c))
            elif self.tiebreak == 'novel':
                combos.sort(key=lambda c: (sum(pop_usage.get(s, 0) for s in c), c))
            # 'short': keep e7's canonical product order
            for prog in combos:
                if nodes >= self.budget:
                    return None, nodes
                got = check(prog)
                if got is not None:
                    return got, nodes
        return None, nodes

    def solves_without(self, task, macro_name, beam_width, cache_replay,
                       pop_usage):
        """Cheap counterfactual: can this mind still solve the task with the
        macro removed from its library and cache (same budget/strategy)?"""
        clone = Mind(self.id, self.lineage, self.strategy, self.budget,
                     self.memory_on, self.tiebreak, self.prims,
                     _rng('cf' + '|' + str(self.id) + '|' + str(task['desc']) + '|' + str(macro_name)),
                     spammer=self.spammer)
        clone.lib = {n: w for n, w in self.lib.items() if n != macro_name}
        clone.cache = [p for p in self.cache if macro_name not in p]
        prog, _ = clone.solve(task, beam_width, cache_replay, pop_usage)
        return prog is not None

    def remember(self, prog, cap):
        self.cache.append(tuple(prog))
        if len(self.cache) > cap:
            del self.cache[: len(self.cache) - cap]


def invented_windows(prog, lib, known_sigs):
    """All distinct length-2/3 windows of the flat solved program whose
    behaviour is new (not a known macro/prim signature, not identity)."""
    fp = flat(prog, lib)
    found, seen = [], set()
    for L in (2, 3):
        for i in range(len(fp) - L + 1):
            w = tuple(fp[i:i + L])
            if w in seen:
                continue
            seen.add(w)
            sig = signature(w)
            if sig not in known_sigs and sig != IDENTITY_SIG \
                    and all(s is not None for s in sig):
                found.append((w, sig))
    return found


@dataclass
class Cfg:
    pop_size: int = 8
    generations: int = 10
    tasks_per_gen: int = 8
    select_every: int = 3
    keep: int = 6
    lam: float = 1.0
    strong_budget: int = 1000
    weak_budget: int = 300
    lib_cap: int = 8
    adopt_per_gen: int = 2
    pub_per_gen: int = 2
    cache_cap: int = 40
    cache_replay: int = 20
    beam_width: int = 16
    fresh_lineage_prob: float = 0.15
    h1_pipes: int = 10
    spammer: bool = False
    credit_mode: str = 'usage'      # 'usage' | 'publication' | 'counterfactual'


POP_CONDITIONS = ('iso-best', 'share-rand', 'share-best', 'share-multi',
                  'share-multi-v2')


def gen_task(rng, domain, desc, prog):
    """Fresh example draws for one authored pipeline (mirrors e7 make_tasks)."""
    ex = []
    tries = 0
    while len(ex) < 16 and tries < 400:
        tries += 1
        x = dsl.GEN[domain](rng)
        o = safe_apply(prog, list(x), {})
        if o is not None and (isinstance(o, int) or len(o) > 0):
            ex.append((tuple(x), o))
    if len(ex) < 16:
        return None
    return dict(domain=domain, desc=desc, target=prog,
                train=ex[:8], test=ex[8:])


def train_pipelines(held):
    return [(dom, desc, prog) for dom, items in dsl.TARGETS.items()
            if dom != held for desc, prog in items]


def init_population(seed, cfg):
    rng = _rng('pop' + '|' + str(seed))
    minds = []
    for i in range(cfg.pop_size):
        drops = set(rng.sample(LISTFNS, 2))
        prims = [p for p in PRIMS if p not in drops]
        minds.append(Mind(i, i,
                          strategy=('bfs', 'beam', 'rand')[i % 3],
                          budget=cfg.strong_budget if i % 2 == 0 else cfg.weak_budget,
                          memory_on=(i % 4) in (0, 1),
                          tiebreak=('short', 'macro', 'novel')[i % 3],
                          prims=prims, rng=_rng('mind' + '|' + str(seed) + '|' + str(i))))
    if cfg.spammer:
        m = minds[-1]
        m.spammer = True
        m.strategy = 'rand'
        m.budget = cfg.weak_budget
    return minds


def spawn(parent, new_id, rng, cfg):
    fresh = rng.random() < cfg.fresh_lineage_prob
    if fresh:
        drops = set(rng.sample(LISTFNS, 2))
        child = Mind(new_id, 10 ** 6 + new_id,
                     rng.choice(('bfs', 'beam', 'rand')),
                     rng.choice((cfg.strong_budget, cfg.weak_budget)),
                     rng.random() < 0.5, rng.choice(('short', 'macro', 'novel')),
                     [p for p in PRIMS if p not in drops],
                     rng=_rng(('mind', new_id, rng.random())))
        return child
    budget = int(min(2000, max(150, parent.budget * rng.uniform(0.8, 1.2))))
    tiebreak = rng.choice(('short', 'macro', 'novel')) if rng.random() < 0.10 \
        else parent.tiebreak
    memory_on = (not parent.memory_on) if rng.random() < 0.05 else parent.memory_on
    prims = list(parent.prims)
    if rng.random() < 0.15:
        droppable = [p for p in prims if p in LISTFNS]
        drop = rng.choice(droppable)
        prims[prims.index(drop)] = rng.choice([p for p in LISTFNS if p not in prims])
    child = Mind(new_id, parent.lineage, parent.strategy, budget, memory_on,
                 tiebreak, prims, rng=_rng(('mind', new_id, rng.random())),
                 spammer=parent.spammer)
    child.lib = dict(parent.lib)  # cultural inheritance of representations
    return child


def run_population(condition, seed, cfg=None):
    import dataclasses
    cfg = cfg or Cfg()
    if condition == 'share-multi-v2':
        cfg = dataclasses.replace(cfg, credit_mode='counterfactual')
    sharing = condition.startswith('share')
    rule = condition.rsplit('-', 1)[1]
    if rule == 'v2':
        rule = 'multi'
    held = ('math', 'bio', 'code', 'physics')[seed % 4]
    pipes = train_pipelines(held)
    minds = init_population(seed, cfg)
    rng = _rng('run' + '|' + str(condition) + '|' + str(seed))

    pool = {}             # name -> dict(expansion, inventor_lineage, times_used, times_adopted)
    known_sigs = {signature((p,)) for p in PRIMS}
    lineage_credit, credit_totals, pub_windows = {}, {}, {}
    pop_usage = {}
    transfer_events = 0
    necessary_transfers = 0
    cf_resolves = 0
    spam_sel_total = 0
    spam_sel_survived = 0
    next_id = cfg.pop_size
    log = []

    def publish(mind, window, sig):
        name = 'p%d' % len(pool)
        pool[name] = dict(expansion=window, inventor_lineage=mind.lineage,
                          times_used=0, times_adopted=0)
        known_sigs.add(sig)
        mind.lib[name] = window
        pub_windows[mind.lineage] = pub_windows.get(mind.lineage, 0) + 1

    for gen in range(cfg.generations):
        task_rng = _rng('tasks' + '|' + str(seed) + '|' + str(gen))
        gen_tasks = [g for g in (gen_task(task_rng, *pipes[i])
                                 for i in task_rng.sample(range(len(pipes)),
                                                          cfg.tasks_per_gen))
                     if g is not None]
        gen_solves, attempts = 0, 0
        for mind in minds:
            pubs = 0
            for task in gen_tasks:
                attempts += 1
                prog, _ = mind.solve(task, cfg.beam_width, cfg.cache_replay,
                                     pop_usage)
                if prog is None:
                    continue
                gen_solves += 1
                mind.window_solves += 1
                mind.total_solves += 1
                for step in set(flat(prog, mind.lib)):
                    pop_usage[step] = pop_usage.get(step, 0) + 1
                credited = set()
                credited_macros = []
                for step in set(prog):
                    if step in mind.lib and step in pool:
                        rec = pool[step]
                        rec['times_used'] += 1
                        inv = rec['inventor_lineage']
                        if inv != mind.lineage:
                            credited_macros.append(step)
                        if inv != mind.lineage and inv not in credited:
                            credited.add(inv)
                            transfer_events += 1
                if cfg.credit_mode == 'counterfactual':
                    for step in credited_macros:
                        inv = pool[step]['inventor_lineage']
                        cf_resolves += 1
                        if not mind.solves_without(task, step, cfg.beam_width,
                                                   cfg.cache_replay, pop_usage):
                            necessary_transfers += 1
                            lineage_credit[inv] = lineage_credit.get(inv, 0) + 1
                            credit_totals[inv] = credit_totals.get(inv, 0) + 1
                else:
                    for step in credited_macros:
                        inv = pool[step]['inventor_lineage']
                        lineage_credit[inv] = lineage_credit.get(inv, 0) + 1
                        credit_totals[inv] = credit_totals.get(inv, 0) + 1
                mind.remember(prog, cfg.cache_cap)
                for window, sig in invented_windows(prog, mind.lib, known_sigs):
                    if pubs >= cfg.pub_per_gen or len(mind.lib) >= cfg.lib_cap:
                        break
                    if sharing:
                        publish(mind, window, sig)
                    else:
                        mind.lib['loc%d_%d' % (mind.id, len(mind.lib))] = window
                        known_sigs.add(sig)
                    pubs += 1
            if mind.spammer and sharing:
                for _ in range(cfg.pub_per_gen):
                    if len(mind.lib) >= cfg.lib_cap:
                        break
                    w = tuple(rng.choice(list(PRIMS))
                              for _ in range(rng.choice((2, 3))))
                    sig = signature(w)
                    if sig in known_sigs or sig == IDENTITY_SIG \
                            or any(s is None for s in sig):
                        continue
                    publish(mind, w, sig)

        if sharing:
            for mind in minds:
                for _ in range(cfg.adopt_per_gen):
                    if len(mind.lib) >= cfg.lib_cap:
                        break
                    choices = [(n, r) for n, r in pool.items()
                               if n not in mind.lib
                               and r['inventor_lineage'] != mind.lineage]
                    if not choices:
                        break
                    names, weights = zip(*[(n, 1 + r['times_used'])
                                           for n, r in choices])
                    pick = rng.choices(names, weights=weights, k=1)[0]
                    mind.lib[pick] = pool[pick]['expansion']
                    pool[pick]['times_adopted'] += 1

        counts = {}
        for m in minds:
            counts[m.lineage] = counts.get(m.lineage, 0) + 1
        shares = [c / len(minds) for c in counts.values()]
        import math as _m
        h = -sum(s * _m.log(s) for s in shares)
        log.append(dict(gen=gen,
                        train_solve_rate=gen_solves / max(1, attempts),
                        n_lineages=len(counts),
                        evenness=(h / _m.log(len(counts))) if len(counts) > 1 else 0.0,
                        n_reprs=len({(tuple(sorted(m.prims)), tuple(sorted(m.lib)))
                                     for m in minds}),
                        pool_size=len(pool),
                        mean_names=sum(len(m.names()) for m in minds) / len(minds)))

        if (gen + 1) % cfg.select_every == 0 and gen + 1 < cfg.generations:
            eff = pub_windows if cfg.credit_mode == 'publication' else lineage_credit
            if rule == 'best':
                ranked = sorted(minds, key=lambda m: (-m.window_solves, m.id))
            elif rule == 'multi':
                ranked = sorted(minds, key=lambda m: (
                    -(m.window_solves + cfg.lam * eff.get(m.lineage, 0)), m.id))
            else:
                ranked = list(minds)
                rng.shuffle(ranked)
            survivors = ranked[: cfg.keep]
            if cfg.spammer:
                spam_sel_total += 1
                spam_sel_survived += any(m.spammer for m in survivors)
            offspring = [spawn(survivors[i % len(survivors)], next_id + i, rng, cfg)
                         for i in range(len(minds) - len(survivors))]
            next_id += len(offspring)
            minds = survivors + offspring
            for m in minds:
                m.window_solves = 0
            lineage_credit, pub_windows = {}, {}

    # ---- frozen final evaluation ------------------------------------------
    eval_rng = _rng('eval' + '|' + str(seed))  # same draws for every condition
    h2 = []
    for desc, prog in dsl.TARGETS[held]:
        t = gen_task(eval_rng, held, desc, prog)
        if t:
            h2.append(t)
    h1 = []
    h1_pipes = _rng('h1' + '|' + str(seed)).sample(pipes, cfg.h1_pipes)
    for dom, desc, prog in h1_pipes:
        t = gen_task(eval_rng, dom, desc, prog)
        if t:
            h1.append(t)

    def evaluate(suite, pop):
        solved_any, per_mind, transfer_solves, total = 0, {}, 0, 0
        for task in suite:
            any_ok = False
            for mind in pop:
                prog, _ = mind.solve(task, cfg.beam_width, cfg.cache_replay,
                                     pop_usage)
                ok = prog is not None
                per_mind.setdefault(mind.id, []).append(ok)
                if ok:
                    total += 1
                    any_ok = True
                    if any(s in mind.lib and s in pool and
                           pool[s]['inventor_lineage'] != mind.lineage
                           for s in set(prog)):
                        transfer_solves += 1
            solved_any += any_ok
        ind = [sum(v) / len(v) for v in per_mind.values()]
        return dict(pop=solved_any / max(1, len(suite)),
                    ind=sum(ind) / max(1, len(ind)),
                    transfer_share=(transfer_solves / total) if total else 0.0,
                    n_tasks=len(suite))

    h1_eval, h2_eval = evaluate(h1, minds), evaluate(h2, minds)

    ablation = []
    if condition in ('share-multi', 'share-multi-v2'):
        credited = {r['inventor_lineage'] for r in pool.values()
                    if r['times_adopted'] > 0}
        for lin in sorted(credited):
            stripped = []
            for mind in minds:
                clone = Mind(mind.id, mind.lineage, mind.strategy, mind.budget,
                             mind.memory_on, mind.tiebreak, mind.prims,
                             mind.rng, spammer=mind.spammer)
                removed = {n for n in mind.lib
                           if n in pool and pool[n]['inventor_lineage'] == lin}
                clone.lib = {n: w for n, w in mind.lib.items() if n not in removed}
                clone.cache = [p for p in mind.cache
                               if not any(s in removed for s in p)]
                stripped.append(clone)
            h2_wo = evaluate(h2, stripped)
            ablation.append(dict(lineage=lin,
                                 attributed_credit=credit_totals.get(lin, 0),
                                 h2_pop_full=h2_eval['pop'],
                                 h2_pop_without=h2_wo['pop'],
                                 true_marginal=h2_eval['pop'] - h2_wo['pop']))

    return dict(condition=condition, seed=seed, held_out=held, log=log,
                final_n_lineages=log[-1]['n_lineages'],
                final_evenness=log[-1]['evenness'],
                final_pool=len(pool), final_names=log[-1]['mean_names'],
                transfer_events=transfer_events,
                necessary_transfers=necessary_transfers,
                cf_resolves=cf_resolves,
                credit_totals=credit_totals,
                h1=h1_eval, h2=h2_eval, ablation=ablation,
                spammer_survived=(any(m.spammer for m in minds)
                                  if cfg.spammer else None),
                spammer_selections_survived=(spam_sel_survived
                                             if cfg.spammer else None),
                spammer_selections_total=(spam_sel_total
                                          if cfg.spammer else None))


def run_e7lib(seed, cfg=None):
    """Anchored e7 baseline: e7's learn() on the training fold, single search
    at e7's main budget 1000 on the same paired evaluation draws."""
    import library as e7lib
    cfg = cfg or Cfg()
    held = ('math', 'bio', 'code', 'physics')[seed % 4]
    tasks = dsl.make_tasks(0)
    train = [t for t in tasks if t['domain'] != held]
    lib, _log = e7lib.learn(train, cfg.strong_budget, seed=0)
    eval_rng = _rng('eval' + '|' + str(seed))
    h2, h1 = [], []
    for desc, prog in dsl.TARGETS[held]:
        t = gen_task(eval_rng, held, desc, prog)
        if t:
            h2.append(t)
    pipes = train_pipelines(held)
    for dom, desc, prog in _rng('h1' + '|' + str(seed)).sample(pipes, cfg.h1_pipes):
        t = gen_task(eval_rng, dom, desc, prog)
        if t:
            h1.append(t)

    def frac(suite, lib_):
        c = 0
        for t in suite:
            p, _ = dsl.solve(t, lib_, cfg.strong_budget)
            c += p is not None and verify(t, p, lib_)
        return c / max(1, len(suite))

    return dict(condition='e7-lib', seed=seed, held_out=held,
                n_macros=len(lib),
                h1=dict(pop=frac(h1, lib), ind=frac(h1, lib)),
                h2=dict(pop=frac(h2, lib), ind=frac(h2, lib)))


def run_e7lib8(seed, cfg=None):
    """Equal-attempts e7 baseline: 8 independently learned e7 libraries
    (learn seeds 0..7), population score = any of 8 solves - matches the 8
    attempts per task the population arms get."""
    import library as e7lib
    cfg = cfg or Cfg()
    held = ('math', 'bio', 'code', 'physics')[seed % 4]
    tasks = dsl.make_tasks(0)
    train = [t for t in tasks if t['domain'] != held]
    libs = [e7lib.learn(train, cfg.strong_budget, seed=i)[0] for i in range(8)]
    eval_rng = _rng('eval' + '|' + str(seed))
    h2 = []
    for desc, prog in dsl.TARGETS[held]:
        t = gen_task(eval_rng, held, desc, prog)
        if t:
            h2.append(t)
    pipes = train_pipelines(held)
    h1 = []
    for dom, desc, prog in _rng('h1' + '|' + str(seed)).sample(pipes, cfg.h1_pipes):
        t = gen_task(eval_rng, dom, desc, prog)
        if t:
            h1.append(t)

    def stats(suite):
        per_lib = []
        solved_any = 0
        for t in suite:
            oks = []
            for lib in libs:
                p, _ = dsl.solve(t, lib, cfg.strong_budget)
                oks.append(p is not None and verify(t, p, lib))
            per_lib.append(oks)
            solved_any += any(oks)
        inds = [sum(oks[i] for oks in per_lib) / max(1, len(per_lib))
                for i in range(len(libs))]
        return dict(pop=solved_any / max(1, len(suite)),
                    ind=sum(inds) / max(1, len(inds)))

    return dict(condition='e7-lib-8', seed=seed, held_out=held,
                n_macros=sum(len(l) for l in libs), h1=stats(h1), h2=stats(h2))
