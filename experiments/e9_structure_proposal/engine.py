"""Observation-conditioned Boolean program synthesis plus the unmodified E6 EIG.

The learner knows a language, not a list of worlds or the hidden circuit. All
interventions set the five inputs, so this identifies input-output mechanisms,
not latent DAGs. Beam synthesis is approximate; its posterior is conditional on
surviving proposals and cannot certify realizability. Everything is synthetic.
"""
from dataclasses import dataclass
from itertools import product
import importlib.util
from pathlib import Path
import numpy as np

_spec = importlib.util.spec_from_file_location(
    "atlas_e6", Path(__file__).parents[1] / "e6_world_model_info_value/engine.py")
_e6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_e6)
SETTINGS = _e6.SETTINGS
MASK = (1 << len(SETTINGS)) - 1

@dataclass(frozen=True)
class Program:
    table: int
    code: str
    nodes: int


def atoms():
    out = [Program(0, "0", 0), Program(MASK, "1", 0)]
    for i in range(5):
        t = sum(int(x[i]) << s for s, x in enumerate(SETTINGS))
        out.extend([Program(t, f"x{i}", 0), Program(t ^ MASK, f"~x{i}", 0)])
    return out


def combine(a, b, op):
    t = {"and": a.table & b.table, "or": a.table | b.table,
         "xor": a.table ^ b.table}[op]
    return Program(t, f"({a.code} {op} {b.code})", a.nodes + b.nodes + 1)


def tabulate(programs):
    return np.array([[(p.table >> s) & 1 for s in range(32)] for p in programs], dtype=np.uint8)


def log_likelihood(programs, observations, noise):
    """History only, no oracle or world parameter. Retains contradictory repeats."""
    if not observations:
        return np.zeros(len(programs))
    mismatch = np.array([sum(((p.table >> s) & 1) != y for s, y in observations)
                         for p in programs])
    if noise == 0:
        return np.where(mismatch == 0, 0.0, -np.inf)
    return mismatch * np.log(noise) + (len(observations) - mismatch) * np.log1p(-noise)


def rank(programs, observations, noise):
    # Mismatch ranks even impossible intermediate subprograms: a subprogram need
    # not itself explain the final output. This heuristic can lose useful pieces.
    return sorted(programs, key=lambda p: (
        sum(((p.table >> s) & 1) != y for s, y in observations), p.nodes, p.code))


def synthesize(observations, noise=0.0, beam=48, max_nodes=2, exhaustive=False):
    """Generate syntax bottom-up, score observations, retain a per-size beam.

    No registry of hidden models is accepted. exhaustive=True disables the
    intermediate beam and is the finite-grammar upper baseline. Evaluation counts
    include generated expressions before semantic deduplication.
    """
    if not 0 <= noise < .5 or beam < 1 or not 0 <= max_nodes <= 3:
        raise ValueError("invalid noise, beam, or grammar bound")
    if any(not 0 <= s < 32 or y not in (0, 1) for s, y in observations):
        raise ValueError("observations must be (setting 0..31, binary output)")
    layers = {0: atoms()}
    seen = {p.table: p for p in layers[0]}
    evaluated = len(seen)
    for size in range(1, max_nodes + 1):
        layer = {}
        for left in range(size):
            right = size - 1 - left
            if left > right:
                continue
            for a, b in product(layers[left], layers[right]):
                for op in ("and", "or", "xor"):
                    evaluated += 1
                    p = combine(a, b, op)
                    if p.table not in seen and p.table not in layer:
                        layer[p.table] = p
        ordered = rank(list(layer.values()), observations, noise)
        # All generated final hypotheses enter the posterior; beam truncates only
        # the reusable intermediate building blocks, never via the hidden world.
        seen.update(layer)
        layers[size] = ordered if exhaustive else ordered[:beam]
    programs = list(seen.values())
    ll = log_likelihood(programs, observations, noise)
    if not np.isfinite(ll).any():
        return [], np.array([]), evaluated
    # Uniform prior over behavioral classes, matching E6. No MDL reward applied.
    post = np.exp(ll - ll.max())
    post /= post.sum()
    keep = post > 0
    return [p for p, k in zip(programs, keep) if k], post[keep], evaluated


def choose(post, tabs, policy, costs, observed, rng, noise):
    if policy == "random":
        available = [s for s in range(32) if noise > 0 or s not in observed]
        return int(rng.choice(available))
    gains = _e6.eig(post, tabs, noise)  # Exact selector reused, no replacement.
    gains = gains / costs if policy == "eig_cost" else gains
    if noise == 0:
        gains[list(observed)] = -np.inf
    return int(np.argmax(gains))


def learn(observations, costs, seed, *, query, policy="eig_cost", exhaustive=False,
          noise=0.0, budget=16, beam=48):
    """query(s) is the only world access. Its replies are added to observation history.

    Fixed query budget avoids turning a beam posterior into global confidence.
    Returns the final table, never accesses world identity to decide or stop.
    """
    costs = np.asarray(costs, dtype=float)
    if costs.shape != (32,) or not np.isfinite(costs).all() or (costs <= 0).any():
        raise ValueError("costs must be 32 finite positive values")
    if policy not in ("random", "eig", "eig_cost") or budget < 0:
        raise ValueError("invalid policy or budget")
    if noise == 0 and budget + len({s for s, _ in observations}) > 32:
        raise ValueError("noiseless budget exceeds unobserved settings")
    history = list(observations)
    rng = np.random.default_rng(seed)
    evaluations = 0
    spent = 0.0
    trajectory = []
    for _ in range(budget):
        programs, post, work = synthesize(history, noise, beam, exhaustive=exhaustive)
        evaluations += work
        if not programs:
            return dict(table=None, cost=spent, queries=len(trajectory), search_evaluations=evaluations,
                        exhausted=True, conditional_confidence=None, trajectory=trajectory)
        s = choose(post, tabulate(programs), policy, costs, {s for s, _ in history}, rng, noise)
        y = int(query(s))
        history.append((s, y))
        spent += float(costs[s])
        trajectory.append([s, y, len(programs)])
    programs, post, work = synthesize(history, noise, beam, exhaustive=exhaustive)
    evaluations += work
    if not programs:
        return dict(table=None, cost=spent, queries=len(trajectory), search_evaluations=evaluations,
                    exhausted=True, conditional_confidence=None, trajectory=trajectory)
    winner = int(np.argmax(post))
    return dict(table=programs[winner].table, code=programs[winner].code, cost=spent,
                queries=len(trajectory), search_evaluations=evaluations, exhausted=False,
                conditional_confidence=float(post[winner]), trajectory=trajectory)
