import numpy as np
from engine import classes, run, SETTINGS

def test_classes_and_convergence():
    cl = classes(); assert len(cl) == 70
    costs = np.ones(len(SETTINGS))
    r = run(5, "eig", costs, 0.0, np.random.default_rng(0))
    assert r["correct"] and r["converged"] and r["steps"] <= 12

def test_noisy_run_stops_on_posterior():
    costs = np.ones(len(SETTINGS))
    r = run(3, "random", costs, 0.1, np.random.default_rng(1))
    assert r["converged"]
