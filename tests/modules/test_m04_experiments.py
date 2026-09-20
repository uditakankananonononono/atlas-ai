from app.modules.m04_research_scientist.experiments import ExperimentPlan, execute_experiment, monte_carlo


def test_simulation_repeats_and_manifest_is_content_addressed():
    plan = ExperimentPlan("exp", "coin is fair", "mean", {"iterations": 100}, 42, "report mean", "abc123")
    runner = lambda p, seed: monte_carlo(seed, p["iterations"], lambda rng: rng.random())
    left = execute_experiment(plan, runner, {"dataset": [1, 2]})
    right = execute_experiment(plan, runner, {"dataset": [1, 2]})
    assert left.outputs == right.outputs
    assert left.manifest.run_id == right.manifest.run_id
    assert left.sample_size == 100


def test_missing_metric_is_rejected():
    plan = ExperimentPlan("exp", "h", "effect", {}, 1, "plan", "v1")
    try:
        execute_experiment(plan, lambda params, seed: {})
    except ValueError as error:
        assert "primary metric" in str(error)
    else:
        raise AssertionError("missing metric accepted")
