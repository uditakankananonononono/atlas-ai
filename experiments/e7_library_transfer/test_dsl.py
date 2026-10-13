from dsl import make_tasks, solve, verify, safe_apply

def test_solver_finds_verified_program():
    t = next(t for t in make_tasks(0) if t["desc"] == "GC running count peak")
    p, n = solve(t, {}, 20000)
    assert p is not None and verify(t, p, {})

def test_macro_reaches_depth4_in_small_budget():
    t = next(t for t in make_tasks(0) if t["desc"] == "accumulated doubled velocity peak")
    assert solve(t, {}, 1000)[0] is None
    lib = {"m_cumsum_max": ("cumsum", "max")}
    p, n = solve(t, lib, 1000)
    assert p is not None and verify(t, p, lib)

def test_verify_rejects_wrong_program():
    t = make_tasks(0)[0]
    assert not verify(t, ("reverse",), {})
