"""Row 692 Mob Programming: executable tests. Loads the module by file path so the
test needs only the standard library (no package __init__ imports)."""
import importlib.util
import pathlib

import pytest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/mob_programming692.py"


def _load():
    spec = importlib.util.spec_from_file_location("mob_programming692", _P)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load()
TEAM = ["ana", "bo", "cy", "di"]


def plan(**kw):
    a = dict(participants=TEAM, task="fix flaky checkout test", session_minutes=60, rotation_minutes=10)
    a.update(kw)
    return M.plan_mob_session(**a)


def test_one_driver_one_navigator_rest_in_mob_per_turn():
    for t in plan()["turns"]:
        assert t["driver"] != t["navigator"]
        assert sorted([t["driver"], t["navigator"], *t["mob"]]) == sorted(TEAM)


def test_navigator_becomes_next_driver_and_driver_goes_to_back():
    t = plan()["turns"]
    assert [x["driver"] for x in t[:5]] == ["ana", "bo", "cy", "di", "ana"]
    assert t[0]["navigator"] == "bo" and t[1]["driver"] == "bo"
    assert t[0]["mob"] == ["cy", "di"] and t[1]["mob"] == ["di", "ana"]


def test_turns_are_contiguous_and_cover_session():
    p = plan()
    t = p["turns"]
    assert t[0]["start_minute"] == 0 and t[-1]["end_minute"] == 60
    for a, b in zip(t, t[1:]):
        assert a["end_minute"] == b["start_minute"]
    assert len(t) == 6


def test_short_last_turn():
    t = plan(session_minutes=25)["turns"]
    assert [x["minutes"] for x in t] == [10, 10, 5]


def test_driver_minutes_sum_to_session_minutes_and_fairness():
    p = plan(session_minutes=40)
    assert sum(p["driver_minutes"].values()) == 40
    assert p["driver_minutes"] == {"ana": 10, "bo": 10, "cy": 10, "di": 10}
    assert p["driver_minutes_spread"] == 0
    p2 = plan(session_minutes=50)
    assert p2["driver_minutes_spread"] == 10 and p2["everyone_drives"] is True


def test_start_driver_selectable():
    assert plan(start_driver="cy")["turns"][0]["driver"] == "cy"
    assert plan(start_driver="cy")["turns"][0]["navigator"] == "di"


def test_start_driver_must_be_participant():
    with pytest.raises(ValueError, match="start_driver"):
        plan(start_driver="zed")


def test_mob_needs_three_or_more_participants():
    with pytest.raises(ValueError, match="at least 3"):
        plan(participants=["ana", "bo"])


def test_duplicate_or_blank_participants_rejected():
    with pytest.raises(ValueError, match="unique"):
        plan(participants=["ana", "ana", "bo"])
    with pytest.raises(ValueError, match="non-empty"):
        plan(participants=["ana", " ", "bo"])


def test_missing_task_and_bad_numbers_rejected():
    with pytest.raises(ValueError, match="task"):
        plan(task="  ")
    with pytest.raises(ValueError, match="rotation_minutes"):
        plan(rotation_minutes=0)
    with pytest.raises(ValueError, match="session_minutes"):
        plan(session_minutes=-5)
    with pytest.raises(ValueError, match="rotation_minutes"):
        plan(rotation_minutes=61)
    with pytest.raises(ValueError, match="rotation_minutes"):
        plan(rotation_minutes=True)


def test_breaks_inserted_at_turn_boundaries_not_at_end():
    p = plan(session_minutes=60, rotation_minutes=10, break_every_minutes=30, break_minutes=5)
    kinds = [x["kind"] for x in p["turns"]]
    assert kinds == ["turn"] * 3 + ["break"] + ["turn"] * 3
    b = p["turns"][3]
    assert (b["start_minute"], b["end_minute"]) == (30, 35)
    assert p["turns"][4]["start_minute"] == 35 and p["total_wall_minutes"] == 65
    assert sum(p["driver_minutes"].values()) == 60
    assert p["turns"][-1]["kind"] == "turn"


def test_break_does_not_skip_driver_rotation():
    p = plan(break_every_minutes=30, break_minutes=5)
    drivers = [x["driver"] for x in p["turns"] if x["kind"] == "turn"]
    assert drivers == ["ana", "bo", "cy", "di", "ana", "bo"]


def test_break_params_validated():
    with pytest.raises(ValueError, match="break_minutes"):
        plan(break_every_minutes=30, break_minutes=0)
    with pytest.raises(ValueError, match="break_every_minutes"):
        plan(break_every_minutes=0)


def test_plan_is_deterministic_and_does_not_mutate_input():
    team = list(TEAM)
    a = M.plan_mob_session(team, "t", 30, 10)
    b = M.plan_mob_session(team, "t", 30, 10)
    assert a == b and team == TEAM


def test_single_task_recorded_and_review_flag():
    p = plan()
    assert p["task"] == "fix flaky checkout test" and p["method"] == "mob_programming"
    assert p["human_review_required"] is True


def test_audit_clean_log():
    log = [{"driver": d, "start_minute": i * 10, "end_minute": i * 10 + 10} for i, d in enumerate(TEAM)]
    r = M.audit_session_log(log, TEAM)
    assert r["ok"] is True and r["violations"] == [] and r["driver_minutes"]["cy"] == 10


def test_audit_detects_overlap_two_drivers_at_once():
    log = [{"driver": "ana", "start_minute": 0, "end_minute": 10}, {"driver": "bo", "start_minute": 5, "end_minute": 15}]
    r = M.audit_session_log(log, TEAM)
    assert r["ok"] is False and any(v["code"] == "overlap" for v in r["violations"])


def test_audit_detects_unknown_driver_and_bad_interval():
    r = M.audit_session_log([{"driver": "zed", "start_minute": 0, "end_minute": 5}], TEAM)
    assert any(v["code"] == "unknown_driver" for v in r["violations"])
    r = M.audit_session_log([{"driver": "ana", "start_minute": 5, "end_minute": 5}], TEAM)
    assert any(v["code"] == "bad_interval" for v in r["violations"])


def test_audit_detects_driver_hogging_and_never_drove():
    log = [{"driver": "ana", "start_minute": 0, "end_minute": 40}, {"driver": "bo", "start_minute": 40, "end_minute": 50}]
    r = M.audit_session_log(log, TEAM, max_driver_share=0.5)
    codes = {v["code"] for v in r["violations"]}
    assert "driver_share_exceeded" in codes and "never_drove" in codes
    assert r["never_drove"] == ["cy", "di"]


def test_audit_empty_log_is_not_ok():
    r = M.audit_session_log([], TEAM)
    assert r["ok"] is False and r["violations"][0]["code"] == "empty_log"


def test_audit_share_exactly_at_limit_is_allowed():
    t3 = ["ana", "bo", "cy"]
    log = [{"driver": "ana", "start_minute": 0, "end_minute": 20},
           {"driver": "bo", "start_minute": 20, "end_minute": 30},
           {"driver": "cy", "start_minute": 30, "end_minute": 40}]
    assert M.audit_session_log(log, t3, max_driver_share=0.5)["ok"] is True

@pytest.mark.parametrize('kw',[{'session_minutes':1441},{'participants':[str(i)for i in range(33)]},{'task':'x'*2001},{'break_minutes':1441},{'session_minutes':1440,'rotation_minutes':1,'break_every_minutes':1}])
def test_plan_caps_refuse(kw):
 with pytest.raises(ValueError):plan(**kw)

def test_plan_exact_caps_and_names():
 assert len(plan(participants=[str(i)for i in range(32)],task='x'*2000,session_minutes=1440,rotation_minutes=1)['turns'])==1440
 assert plan(participants=['a'*200,'bo','cy'],break_minutes=1440)['human_review_required']
 with pytest.raises(ValueError):plan(participants=['a'*201,'bo','cy'])

@pytest.mark.parametrize('value',[0,True,float('nan'),float('inf'),'x',None,[],1.1])
def test_share_strict_range(value):
 with pytest.raises(ValueError):M.audit_session_log([],TEAM,value)

@pytest.mark.parametrize('log',[5,None,'x',{},[None],[5],[{'driver':[],'start_minute':0,'end_minute':1}],[{'driver':'ana','start_minute':0,'end_minute':1,'extra':0}]])
def test_log_shape_valueerror(log):
 with pytest.raises(ValueError):M.audit_session_log(log,TEAM)

@pytest.mark.parametrize('field',['start_minute','end_minute'])
@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),'x',[],None])
def test_log_time_finite_exact(field,value):
 entry={'driver':'ana','start_minute':0,'end_minute':10};entry[field]=value
 with pytest.raises(ValueError):M.audit_session_log([entry],TEAM)

@pytest.mark.parametrize('value',[0,True,float('nan'),float('inf'),'x'])
def test_unused_break_still_checked(value):
 with pytest.raises(ValueError):plan(break_minutes=value)

@pytest.mark.parametrize('control',['\x00','\x81','\u200b','\u2028','\u2029'])
def test_task_and_name_controls(control):
 for kw in ({'task':'x'+control},{'participants':['ana'+control,'bo','cy']},{'start_driver':'ana'+control}):
  with pytest.raises(ValueError):plan(**kw)
 with pytest.raises(ValueError):M.audit_session_log([{'driver':'ana'+control,'start_minute':0,'end_minute':1}],TEAM)

def test_padded_driver_matches_normalized_participants_and_honesty():
 log=[{'driver':' '+d+' ','start_minute':i*10,'end_minute':i*10+10}for i,d in enumerate(TEAM)]
 out=M.audit_session_log(log,[' '+d+' 'for d in TEAM]);assert out['ok']
 for result in (out,plan(),M.audit_session_log([],TEAM)):
  assert result['session_executed'] is False and result['evidence_independently_verified'] is False

class L(list):pass
class D(dict):pass
class S(str):pass
class I(int):pass
@pytest.mark.parametrize('kw',[{'participants':L(TEAM)},{'task':S('task')},{'session_minutes':I(60)},{'start_driver':S('ana')}])
def test_plan_subclasses_refused(kw):
 with pytest.raises(ValueError):plan(**kw)

def test_log_count_and_time_boundaries():
 log=[{'driver':'ana','start_minute':0,'end_minute':1}]*2000
 assert M.audit_session_log(log,TEAM)['human_review_required']
 with pytest.raises(ValueError):M.audit_session_log(log+[{}],TEAM)
 with pytest.raises(ValueError):M.audit_session_log(L([]),TEAM)
 with pytest.raises(ValueError):M.audit_session_log([D(log[0])],TEAM)
 assert M.audit_session_log([{'driver':'ana','start_minute':999999,'end_minute':1000000}],TEAM)
 with pytest.raises(ValueError):M.audit_session_log([{'driver':'ana','start_minute':0,'end_minute':1000001}],TEAM)

def test_exact_turn_count_boundary():
 assert len(plan(session_minutes=1334,rotation_minutes=1,break_every_minutes=2)['turns'])==2000
 with pytest.raises(ValueError):plan(session_minutes=1335,rotation_minutes=1,break_every_minutes=2)

def test_caps_beat_content_errors_and_huge_numeric_safe():
 with pytest.raises(ValueError,match='count cap'):plan(participants=['x\u200b']*33,task='x\u200b')
 with pytest.raises(ValueError,match='raw text cap'):plan(task='x'*2001,participants=['x\u200b','bo','cy'])
 with pytest.raises(ValueError):plan(session_minutes=10**9)
 with pytest.raises(ValueError):M.audit_session_log([],TEAM,10**400)
 with pytest.raises(ValueError):M.audit_session_log([{'driver':'ana','start_minute':0,'end_minute':10**400}],TEAM)

def test_odd_turn_cap_and_valid_log_overcap():
 with pytest.raises(ValueError,match='turns'):plan(session_minutes=1001,rotation_minutes=1,break_every_minutes=1)
 e={'driver':'ana','start_minute':0,'end_minute':1}
 with pytest.raises(ValueError,match='count cap'):M.audit_session_log([e]*2001,TEAM)

def test_log_key_shape_and_early_count_precedence():
 with pytest.raises(ValueError,match='key cap'):M.audit_session_log([{'driver':'ana','start_minute':0,'end_minute':1,5:0}],TEAM)
 with pytest.raises(ValueError):M.audit_session_log([{'driver':'ana','start_minute':0}],TEAM)

def test_names_strip_consistently_on_both_surfaces():
 assert plan(participants=[' ana ','bo','cy'])['participants']==['ana','bo','cy']
 out=M.audit_session_log([{'driver':' ana ','start_minute':0,'end_minute':1}],TEAM)
 assert not any(v['code']=='unknown_driver'for v in out['violations'])


def test_audit_participant_cap_independent_of_plan():
 with pytest.raises(ValueError,match='count cap'):
  M.audit_session_log([], [str(i)for i in range(33)])


@pytest.mark.parametrize('start,drivers',[('di',['di','el','ana','bo','cy','di','el']),('el',['el','ana','bo','cy','di','el','ana'])])
def test_start_driver_fourth_fifth_exact_sequence(start,drivers):
 out=plan(participants=['ana','bo','cy','di','el'],start_driver=start,session_minutes=7,rotation_minutes=1)
 assert [t['driver']for t in out['turns']]==drivers


def test_uneven_driver_minutes_exact_attribution():
 assert plan(session_minutes=10,rotation_minutes=3)['driver_minutes']=={'ana':3,'bo':3,'cy':3,'di':1}


def test_everyone_drives_false_when_session_too_short():
 out=plan(session_minutes=5,rotation_minutes=3)
 assert out['everyone_drives'] is False
 assert out['driver_minutes']=={'ana':3,'bo':2,'cy':0,'di':0}


def test_share_boundaries_rounding_and_empty_never_drove():
 log=[{'driver':'ana','start_minute':0,'end_minute':2},{'driver':'bo','start_minute':2,'end_minute':3}]
 assert not any(v['code']=='driver_share_exceeded'for v in M.audit_session_log(log,TEAM,1.0)['violations'])
 for value in (0,1.0000001):
  with pytest.raises(ValueError):M.audit_session_log(log,TEAM,value)
 out=M.audit_session_log(log,TEAM,.5)
 assert next(v for v in out['violations']if v['code']=='driver_share_exceeded')=={'code':'driver_share_exceeded','driver':'ana','share':.6667}
 assert M.audit_session_log([],TEAM)['never_drove']==TEAM
