import datetime as dt
from types import SimpleNamespace as NS
from app.modules.m20_general_cognitive_worker.episode_outcome_metacognition import collect_action_outcomes, gate_from_episodes

# NOTE: NS stand-ins carry the same attribute names as schemas.Episode/ActionRecord
# (tool, succeeded, outcome_unknown, started_at); real pydantic models were not
# importable in this environment, so this is an interface-compat test, not an Episode test.
T = dt.datetime(2026, 10, 15, 12, 0)


def act(tool, ok, i, unk=False):
    return NS(tool=tool, succeeded=ok, outcome_unknown=unk, started_at=T + dt.timedelta(minutes=i))


def test_replay_counts_exclude_unknown_and_order_by_start():
    eps = [NS(actions=[act("send", True, 5), act("send", False, 1), act("send", True, 9, unk=True)]),
           NS(actions=[act("fetch", True, 2), NS(tool="", succeeded=True, outcome_unknown=False, started_at=T)])]
    rows, st = collect_action_outcomes(eps)
    assert [r[1:] for r in rows] == [("send", False), ("fetch", True), ("send", True)]
    assert st == {"counted": 3, "unknown_excluded": 1, "malformed_skipped": 1}
    g, _ = gate_from_episodes(eps)
    rep = g.learner.report()
    assert rep["send"]["wins"] == 1 and rep["send"]["losses"] == 1 and rep["fetch"]["wins"] == 1


def test_gate_decision_from_history_and_no_execution():
    eps = [NS(actions=[act("good", True, i) for i in range(60)] + [act("thin", True, 100), act("thin", True, 101)])]
    g, st = gate_from_episodes(eps)
    d = g.decide("high")
    assert d["action"] == "eligible_pending_authority" and d["strategy"] == "good"
    assert {t["strategy"]: t["n"] for t in d["table"]} == {"good": 60, "thin": 2}
    r = g.learner.run(1, lambda t, x: True)  # observation-only: execution refused, recorded as failure
    assert r["success"] is False and "observation-only" in r["error"]


def test_empty_history_rejected():
    for eps in ([], [NS(actions=[])], [NS(actions=[act("x", True, 0, unk=True)])]):
        try: gate_from_episodes(eps); assert False
        except ValueError: pass


def test_v5_second_audit_timestamp_sorting():
    ep=NS(actions=[NS(tool='t',succeeded=True,started_at=None),NS(tool='u',succeeded=False,started_at=None)])
    assert collect_action_outcomes([ep])[0]==[(None,'t',True),(None,'u',False)]
    ep.actions[1].started_at=1
    assert collect_action_outcomes([ep])[0]==[(1,'u',False),(None,'t',True)]


def test_v5_episode_nonbool_outcome_admission():
    ep=NS(actions=[NS(tool='t',succeeded=1,started_at=1),NS(tool='u',succeeded=0,started_at=2)])
    rows,stats=collect_action_outcomes([ep])
    assert rows==[] and stats['malformed_skipped']==2
