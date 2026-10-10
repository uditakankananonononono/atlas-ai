"""ATLAS-U-1232 (owner row 193 substitute): tests for m19_idea_incubator/scaling_bench.py.
Authored BEFORE the implementation. AUTHORED NOT RUN by the builder.
Hermetic: in-memory ledger repository and an injected fake clock; no network, no real timing."""
from datetime import datetime,timezone
import pytest
from app.modules.m19_idea_incubator import scaling_bench as B
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository
from app.modules.m19_idea_incubator.schemas import *
OBS=datetime(2026,9,1,tzinfo=timezone.utc)
def svc():return LedgerService(MemoryIdeaRepository(),"bench-test")
def idea(s,title="t"):return s.create_idea(IdeaCreate(title=title,problem="p",proposed_solution="s")).id
def ev(s,i,pol,strength,conf):
    return s.add_evidence(i,EvidenceCreate(kind=EvidenceKind.OTHER,claim="c",source="s",polarity=pol,strength=strength,confidence=conf,observed_at=OBS))
SUP,CON,NEU=EvidencePolarity.SUPPORTS,EvidencePolarity.CONTRADICTS,EvidencePolarity.NEUTRAL
def fixture():
    s=svc();a=idea(s,"a");b=idea(s,"b");c=idea(s,"c")
    ev(s,a,SUP,.8,.5);ev(s,a,SUP,.8,.5);ev(s,a,CON,.6,.5);ev(s,a,NEU,1.0,1.0)   # 4 rows
    ev(s,b,SUP,.5,.5)                                                           # 1 row; c has none
    return s,a,b,c
class Clock:
    def __init__(s,step=2.0):s.t=0.0;s.step=step;s.calls=0
    def __call__(s):s.calls+=1;v=s.t;s.t+=s.step;return v

# ---- honesty ----
def test_module_docstring_has_verbatim_gap_and_unmet_owner_gap_and_states_no_solver():
    d=B.__doc__
    assert "Literal 1M-variable claim" in d and B.GAP_VERBATIM=="Literal 1M-variable claim"
    assert "1,000,000" in d and "NOT met" in d and "per-idea" in d
    assert "no matrix" in d.lower() and "no optimi" in d.lower()
    assert B.TARGET_VARIABLES==1_000_000

# ---- counting ----
def test_count_variables_counts_evidence_rows_across_ideas():
    s,a,b,c=fixture();assert B.count_variables(s)==5
def test_count_variables_empty_ledger_is_zero():assert B.count_variables(svc())==0

# ---- analysis against hand computed values ----
def test_analyze_portfolio_matches_hand_computed_noisy_or_values():
    s,a,b,c=fixture();r=B.analyze_portfolio(s)
    A=r["ideas"][a]
    assert A["supporting_count"]==2 and A["contradicting_count"]==1 and A["neutral_count"]==1
    assert A["support_score"]==pytest.approx(.64,abs=1e-9) and A["contradiction_score"]==pytest.approx(.3,abs=1e-9)
    assert A["net_score"]==pytest.approx(.34,abs=1e-9) and A["confidence"]==pytest.approx(.625,abs=1e-9)
    Bv=r["ideas"][b];assert Bv["support_score"]==pytest.approx(.25) and Bv["supporting_count"]==1
def test_idea_without_evidence_is_present_with_zero_scores_and_zero_variables():
    s,a,b,c=fixture();r=B.analyze_portfolio(s);C=r["ideas"][c]
    assert C["supporting_count"]==C["contradicting_count"]==C["neutral_count"]==0 and C["support_score"]==0 and C["confidence"]==0
    assert r["variables_analyzed"]==5 and r["ideas_analyzed"]==3
def test_analysis_equals_the_ledger_service_summary_for_every_idea():
    s,a,b,c=fixture();r=B.analyze_portfolio(s)
    for i in (a,b,c):assert r["ideas"][i]==s.evidence_summary(i).model_dump()
def test_variables_analyzed_comes_from_analysis_not_from_a_second_count():
    s,a,b,c=fixture();r=B.analyze_portfolio(s)
    assert r["variables_analyzed"]==sum(v["supporting_count"]+v["contradicting_count"]+v["neutral_count"] for v in r["ideas"].values())

# ---- decomposition ----
def test_chunked_analysis_is_identical_for_any_chunk_size():
    s,a,b,c=fixture();whole=B.analyze_portfolio(s)
    for k in (1,2,3,10):assert B.analyze_portfolio(s,chunk_size=k)==whole
def test_analysis_is_independent_of_idea_order():
    s,a,b,c=fixture();r1=B.analyze_ideas(s,[a,b,c]);r2=B.analyze_ideas(s,[c,b,a]);assert r1==r2
def test_one_ideas_evidence_does_not_change_another_ideas_result():
    s,a,b,c=fixture();before=B.analyze_ideas(s,[b])[b];ev(s,a,SUP,.9,.9);assert B.analyze_ideas(s,[b])[b]==before
def test_bad_chunk_size_rejected():
    s,*_=fixture()
    for bad in (0,-1,True,1.5):
        with pytest.raises(ValueError):B.analyze_portfolio(s,chunk_size=bad)
def test_analyze_ideas_unknown_idea_raises_lookup_error():
    with pytest.raises(LookupError):B.analyze_ideas(svc(),["nope"])
def test_verify_decomposition_passes_for_real_analyzer():
    s,*_=fixture();assert B.verify_decomposition(s,chunk_sizes=(1,2))==[]
def test_verify_decomposition_detects_an_analyzer_that_depends_on_chunking():
    s,a,b,c=fixture()
    def bad(service,ids):
        out=B.analyze_ideas(service,ids)
        if len(ids)>1:
            for v in out.values():v["support_score"]+=0.5
        return out
    m=B.verify_decomposition(s,chunk_sizes=(1,3),analyzer=bad);assert m and any("support_score" in x for x in m)

# ---- synthetic seeding ----
def test_seed_synthetic_creates_exact_counts_and_is_labelled_synthetic():
    s=svc();ids=B.seed_synthetic(s,n_ideas=4,evidence_per_idea=5,seed=1)
    assert len(ids)==4 and B.count_variables(s)==20 and all(len(s.repository.list_evidence(i))==5 for i in ids)
    assert B.SYNTHETIC_LABEL=="synthetic-seeded-not-real-ledger-data"
def test_seed_synthetic_is_deterministic_for_same_seed_and_differs_for_other_seed():
    def sig(seed):
        s=svc();B.seed_synthetic(s,3,4,seed=seed)
        return sorted((e.polarity.value,e.strength,e.confidence) for i in s.repository.list_ideas() for e in s.repository.list_evidence(i.id))
    assert sig(7)==sig(7) and sig(7)!=sig(8)
def test_seed_synthetic_values_are_valid_ledger_inputs_in_all_three_polarities():
    s=svc();B.seed_synthetic(s,10,10,seed=3)
    rows=[e for i in s.repository.list_ideas() for e in s.repository.list_evidence(i.id)]
    assert {e.polarity for e in rows}=={SUP,CON,NEU} and all(0<=e.strength<=1 and 0<=e.confidence<=1 for e in rows)
def test_seed_synthetic_rejects_nonpositive_or_non_int_sizes():
    for a,b in ((0,1),(1,0),(-1,2),(2,True),(1.5,2)):
        with pytest.raises(ValueError):B.seed_synthetic(svc(),a,b)

# ---- measurement ----
def test_measure_scaling_uses_injected_clock_exactly_twice_per_scale_and_computes_arithmetic_only():
    c=Clock(step=2.0);pts=B.measure_scaling(svc,[10,20],evidence_per_idea=5,clock=c)
    assert c.calls==4 and [p["variables_analyzed"] for p in pts]==[10,20] and [p["ideas_analyzed"] for p in pts]==[2,4]
    assert [p["elapsed_seconds"] for p in pts]==[2.0,2.0]
    assert pts[0]["seconds_per_variable"]==pytest.approx(0.2) and pts[1]["seconds_per_variable"]==pytest.approx(0.1)
    assert all(p["data_origin"]==B.SYNTHETIC_LABEL for p in pts)
def test_measure_scaling_seeding_is_not_inside_the_timed_window():
    seen=[]
    def clock():
        seen.append(None);return float(len(seen))
    calls=[]
    def make():
        s=svc();calls.append(len(seen));return s
    B.measure_scaling(make,[5],evidence_per_idea=5,clock=clock);assert calls==[0]
def test_measure_scaling_rejects_bad_scales_and_non_divisible_scales():
    for sc in ([],[0],[10,10],[20,10],[7],[True],[1.5]):
        with pytest.raises(ValueError):B.measure_scaling(svc,sc,evidence_per_idea=5,clock=Clock())
def test_measure_scaling_negative_elapsed_from_a_backwards_clock_is_an_error():
    ticks=iter([5.0,1.0])
    with pytest.raises(ValueError):B.measure_scaling(svc,[5],evidence_per_idea=5,clock=lambda:next(ticks))

# ---- report ----
def test_report_states_both_gaps_never_claims_1m_and_never_extrapolates():
    pts=B.measure_scaling(svc,[10,20],evidence_per_idea=5,clock=Clock());r=B.build_report(pts)
    assert r["literal_1m_claimed"] is False and r["target_variables"]==1_000_000 and r["target_met"] is False
    assert r["max_variables_measured"]==20 and r["gap_verbatim"]=="Literal 1M-variable claim"
    assert "NOT met" in r["unmet_owner_gap"] and r["unmet_owner_gap"]==B.UNMET_OWNER_GAP
    assert not any("extrapol" in k or "projected" in k or "estimate" in k for k in r) and r["points"]==pts
def test_report_growth_ratios_are_plain_arithmetic_between_consecutive_points():
    pts=B.measure_scaling(svc,[10,20,40],evidence_per_idea=5,clock=Clock());r=B.build_report(pts)
    assert r["growth"]==[{"from_variables":10,"to_variables":20,"variables_ratio":2.0,"elapsed_ratio":1.0},{"from_variables":20,"to_variables":40,"variables_ratio":2.0,"elapsed_ratio":1.0}]
def test_report_with_no_points_is_rejected():
    with pytest.raises(ValueError):B.build_report([])
def test_report_target_met_stays_false_even_if_a_point_reports_a_million_variables_because_synthetic():
    pt={"variables_analyzed":1_000_000,"ideas_analyzed":10,"elapsed_seconds":1.0,"seconds_per_variable":1e-6,"data_origin":B.SYNTHETIC_LABEL}
    r=B.build_report([pt]);assert r["target_met"] is False and r["literal_1m_claimed"] is False
def test_report_is_deterministic_json_serialisable():
    import json
    a=B.build_report(B.measure_scaling(svc,[10],evidence_per_idea=5,clock=Clock()));b=B.build_report(B.measure_scaling(svc,[10],evidence_per_idea=5,clock=Clock()))
    assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
