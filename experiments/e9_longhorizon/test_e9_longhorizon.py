from lh_tasks import Project, NMOD
from lh_agents import run_agent

def test_reference_passes_everything():
    P = Project(5, 3); ns = P.ref
    assert P.run(ns, P.vis) == 0 and P.run(ns, P.hid) == 0

def test_each_bug_fails_a_visible_test_and_buggy_program_fails():
    P = Project(6, 4)
    assert len(P.bugs) == 4
    for k, v in P.bugs.items():
        assert P.run(P.build({k: v}), P.vis) > 0
    assert P.run(P.build(P.bugs), P.vis) > 0

def test_restoring_originals_repairs():
    P = Project(7, 3)
    fixed = {k: P.original_of(k) for k in P.bugs}
    assert P.run(P.build(fixed), P.vis) == 0 and P.run(P.build(fixed), P.hid) == 0

def test_deterministic_generation():
    a, b = Project(9, 3), Project(9, 3)
    assert a.src == b.src and a.bugs == b.bugs and a.vis == b.vis

def test_edit_space_does_not_reveal_bugs():
    P = Project(8, 3); sp = P.edit_space()
    assert all(any(s == k for s, v, kind in sp) for k in P.bugs)
    # every site offers its original value, so a revert exists at every site (bugged or not)
    assert sum(1 for s, v, kind in sp if v == P.original_of(s)) == len({s for s, v, kind in sp})

def test_agent_runs_and_charges_cost():
    P = Project(10, 2)
    r = run_agent(P, "M", 0, maxb=400)
    assert r["evals"] <= 401 and r["tests"] >= r["evals"] * len(P.vis) - len(P.vis)
    if r["solved_vis"]: assert r["hid_fail"] is not None

def test_budget_curve_is_valid_for_anytime_agent():
    P = Project(11, 2); small = run_agent(P, "S_fl", 3, maxb=300); big = run_agent(P, "S_fl", 3, maxb=3000)
    if small["solved_vis"]: assert big["evals"] == small["evals"]

if __name__ == "__main__":  # fallback runner when pytest is unavailable
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
