from datetime import datetime,timezone
import pytest
from app.modules.m19_idea_incubator.schemas import *
from app.modules.m19_idea_incubator.repository import MemoryIdeaRepository
from app.modules.m19_idea_incubator.ledger import ConflictError,LedgerService,ValidationError

def svc():return LedgerService(MemoryIdeaRepository(),"actor-1")
def idea(s):return s.create_idea(IdeaCreate(title="Scholarship matcher",problem="Deadlines are missed",proposed_solution="Verified matching"))
def ev(p=EvidencePolarity.SUPPORTS,strength=.8,confidence=.9):return EvidenceCreate(kind=EvidenceKind.INTERVIEW,claim="Students need this",source="interview-1",polarity=p,strength=strength,confidence=confidence,observed_at=datetime.now(timezone.utc))
def dim(n=80,c=.8):return DimensionScore(score=n,confidence=c)
def feasibility(n=80,**kw):return FeasibilityTestCreate(desirability=dim(n),technical=dim(n),viability=dim(n),strategic_fit=dim(n),compliance=dim(n),**kw)
def decision(stage,version=None):return DecisionCreate(to_stage=stage,rationale="Evidence supports moving",expected_version=version)
def experiment():return ExperimentCreate(name="Demand test",hypothesis="Users convert",method="Landing page",metric="conversion",target=10)

def test_idea_crud_is_defensively_copied():
 s=svc();x=idea(s);y=s._idea(x.id);y.title="changed";assert s._idea(x.id).title=="Scholarship matcher";assert s.list_ideas(IdeaStage.CAPTURED)[0].id==x.id

def test_evidence_scoring_uses_complementary_probabilities():
 s=svc();x=idea(s);s.add_evidence(x.id,ev(strength=.8,confidence=.5));s.add_evidence(x.id,ev(strength=.5,confidence=.8));s.add_evidence(x.id,ev(EvidencePolarity.CONTRADICTS,.5,.5));z=s.evidence_summary(x.id);assert (z.support_score,z.contradiction_score,z.net_score)==(.64,.25,.39)

def test_feasibility_outcomes_and_hard_failures():
 s=svc();x=idea(s);assert s.test_feasibility(x.id,feasibility()).outcome==FeasibilityOutcome.PASS;assert s.test_feasibility(x.id,feasibility(60)).outcome==FeasibilityOutcome.CONDITIONAL;assert s.test_feasibility(x.id,feasibility(80,blockers=["license"])).outcome==FeasibilityOutcome.FAIL
 d=feasibility(90);d.compliance=dim(20);assert s.test_feasibility(x.id,d).outcome==FeasibilityOutcome.FAIL

def test_invalid_weights_rejected():
 s=svc();x=idea(s)
 with pytest.raises(ValidationError,match="five dimensions"):s.test_feasibility(x.id,feasibility(weights={"technical":1}))
 with pytest.raises(ValidationError,match="sum to 1"):s.test_feasibility(x.id,feasibility(weights={k:.3 for k in ("desirability","technical","viability","strategic_fit","compliance")}))

def test_experiment_lifecycle_and_result_immutability():
 s=svc();x=idea(s);e=s.create_experiment(x.id,experiment());s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.RUNNING));done=s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.SUCCEEDED,observed_value=13,learnings="target beaten"));assert done.observed_value==13
 with pytest.raises(ConflictError,match="immutable"):s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.RUNNING))

def test_experiment_transition_and_result_validation():
 s=svc();x=idea(s);e=s.create_experiment(x.id,experiment())
 with pytest.raises(ValidationError,match="must start"):s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.SUCCEEDED,observed_value=1))
 s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.RUNNING))
 with pytest.raises(ValidationError,match="observed_value"):s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.FAILED))

def test_stage_gates_and_version_conflict():
 s=svc();x=idea(s);first=s.decide(x.id,decision(IdeaStage.DISCOVERY,1));assert first.actor_id=="actor-1" and first.idea_version==2
 with pytest.raises(ValidationError,match="requires evidence"):s.decide(x.id,decision(IdeaStage.VALIDATION))
 s.add_evidence(x.id,ev());s.decide(x.id,decision(IdeaStage.VALIDATION,2))
 with pytest.raises(ValidationError,match="requires an experiment"):s.decide(x.id,decision(IdeaStage.EXPERIMENTING))
 with pytest.raises(ConflictError,match="refresh"):s.decide(x.id,decision(IdeaStage.APPROVED,1))

def test_approval_requires_latest_pass_positive_evidence_and_finished_experiments():
 s=svc();x=idea(s);s.decide(x.id,decision(IdeaStage.DISCOVERY));s.add_evidence(x.id,ev());s.decide(x.id,decision(IdeaStage.VALIDATION));e=s.create_experiment(x.id,experiment());s.test_feasibility(x.id,feasibility())
 with pytest.raises(ValidationError,match="finished"):s.decide(x.id,decision(IdeaStage.APPROVED))
 s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.RUNNING));s.update_experiment(x.id,e.id,ExperimentUpdate(status=ExperimentStatus.SUCCEEDED,observed_value=12));assert s.decide(x.id,decision(IdeaStage.APPROVED)).to_stage==IdeaStage.APPROVED

def test_latest_feasibility_is_authoritative():
 s=svc();x=idea(s);s.decide(x.id,decision(IdeaStage.DISCOVERY));s.add_evidence(x.id,ev());s.decide(x.id,decision(IdeaStage.VALIDATION));s.test_feasibility(x.id,feasibility());s.test_feasibility(x.id,feasibility(40))
 with pytest.raises(ValidationError,match="passing latest"):s.decide(x.id,decision(IdeaStage.APPROVED))

def test_dossier_is_complete_audit_view():
 s=svc();x=idea(s);e=s.add_evidence(x.id,ev());f=s.test_feasibility(x.id,feasibility());d=s.dossier(x.id);assert d.idea.id==x.id and d.evidence[0].id==e.id and d.feasibility_tests[0].id==f.id and d.evidence_summary.net_score>0
