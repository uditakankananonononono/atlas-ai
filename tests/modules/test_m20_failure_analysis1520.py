"""Row 1520 Failure Analysis: hermetic stdlib tests, exact-value pins, row-tagged refusals. Loads the module by path."""
import importlib.util
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/failure_analysis1520.py"
_spec = importlib.util.spec_from_file_location("failure_analysis1520", _SRC)
fa = importlib.util.module_from_spec(_spec)
sys.modules["failure_analysis1520"] = fa
_spec.loader.exec_module(fa)


def ev(i="E1", kind="photograph", desc="fracture surface photo"):
    return {"id": i, "kind": kind, "description": desc}


def hyp(i="H1", sup=("E1",), con=()):
    return {"id": i, "statement": "fatigue initiated at the notch",
            "supporting_evidence_ids": list(sup), "contrary_evidence_ids": list(con)}


def go(**over):
    d = {"problem_statement": "bracket failed in service",
         "evidence": [ev()],
         "hypotheses": [hyp()],
         "timeline": [{"at": "2026-01-04", "event": "failure reported"}],
         "preservation_actions": ["fracture surface sealed"]}
    d.update(over)
    return fa.plan(d)


def refused(fn, word):
    with pytest.raises(fa.FailError) as e:
        fn()
    assert str(e.value).startswith("FAIL1520: ")
    assert word in str(e.value)


def test_happy_path_exact():
    r = go()
    assert r["row"] == 1520 and r["analysis_type"] == "failure"
    assert r["problem_statement"] == "bracket failed in service"
    assert r["evidence_registered"] == 1
    assert r["hypotheses"] == [{"index": 0, "id": "H1",
                                "statement": "fatigue initiated at the notch",
                                "supporting_evidence_count": 1, "contrary_evidence_count": 0,
                                "net_support": 1, "status": "candidate_not_root_cause"}]
    assert r["hypotheses_supplied"] == 1
    assert r["unsupported_hypothesis_ids"] == []
    assert r["unreferenced_evidence_ids"] == []
    assert r["timeline_events_declared"] == 1 and r["preservation_actions_declared"] == 1
    assert r["root_cause_claimed"] is False and r["evidence_verified"] is False
    assert r["plan_only"] is True and r["test_executed"] is False
    assert len(r["limits"]) == 3


def test_bookkeeping_counts_exact():
    r = go(evidence=[ev("E1"), ev("E2", "log", "maintenance log"), ev("E3", "photo", "bench photo")],
           hypotheses=[hyp("H1", ("E1", "E2"), ("E3",)), hyp("H2", ())])
    assert [h["supporting_evidence_count"] for h in r["hypotheses"]] == [2, 0]
    assert [h["contrary_evidence_count"] for h in r["hypotheses"]] == [1, 0]
    assert [h["net_support"] for h in r["hypotheses"]] == [1, 0]
    assert r["unsupported_hypothesis_ids"] == ["H2"]
    assert r["unreferenced_evidence_ids"] == []


def test_unreferenced_evidence_sorted_exact():
    r = go(evidence=[ev("E2"), ev("E1"), ev("E3")], hypotheses=[hyp("H1", ("E3",))])
    assert r["unreferenced_evidence_ids"] == ["E1", "E2"]


def test_input_must_be_mapping():
    refused(lambda: fa.plan([1, 2]), "mapping")
    class Sneaky(dict):
        pass
    refused(lambda: fa.plan(Sneaky(problem_statement="x")), "mapping")


def test_missing_and_unknown_top_keys_refused():
    refused(lambda: go(problem_statement=None), "text")
    for k in ("problem_statement", "evidence", "hypotheses", "timeline", "preservation_actions"):
        d = {"problem_statement": "x", "evidence": [ev()], "hypotheses": [hyp()],
             "timeline": [], "preservation_actions": []}
        del d[k]
        refused(lambda d=d: fa.plan(d), "required")
    d = {"problem_statement": "x", "evidence": [ev()], "hypotheses": [hyp()],
         "timeline": [], "preservation_actions": [], "extra": 1}
    refused(lambda: fa.plan(d), "unknown key")
    d2 = {1: "x", "problem_statement": "x", "evidence": [ev()], "hypotheses": [hyp()],
          "timeline": []}
    refused(lambda: fa.plan(d2), "keys must be text")


def test_problem_statement_text_rules():
    refused(lambda: go(problem_statement=""), "non-empty")
    refused(lambda: go(problem_statement="   "), "non-empty")
    refused(lambda: go(problem_statement="x" * 513), "at most 512")
    go(problem_statement="x" * 512)
    refused(lambda: go(problem_statement="soft ad\u00adhyphen"), "Unicode")
    refused(lambda: go(problem_statement="word\u2060joiner"), "Unicode")
    refused(lambda: go(problem_statement=3), "text")


def test_evidence_register_rules():
    refused(lambda: go(evidence=[]), "1 to 50")
    refused(lambda: go(evidence=[ev()] * 51), "1 to 50")
    refused(lambda: go(evidence=[dict(ev(), extra=1)]), "unknown evidence key")
    refused(lambda: go(evidence=[{"id": "E1", "kind": "photo"}]), "required")
    refused(lambda: go(evidence=[ev("E1"), ev("E1")]), "unique")
    refused(lambda: go(evidence=[ev(kind="k" * 33)]), "at most 32")
    refused(lambda: go(evidence=[ev(desc="d" * 257)]), "at most 256")
    refused(lambda: go(evidence=[ev(i="i" * 65)]), "at most 64")
    refused(lambda: go(evidence=[ev(kind="bad\u200bkind")]), "Unicode")
    refused(lambda: go(evidence=[ev(i=1)]), "text")
    class Sneaky(dict):
        pass
    refused(lambda: go(evidence=[Sneaky(ev())]), "mapping")


def test_hypothesis_rules():
    refused(lambda: go(hypotheses=[]), "1 to 20")
    refused(lambda: go(hypotheses=[hyp("H%d" % n) for n in range(21)]), "1 to 20")
    refused(lambda: go(hypotheses=[dict(hyp(), extra=1)]), "unknown hypothesis key")
    refused(lambda: go(hypotheses=[hyp("H1"), hyp("H1")]), "unique")
    refused(lambda: go(hypotheses=[hyp("H1", ("NOPE",))]), "unknown evidence reference")
    refused(lambda: go(hypotheses=[hyp("H1", (), ("NOPE",))]), "unknown evidence reference")
    refused(lambda: go(hypotheses=[hyp("H1", ("E1", "E1"))]), "duplicate evidence reference")
    refused(lambda: go(hypotheses=[hyp("H1", ("E1",), ("E1",))]), "both supporting and contrary")
    refused(lambda: go(hypotheses=[hyp("H1", (1,))]), "text")
    refused(lambda: go(hypotheses=[dict(hyp(), statement="s" * 257)]), "at most 256")


def test_timeline_and_preservation_rules():
    refused(lambda: go(timeline=[{"at": "t", "event": "e"}] * 51), "0 to 50")
    refused(lambda: go(timeline=[{"at": "t"}]), "required")
    refused(lambda: go(timeline=[{"at": "t", "event": "e", "x": 1}]), "unknown timeline key")
    refused(lambda: go(timeline=[{"at": "t", "event": ""}]), "non-empty")
    refused(lambda: go(timeline=[{"at": "a" * 65, "event": "e"}]), "at most 64")
    refused(lambda: go(preservation_actions=["x"] * 21), "0 to 20")
    refused(lambda: go(preservation_actions=[""]), "non-empty")
    refused(lambda: go(preservation_actions=["p" * 257]), "at most 256")
    refused(lambda: go(preservation_actions=[1]), "text")
    go(timeline=[], preservation_actions=[])


def test_no_judgment_leaks():
    # a hypothesis with zero supporting references is bookkeeping-flagged, never refused
    r = go(hypotheses=[hyp("H1", ())])
    assert r["hypotheses"][0]["status"] == "candidate_not_root_cause"
    assert r["unsupported_hypothesis_ids"] == ["H1"]
    # many contrary references change counts only - still accepted, never adjudicated
    r2 = go(evidence=[ev("E1"), ev("E2")], hypotheses=[hyp("H1", (), ("E1", "E2"))])
    assert r2["hypotheses"][0]["net_support"] == -2
    assert r2["root_cause_claimed"] is False

@pytest.mark.parametrize('char',['\x00','\t','\u2028','\u2029'])
@pytest.mark.parametrize('field',['problem_statement','evidence_description'])
def test_closing_unicode_categories(char,field):
    with pytest.raises(fa.FailError) as exc:
        if field=='problem_statement':go(problem_statement='a'+char+'b')
        else:go(evidence=[ev(desc='a'+char+'b')])
    name='problem_statement' if field=='problem_statement' else 'evidence description'
    assert str(exc.value)=='FAIL1520: '+name+' carries a refused Unicode character'


def test_closing_str_subclass_refused():
    class Text(str):pass
    with pytest.raises(fa.FailError) as exc:go(problem_statement=Text('statement'))
    assert str(exc.value)=='FAIL1520: problem_statement must be text'

@pytest.mark.parametrize('field',['supporting_evidence_ids','contrary_evidence_ids','evidence','hypotheses','timeline','preservation_actions'])
def test_closing_list_subclasses_refused(field):
    class Items(list):
        def __iter__(self):raise AssertionError('subclass iterated')
    if field in ('supporting_evidence_ids','contrary_evidence_ids'):
        row=hyp();row[field]=Items(['E1'] if field=='supporting_evidence_ids' else [])
        call=lambda:go(hypotheses=[row])
        expected=field+' must be a list of at most 50 references'
    else:
        values={'evidence':[ev()],'hypotheses':[hyp()],'timeline':[],'preservation_actions':[]}
        call=lambda:go(**{field:Items(values[field])})
        expected={'evidence':'evidence must be a list of 1 to 50 items','hypotheses':'hypotheses must be a list of 1 to 20 items','timeline':'timeline must be a list of 0 to 50 events','preservation_actions':'preservation_actions must be a list of 0 to 20 entries'}[field]
    with pytest.raises(fa.FailError) as exc:call()
    assert str(exc.value)=='FAIL1520: '+expected


def test_closing_limits_not_aliased_across_results():
    baseline=list(go()['limits']);first=go();first['limits'][0]='changed';first['limits'].append('extra')
    assert go()['limits']==baseline
