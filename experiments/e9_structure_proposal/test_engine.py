import ast
from pathlib import Path
import numpy as np
import pytest
import engine
from engine import atoms, synthesize, tabulate, choose, learn, combine


def test_generated_exhaustive_contains_composition():
    target = combine(combine(atoms()[2], atoms()[4], "xor"), atoms()[6], "and")
    programs, post, work = synthesize([], exhaustive=True)
    assert target.table in {p.table for p in programs}
    assert len(programs) > 70
    assert np.isclose(post.sum(), 1)
    assert work > len(programs)


def test_eig_is_actual_e6_function():
    assert engine._e6.eig.__module__ == "atlas_e6"
    tabs = np.array([[0] * 32, [0, 1] + [0] * 30], dtype=np.uint8)
    assert choose(np.ones(2) / 2, tabs, "eig_cost", np.ones(32), set(),
                  np.random.default_rng(0), 0) == 1


def test_no_world_import_or_candidate_argument():
    text = Path(engine.__file__).read_text()
    tree = ast.parse(text)
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert all("worlds" not in ast.unparse(n) for n in imports)
    import inspect
    assert "world" not in inspect.signature(synthesize).parameters
    assert "candidates" not in inspect.signature(synthesize).parameters


def test_observation_conditioning_and_exact_full_history():
    a = combine(combine(atoms()[2], atoms()[4], "xor"), atoms()[6], "and")
    observations = [(s, (a.table >> s) & 1) for s in range(32)]
    programs, post, _ = synthesize(observations, exhaustive=True)
    assert [p.table for p in programs] == [a.table]
    assert post.tolist() == [1.0]
    _, _, count = synthesize(observations, beam=4)
    _, _, full_count = synthesize(observations, exhaustive=True)
    assert count < full_count


def test_contradictions_not_silently_erased():
    assert not synthesize([(0, 0), (0, 1)], noise=0)[0]
    programs, posterior, _ = synthesize([(0, 0), (0, 1)], noise=.1)
    assert len(programs) > 0 and np.isclose(posterior.sum(), 1)


def test_only_query_callback_reads_truth_and_fixed_budget():
    calls = []
    def query(s):
        calls.append(s)
        return int(engine.SETTINGS[s, 0])
    result = learn([], np.ones(32), 1, query=query, budget=8)
    assert len(calls) == result["queries"] == 8
    assert len(set(calls)) == 8
    assert result["table"] == atoms()[2].table


def test_behavioral_split_no_overlap():
    from worlds import generate
    worlds = generate(73, 100)
    development = {w["table"] for w in worlds if w["split"] == "development"}
    holdout = {w["table"] for w in worlds if w["split"] == "heldout"}
    assert development and holdout and not development.intersection(holdout)


def test_outside_grammar_can_be_rejected():
    from worlds import generate
    w = generate(91, 1, outside=True)[0]
    programs, _, _ = synthesize([(s, (w["table"] >> s) & 1) for s in range(32)], exhaustive=True)
    assert programs == []


def test_tiny_replay_is_deterministic():
    from run import benchmark, summarize
    from worlds import generate
    worlds = generate(73, 2)
    a = benchmark(worlds, seeds=1, budget=3)
    b = benchmark(worlds, seeds=1, budget=3)
    assert a == b
    assert summarize(a) == summarize(b)


def test_saved_row_metrics_and_summaries():
    import json
    from run import summarize, run_schedule
    for folder in (Path(engine.__file__).parent / "results").iterdir():
        rows = [json.loads(line) for line in (folder / "rows.jsonl").read_text().splitlines()]
        assert summarize(rows) == (folder / "analysis.txt").read_text()
        max_position = max(row["world_position"] for row in rows)
        n_seeds = max(row["seed"] for row in rows) + 1
        schedule = run_schedule(max_position + 1, n_seeds)
        for r in rows:
            truth, pred = r["truth_table"], r["predicted_table"]
            assert r["correct"] == (truth == pred)
            expected = 0.0 if pred is None else 1 - (pred ^ truth).bit_count() / 32
            assert r["predictive_accuracy"] == expected
            costs, specs = schedule[r["world_position"]]
            assert specs[r["seed"]]["learner_seed"] == r["learner_seed"]
            assert np.isclose(r["cost"], sum(costs[s] for s, y, n in r["trajectory"]))
            assert r["queries"] == len(r["trajectory"])
            if r["noise"] == 0:
                assert all(y == ((truth >> s) & 1) for s, y, n in r["trajectory"])


def test_proposals_change_with_observations():
    a, _, _ = synthesize([(0, 0)], beam=4)
    b, _, _ = synthesize([(0, 1)], beam=4)
    assert {p.table for p in a} != {p.table for p in b}


def test_noisy_likelihood_counts_repeated_measurements():
    p = atoms()[0]
    likelihood = engine.log_likelihood([p], [(0, 0), (0, 0), (0, 1)], .1)[0]
    assert np.isclose(likelihood, 2 * np.log(.9) + np.log(.1))


@pytest.mark.parametrize("kwargs", [{"noise": -1}, {"noise": .5}, {"beam": 0}, {"max_nodes": 4}])
def test_invalid_synthesis_parameters(kwargs):
    with pytest.raises(ValueError):
        synthesize([], **kwargs)


def test_invalid_budget_and_costs():
    with pytest.raises(ValueError):
        learn([], np.ones(32), 1, query=lambda s: 0, budget=33)
    with pytest.raises(ValueError):
        learn([], np.zeros(32), 1, query=lambda s: 0)


def test_truth_permutation_cannot_change_randomization_or_fixed_transcript(monkeypatch):
    """Counterfactual boundary check, not a statistical proof from finite samples.

    Permute truth identities with all non-observation learner inputs unchanged.
    Actual observation values can differ, as they should. Hold those values and
    future callback replies fixed to test that no truth label changes queries.
    """
    import run
    from worlds import generate
    real_learn = run.learn
    captured = []
    def fixed_transcript_learn(observations, costs, seed, **kwargs):
        captured.append((costs.tolist(), seed, [s for s, y in observations]))
        kwargs["query"] = lambda s: int(engine.SETTINGS[s, 0])
        return real_learn([(s, int(engine.SETTINGS[s, 0])) for s, y in observations],
                          costs, seed, **kwargs)
    monkeypatch.setattr(run, "learn", fixed_transcript_learn)
    worlds = generate(73, 20)
    # Rotate rather than reverse: reversal can preserve symmetric bit patterns.
    permuted = worlds[1:] + worlds[:1]
    for bit in (1, 3):
        assert any(((a["table"] >> bit) & 1) != ((b["table"] >> bit) & 1)
                   for a, b in zip(worlds, permuted))
    first = run.benchmark(worlds, seeds=1, budget=3)
    initial_captured = list(captured); captured.clear()
    second = run.benchmark(permuted, seeds=1, budget=3)
    assert initial_captured == captured
    ignored = {"world_id", "split", "truth_table", "correct", "predictive_accuracy"}
    assert [{k: v for k, v in r.items() if k not in ignored} for r in first] == [
        {k: v for k, v in r.items() if k not in ignored} for r in second]


def test_schedule_has_no_world_or_truth_interface():
    import inspect
    from run import run_schedule
    assert list(inspect.signature(run_schedule).parameters) == ["count", "seeds"]
    schedule = run_schedule(2, 3)
    assert schedule[0][1][0]["learner_seed"] != schedule[1][1][0]["learner_seed"]
