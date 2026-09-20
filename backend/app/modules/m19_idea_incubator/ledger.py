"""Evidence, feasibility, experiment and decision domain logic."""
from __future__ import annotations
from datetime import datetime,timezone
from math import fsum
from uuid import uuid4
from .schemas import *

class ConflictError(RuntimeError):pass
class ValidationError(ValueError):pass
DIMENSIONS=("desirability","technical","viability","strategic_fit","compliance")
DEFAULT_WEIGHTS={"desirability":.25,"technical":.2,"viability":.2,"strategic_fit":.15,"compliance":.2}
TRANSITIONS={IdeaStage.CAPTURED:{IdeaStage.DISCOVERY,IdeaStage.PARKED,IdeaStage.REJECTED},IdeaStage.DISCOVERY:{IdeaStage.VALIDATION,IdeaStage.PARKED,IdeaStage.REJECTED},IdeaStage.VALIDATION:{IdeaStage.EXPERIMENTING,IdeaStage.APPROVED,IdeaStage.PARKED,IdeaStage.REJECTED},IdeaStage.EXPERIMENTING:{IdeaStage.VALIDATION,IdeaStage.APPROVED,IdeaStage.PARKED,IdeaStage.REJECTED},IdeaStage.PARKED:{IdeaStage.DISCOVERY,IdeaStage.REJECTED},IdeaStage.APPROVED:set(),IdeaStage.REJECTED:set()}
TERMINAL={ExperimentStatus.SUCCEEDED,ExperimentStatus.FAILED,ExperimentStatus.INCONCLUSIVE,ExperimentStatus.CANCELLED}
def now():return datetime.now(timezone.utc)
class LedgerService:
    def __init__(self,repository,actor_id="system"):self.repository=repository;self.actor_id=actor_id
    def _idea(self,i):
        x=self.repository.get_idea(i)
        if not x:raise LookupError(i)
        return x
    def create_idea(self,data):
        at=now();return self.repository.save_idea(Idea(id=str(uuid4()),created_at=at,updated_at=at,**data.model_dump()))
    def list_ideas(self,stage=None):return [x for x in self.repository.list_ideas() if stage is None or x.stage==stage]
    def add_evidence(self,i,data):self._idea(i);return self.repository.add_evidence(Evidence(id=str(uuid4()),idea_id=i,created_at=now(),**data.model_dump()))
    def evidence_summary(self,i):
        items=self.repository.list_evidence(self._idea(i).id)
        def score(p):
            residual=1
            for x in items:
                if x.polarity==p:residual*=1-x.strength*x.confidence
            return 1-residual
        support=score(EvidencePolarity.SUPPORTS);contradiction=score(EvidencePolarity.CONTRADICTS)
        return EvidenceSummary(supporting_count=sum(x.polarity==EvidencePolarity.SUPPORTS for x in items),contradicting_count=sum(x.polarity==EvidencePolarity.CONTRADICTS for x in items),neutral_count=sum(x.polarity==EvidencePolarity.NEUTRAL for x in items),support_score=round(support,4),contradiction_score=round(contradiction,4),net_score=round(support-contradiction,4),confidence=round(fsum(x.confidence for x in items)/len(items),4) if items else 0)
    def test_feasibility(self,i,data):
        self._idea(i);weights=data.weights or DEFAULT_WEIGHTS
        if set(weights)!=set(DIMENSIONS):raise ValidationError("weights must contain all five dimensions")
        if any(x<0 for x in weights.values()) or abs(sum(weights.values())-1)>1e-6:raise ValidationError("weights must be non-negative and sum to 1")
        dimensions={k:getattr(data,k) for k in DIMENSIONS};score=fsum(dimensions[k].score*weights[k] for k in DIMENSIONS);confidence=fsum(dimensions[k].confidence*weights[k] for k in DIMENSIONS)
        outcome=FeasibilityOutcome.FAIL if data.blockers or min(x.score for x in dimensions.values())<30 or score<50 else FeasibilityOutcome.PASS if score>=70 and confidence>=.6 else FeasibilityOutcome.CONDITIONAL
        payload=data.model_dump();payload["weights"]=weights
        return self.repository.add_test(FeasibilityTest(id=str(uuid4()),idea_id=i,weighted_score=round(score,2),weighted_confidence=round(confidence,4),outcome=outcome,tested_at=now(),**payload))
    def create_experiment(self,i,data):
        idea=self._idea(i)
        if idea.stage in {IdeaStage.APPROVED,IdeaStage.REJECTED}:raise ValidationError("terminal ideas cannot receive experiments")
        at=now();return self.repository.save_experiment(Experiment(id=str(uuid4()),idea_id=i,created_at=at,updated_at=at,**data.model_dump()))
    def update_experiment(self,i,eid,data):
        self._idea(i);item=next((x for x in self.repository.list_experiments(i) if x.id==eid),None)
        if not item:raise LookupError(eid)
        if item.status in TERMINAL:raise ConflictError("completed experiment results are immutable")
        if item.status==ExperimentStatus.PLANNED and data.status not in {ExperimentStatus.RUNNING,ExperimentStatus.CANCELLED}:raise ValidationError("a planned experiment must start or be cancelled")
        if item.status==ExperimentStatus.RUNNING and data.status not in TERMINAL:raise ValidationError("a running experiment must finish or be cancelled")
        if data.status in {ExperimentStatus.SUCCEEDED,ExperimentStatus.FAILED} and data.observed_value is None:raise ValidationError("observed_value is required")
        return self.repository.save_experiment(item.model_copy(update={**data.model_dump(),"updated_at":now()}))
    def decide(self,i,data):
        idea=self._idea(i)
        if data.expected_version is not None and data.expected_version!=idea.version:raise ConflictError("idea changed; refresh before deciding")
        if data.to_stage not in TRANSITIONS[idea.stage]:raise ValidationError(f"invalid transition {idea.stage.value} to {data.to_stage.value}")
        evidence=self.evidence_summary(i);tests=self.repository.list_tests(i);experiments=self.repository.list_experiments(i)
        if data.to_stage==IdeaStage.VALIDATION and not self.repository.list_evidence(i):raise ValidationError("validation requires evidence")
        if data.to_stage==IdeaStage.EXPERIMENTING and not experiments:raise ValidationError("experimenting requires an experiment")
        if data.to_stage==IdeaStage.APPROVED:
            if not tests or tests[-1].outcome!=FeasibilityOutcome.PASS:raise ValidationError("approval requires a passing latest feasibility test")
            if evidence.net_score<=0:raise ValidationError("approval requires net-positive evidence")
            if any(x.status not in TERMINAL for x in experiments):raise ValidationError("approval requires finished experiments")
        before=idea.stage;updated=idea.model_copy(update={"stage":data.to_stage,"version":idea.version+1,"updated_at":now()});self.repository.save_idea(updated,idea.version)
        return self.repository.add_decision(Decision(id=str(uuid4()),idea_id=i,from_stage=before,to_stage=data.to_stage,rationale=data.rationale,actor_id=self.actor_id,metadata=data.metadata,decided_at=updated.updated_at,idea_version=updated.version))
    def dossier(self,i):return IdeaDossier(idea=self._idea(i),evidence=self.repository.list_evidence(i),evidence_summary=self.evidence_summary(i),feasibility_tests=self.repository.list_tests(i),experiments=self.repository.list_experiments(i),decisions=self.repository.list_decisions(i))
