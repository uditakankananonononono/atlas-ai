"""Focused tests for feature rows 388-399: durable planning & measurement entities."""
from datetime import datetime,timedelta,timezone
import pytest
from app.modules.m16_executive_dashboard import planning
from app.modules.m16_executive_dashboard.planning import WipLimitExceeded
from app.modules.m16_executive_dashboard.schemas import *
from app.modules.m16_executive_dashboard.service import Service
NOW=datetime.now(timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0)
class FakePlanningRepo:
    def __init__(self):self.items={};self.sprints={};self.ceremonies=[];self.retros=[];self.experiments={};self.roadmaps={}
    # dashboard protocol (unused here but Service touches them on some paths)
    def list_work_items(self,sprint_id=None,roadmap_id=None,status=None):
        out=list(self.items.values())
        if sprint_id is not None:out=[i for i in out if i.sprint_id==sprint_id]
        if roadmap_id is not None:out=[i for i in out if i.roadmap_id==roadmap_id]
        if status is not None:out=[i for i in out if i.status==status]
        return sorted(out,key=lambda i:(i.rank,i.created_at))
    def save_work_item(self,i):self.items[i.id]=i;return i
    def get_work_item(self,i):return self.items.get(i)
    def delete_work_item(self,i):return self.items.pop(i,None) is not None
    def save_sprint(self,s):self.sprints[s.id]=s;return s
    def get_sprint(self,i):return self.sprints.get(i)
    def list_sprints(self):return sorted(self.sprints.values(),key=lambda s:s.start)
    def save_ceremony(self,c):self.ceremonies.append(c);return c
    def list_ceremonies(self,sprint_id=None):return [c for c in self.ceremonies if sprint_id is None or c.sprint_id==sprint_id]
    def save_retrospective(self,r):self.retros.append(r);return r
    def list_retrospectives(self):return list(self.retros)
    def save_experiment(self,e):self.experiments[e.id]=e;return e
    def get_experiment(self,i):return self.experiments.get(i)
    def list_experiments(self):return list(self.experiments.values())
    def save_roadmap(self,r):self.roadmaps[r.id]=r;return r
    def get_roadmap(self,i):return self.roadmaps.get(i)
    def list_roadmaps(self):return list(self.roadmaps.values())
def svc():return Service(FakePlanningRepo())
def item(s,title,**kw):return s.create_work_item(WorkItemIn(title=title,**kw))
def sprint(s,name="S1",start=None,end=None):
    return s.create_sprint(SprintIn(name=name,start=start or NOW-timedelta(days=7),end=end or NOW+timedelta(days=7)))
def test_row_388_feature_prioritization_ranks_by_rice_with_inputs():
    s=svc()
    high=item(s,"big win",reach=1000,impact=2.0,confidence=.8,effort=2)
    low=item(s,"small win",reach=10,impact=1.0,confidence=.5,effort=5)
    incomplete=item(s,"no inputs")
    ranked=s.prioritization("rice")
    assert [r.item.id for r in ranked]==[high.id,low.id,incomplete.id]
    assert ranked[0].score==800.0 and ranked[0].formula=="reach * impact * confidence / effort"
    assert ranked[2].score is None and set(ranked[2].missing_inputs)>={"reach","impact","confidence","effort"}
    wsjf=s.prioritization("wsjf")
    assert all("value" in r.missing_inputs or r.score is not None for r in wsjf)
    with pytest.raises(ValueError):s.prioritization("bogus")
def test_row_389_roadmap_planning_sequences_items_by_week():
    s=svc()
    rm=s.create_roadmap(RoadmapIn(name="Q4",horizon_start=NOW,horizon_end=NOW+timedelta(days=90)))
    a=item(s,"a",roadmap_id=rm.id,planned_start=NOW+timedelta(days=3))
    b=item(s,"b",roadmap_id=rm.id,planned_start=NOW+timedelta(days=10))
    c=item(s,"c",roadmap_id=rm.id)
    view=s.roadmap_view(rm.id)
    lanes=list(view.lanes)
    assert lanes[-1]=="unplanned" and [i.id for i in view.lanes["unplanned"]]==[c.id]
    first_week=[i.id for i in view.lanes[lanes[0]]]
    assert a.id in first_week and b.id not in first_week
    with pytest.raises(ValueError):s.create_roadmap(RoadmapIn(name="bad",horizon_start=NOW,horizon_end=NOW))
def test_row_390_sprint_planning_lifecycle_single_active():
    s=svc();sp1=sprint(s,"S1");sp2=sprint(s,"S2")
    assert s.start_sprint(sp1.id).status=="active"
    with pytest.raises(ValueError):s.start_sprint(sp2.id)
    with pytest.raises(ValueError):s.start_sprint(sp1.id)
    assert s.close_sprint(sp1.id).status=="closed"
    assert s.start_sprint(sp2.id).status=="active"
    with pytest.raises(LookupError):s.close_sprint("missing")
def test_row_391_backlog_grooming_reorder_ready_and_stale():
    s=svc()
    a=item(s,"a");b=item(s,"b");c=item(s,"c")
    assert [i.rank for i in s.list_work_items()]==[1,2,3]
    moved=s.patch_work_item(c.id,WorkItemPatch(rank=1,status="ready"))
    assert moved.rank==1 and moved.status=="ready"
    stale=planning.stale_backlog([a.model_copy(update={"updated_at":NOW-timedelta(days=45)})],NOW)
    assert [i.id for i in stale]==[a.id]
    with pytest.raises(ValueError):s.patch_work_item(a.id,WorkItemPatch(status="sideways"))
def test_row_392_velocity_tracking_averages_closed_sprints():
    s=svc()
    sp1=sprint(s,"S1",NOW-timedelta(days=28),NOW-timedelta(days=14));sp2=sprint(s,"S2",NOW-timedelta(days=14),NOW-timedelta(days=1))
    for sp in(sp1,sp2):s.start_sprint(sp.id);s.close_sprint(sp.id)
    d1=item(s,"done1",estimate=5,sprint_id=sp1.id);s.patch_work_item(d1.id,WorkItemPatch(status="done"))
    d2=item(s,"done2",estimate=3,sprint_id=sp1.id);s.patch_work_item(d2.id,WorkItemPatch(status="done"))
    d3=item(s,"done3",estimate=8,sprint_id=sp2.id);s.patch_work_item(d3.id,WorkItemPatch(status="done"))
    report=s.velocity_report()
    assert [p.completed_points for p in report.sprints]==[8.0,8.0] and report.average_completed==8.0
    assert report.inputs["sprint_ids"]==[sp1.id,sp2.id]
    assert s.velocity_report().sprints[0].committed_points==8.0
def test_row_393_burndown_tracks_actual_vs_ideal_with_scope_note():
    s=svc();sp=sprint(s,"S1",NOW-timedelta(days=4),NOW+timedelta(days=6))
    a=item(s,"a",estimate=4,sprint_id=sp.id);b=item(s,"b",estimate=4,sprint_id=sp.id)
    s.patch_work_item(a.id,WorkItemPatch(status="done"))
    report=s.burndown(sp.id,NOW)
    assert report.series[0].total_committed==8 and report.series[0].ideal_remaining==8
    assert report.series[-1].actual_remaining<=8 and any("Ideal line is linear" in x for x in report.assumptions)
    done_days=[p for p in report.series if p.actual_remaining<8]
    assert done_days and all(p.actual_remaining==4 for p in done_days)
def test_row_394_kanban_board_columns_and_wip_limits():
    s=svc()
    items=[item(s,f"t{i}") for i in range(4)]
    for i in items[:3]:s.move_item(i.id,"in_progress")
    with pytest.raises(WipLimitExceeded):s.move_item(items[3].id,"in_progress")
    board=s.board()
    assert len(board.columns["in_progress"])==3 and len(board.columns["backlog"])==1
    done=s.move_item(items[0].id,"done")
    assert done.completed_at is not None
    assert s.move_item(items[3].id,"in_progress").status=="in_progress"
    with pytest.raises(ValueError):s.move_item(items[3].id,"mars")
def test_row_395_scrum_ceremonies_recorded_per_sprint():
    s=svc();sp=sprint(s)
    c=s.create_ceremony(CeremonyIn(sprint_id=sp.id,kind="planning",scheduled_at=NOW,notes="goal set",action_items=[{"text":"prepare board"}]))
    assert s.list_ceremonies(sp.id)[0].id==c.id
    with pytest.raises(LookupError):s.create_ceremony(CeremonyIn(sprint_id="nope",kind="daily",scheduled_at=NOW))
def test_row_396_retrospective_analysis_rollup_tracks_actions():
    s=svc();sp1=sprint(s,"S1");sp2=sprint(s,"S2")
    s.create_retrospective(RetrospectiveIn(sprint_id=sp1.id,went_well=["shipping"],didnt_go_well=["scope creep"],action_items=[{"text":"tighter estimates","status":"done"},{"text":"cap wip"}]))
    s.create_retrospective(RetrospectiveIn(sprint_id=sp2.id,action_items=[{"text":"write tests first","status":"done"}]))
    roll=s.retro_rollup()
    assert roll["retrospectives"]==2 and roll["action_items_total"]==3 and roll["action_items_done"]==2
    assert roll["completion_rate"]==pytest.approx(2/3) and roll["action_items_open"][0]["text"]=="cap wip"
def test_row_397_ab_testing_design_lifecycle_and_measurement_gate():
    s=svc()
    exp=s.create_experiment(ExperimentIn(name="cta",metric="click_rate",variants=[VariantIn(key="control",allocation=.5),VariantIn(key="treatment",allocation=.5)]))
    assert exp.status=="draft"
    with pytest.raises(ValueError):s.record_measurement(exp.id,MeasurementIn(variant_key="control",trials=100,successes=10))
    s.set_experiment_status(exp.id,"running")
    updated=s.record_measurement(exp.id,MeasurementIn(variant_key="control",trials=100,successes=10))
    assert updated.variants[0].trials==100
    with pytest.raises(LookupError):s.record_measurement(exp.id,MeasurementIn(variant_key="ghost",trials=1,successes=1))
    with pytest.raises(ValueError):s.set_experiment_status(exp.id,"draft")
    bad=ExperimentIn(name="bad",metric="m",variants=[VariantIn(key="a",allocation=.7),VariantIn(key="b",allocation=.7)])
    with pytest.raises(ValueError):s.create_experiment(bad)
def test_row_398_multivariate_testing_requires_factors_and_runs_chi_square():
    s=svc()
    with pytest.raises(ValueError):
        s.create_experiment(ExperimentIn(name="mv-bad",metric="m",kind="multivariate",variants=[VariantIn(key="a",allocation=.5),VariantIn(key="b",allocation=.5)]))
    exp=s.create_experiment(ExperimentIn(name="mv",metric="signup",kind="multivariate",variants=[
        VariantIn(key="blue-short",allocation=.25,factors={"color":"blue","copy":"short"}),
        VariantIn(key="blue-long",allocation=.25,factors={"color":"blue","copy":"long"}),
        VariantIn(key="red-short",allocation=.25,factors={"color":"red","copy":"short"}),
        VariantIn(key="red-long",allocation=.25,factors={"color":"red","copy":"long"})]))
    s.set_experiment_status(exp.id,"running")
    for key,trials,succ in[("blue-short",400,40),("blue-long",400,42),("red-short",400,110),("red-long",400,108)]:
        s.record_measurement(exp.id,MeasurementIn(variant_key=key,trials=trials,successes=succ))
    report=s.experiment_significance(exp.id)
    assert report.test=="chi_square" and report.significant and report.p_value<0.05
    assert report.inputs["df"]==3 and any("Chi-square" in a for a in report.assumptions)
def test_row_399_statistical_significance_z_test_inputs_and_assumptions():
    s=svc()
    exp=s.create_experiment(ExperimentIn(name="cta",metric="click",variants=[VariantIn(key="control",allocation=.5),VariantIn(key="treatment",allocation=.5)]))
    s.set_experiment_status(exp.id,"running")
    s.record_measurement(exp.id,MeasurementIn(variant_key="control",trials=1000,successes=100))
    s.record_measurement(exp.id,MeasurementIn(variant_key="treatment",trials=1000,successes=150))
    report=s.experiment_significance(exp.id)
    assert report.test=="two_proportion_z" and report.significant and report.p_value<0.01
    assert report.uplift==pytest.approx(.05) and report.confidence_interval[0]<.05<report.confidence_interval[1]
    assert report.inputs["control"]["trials"]==1000 and any("Fixed-horizon" in a for a in report.assumptions)
    flat=s.create_experiment(ExperimentIn(name="flat",metric="m",variants=[VariantIn(key="control",allocation=.5),VariantIn(key="treatment",allocation=.5)]))
    s.set_experiment_status(flat.id,"running")
    s.record_measurement(flat.id,MeasurementIn(variant_key="control",trials=1000,successes=100))
    s.record_measurement(flat.id,MeasurementIn(variant_key="treatment",trials=1000,successes=102))
    assert not s.experiment_significance(flat.id).significant
    small=s.create_experiment(ExperimentIn(name="small",metric="m",variants=[VariantIn(key="control",allocation=.5),VariantIn(key="treatment",allocation=.5)]))
    s.set_experiment_status(small.id,"running")
    s.record_measurement(small.id,MeasurementIn(variant_key="control",trials=10,successes=5))
    s.record_measurement(small.id,MeasurementIn(variant_key="treatment",trials=10,successes=9))
    low=s.experiment_significance(small.id)
    assert low.p_value is None and not low.significant and any("Insufficient sample" in a for a in low.assumptions)
def test_z_test_matches_known_value():
    from app.modules.m16_executive_dashboard.planning import z_test
    r=z_test({"trials":1000,"successes":100},{"trials":1000,"successes":150})
    assert r.p_value==pytest.approx(0.00072,abs=2e-4)  # z~3.38 two-sided
    from app.modules.m16_executive_dashboard.planning import chi_square_sf
    assert chi_square_sf(3.841,1)==pytest.approx(0.05,abs=1e-3)  # chi2 critical value df=1
    assert chi_square_sf(5.991,2)==pytest.approx(0.05,abs=1e-3)
def test_planning_entities_are_tenant_scoped_rows():
    from app.modules.m16_executive_dashboard.repository import WorkItemRow,SprintRow,ExperimentRow
    for row in(WorkItemRow,SprintRow,ExperimentRow):
        assert "tenant_id" in row.__table__.c and row.__table__.c.tenant_id.index
