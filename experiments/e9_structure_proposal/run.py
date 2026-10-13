"""Paired replay. Run as python experiments/e9_structure_proposal/run.py --output DIR.

Tuning must use development rows only. No hyperparameters selected from heldout
results. Fixed settings before first benchmark: beam 48, two binary nodes,
4 initial observations, 12 intervention budget, 3 seeds, worlds seed 73.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
if __package__:
    from .engine import learn, SETTINGS
    from .worlds import generate
else:
    from engine import learn, SETTINGS
    from worlds import generate

POLICIES = (("beam_random", False, "random"), ("beam_eig_cost", False, "eig_cost"),
            ("exhaustive_random", True, "random"), ("exhaustive_eig_cost", True, "eig_cost"))


def run_schedule(count, seeds):
    """Randomization is generated before reading worlds, with a separate seed.

    Schedule inputs are run counts only, never table/hash/world labels. Costs
    stay paired across seeds and policies for each position in the suite.
    """
    rng = np.random.default_rng(2026101309)
    schedule = []
    for _ in range(count):
        costs = 1 + 4 * rng.random(32)
        runs = []
        for _ in range(seeds):
            run_id, learner_seed, initial_seed, noise_seed = map(
                int, rng.integers(0, 2**62, size=4))
            initial_rng = np.random.default_rng(initial_seed)
            initial_x = initial_rng.choice(32, 4, replace=False)
            initial_uniform = initial_rng.random(4)
            runs.append(dict(run_id=run_id, learner_seed=learner_seed,
                             initial_x=initial_x, initial_uniform=initial_uniform,
                             noise_seed=noise_seed))
        schedule.append((costs, runs))
    return schedule


def benchmark(worlds, seeds=3, budget=12, noise=0.0):
    rows = []
    schedule = run_schedule(len(worlds), seeds)
    for wi, w in enumerate(worlds):
        table = w["table"]
        costs, runs = schedule[wi]
        for seed, spec in enumerate(runs):
            # Exogenous unbiased input observations. The initial cost is omitted
            # equally for all policies; no claim about passive confounding.
            initial = [(int(s), ((table >> int(s)) & 1) ^ int(u < noise))
                       for s, u in zip(spec["initial_x"], spec["initial_uniform"])]
            for name, exhaustive, policy in POLICIES:
                # Per-setting/per-visit noise streams pair policies despite their
                # different queries; a policy cannot peek at future noise.
                visits = np.zeros(32, dtype=int)
                noise_uniforms = np.random.default_rng(spec["noise_seed"]).random((32, budget + 1))
                def query(s):
                    visit = int(visits[s]); visits[s] += 1
                    flip = noise_uniforms[s, visit] < noise
                    return ((table >> s) & 1) ^ int(flip)
                result = learn(initial, costs, spec["learner_seed"], query=query, policy=policy,
                               exhaustive=exhaustive, noise=noise, budget=budget)
                predicted = result.pop("table")
                accuracy = 0.0 if predicted is None else 1 - (predicted ^ table).bit_count() / 32
                rows.append(dict(world_id=w["world_id"], split=w["split"], seed=seed, policy=name,
                                 world_position=wi, run_id=spec["run_id"],
                                 learner_seed=spec["learner_seed"],
                                 outside=w["outside"], noise=noise, correct=predicted == table,
                                 truth_table=table, predicted_table=predicted,
                                 predictive_accuracy=accuracy, **result))
        if (wi + 1) % 10 == 0:
            print(f"completed {wi + 1}/{len(worlds)} worlds", flush=True)
    return rows


def summarize(rows):
    lines = []
    for outside, noise, split in sorted({(r["outside"], r["noise"], r["split"]) for r in rows}):
        subset = [r for r in rows if (r["outside"], r["noise"], r["split"]) == (outside, noise, split)]
        lines.append(f"outside={outside} noise={noise} split={split}")
        for name, _, _ in POLICIES:
            rs = [r for r in subset if r["policy"] == name]
            metrics = {key: float(np.mean([r[key] for r in rs])) for key in
                       ("correct", "predictive_accuracy", "cost", "queries", "search_evaluations", "exhausted")}
            lines.append(name + " n=" + str(len(rs)) + " " + json.dumps(metrics, sort_keys=True))
        # Bootstrap whole worlds, not individual seeds (E6 optimism fixed).
        for a, b in (("beam_eig_cost", "beam_random"),
                     ("beam_eig_cost", "exhaustive_eig_cost")):
            for key in ("correct", "predictive_accuracy", "cost", "search_evaluations"):
                paired = {(r["world_id"], r["seed"], r["policy"]): r[key] for r in subset}
                diffs = []
                for world in sorted({r["world_id"] for r in subset}):
                    seeds = sorted({r["seed"] for r in subset if r["world_id"] == world})
                    diffs.append(np.mean([paired[(world, s, a)] - paired[(world, s, b)] for s in seeds]))
                diffs = np.array(diffs)
                rng = np.random.default_rng(123)
                bs = diffs[rng.integers(0, len(diffs), (2000, len(diffs)))].mean(axis=1)
                lo, hi = np.quantile(bs, [.025, .975])
                lines.append(f"paired world-cluster {a} minus {b}: {key} {diffs.mean():+.6f} CI [{lo:+.6f},{hi:+.6f}]")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=int, default=100)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=12)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--outside", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    worlds = generate(91 if args.outside else 73, args.worlds, args.outside)
    rows = benchmark(worlds, args.seeds, args.budget, args.noise)
    text = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
    (args.output / "rows.jsonl").write_text(text)
    analysis = summarize(rows)
    (args.output / "analysis.txt").write_text(analysis)
    print(analysis)
    print("rows_sha256", hashlib.sha256(text.encode()).hexdigest())

if __name__ == "__main__":
    main()
