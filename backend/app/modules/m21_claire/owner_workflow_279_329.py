"""Owner-controlled Claire workflow, evidence trace, consented memory and preference feedback."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from typing import Any
NAMES=["Goal intake and acceptance criteria","Creative multi-path planning","Playful personality without deceptive behavior","Web and public-social research","Public image/code/idea extraction with attribution","Trend and inspiration synthesis","Software/tool identification","Approved software installation","Dependency management","Environment configuration preview","Multi-model AI orchestration","Vibecoding project generation","Iterative code review and refinement","Existing-system code integration","Owner-consented filesystem read","Approved filesystem write","Approved shell command execution","Approved service deployment","Repetitive-task automation","Background schedule management","Software experiment design","Hardware/IoT experiment planning","Simulation experiments","Prototype design","3D-printing workflow proposal","Atlas supervision and health monitoring","Atlas configuration proposal","Atlas module integration","Performance diagnosis","Patch generation and test execution","Bounded retry and alternate-path loop","Failure log and root-cause analysis","Transparent goal-plan-evidence-decision trace","No hidden chain-of-thought capture","Risk classification","Approval before installs","Approval before purchases","Approval before system changes","Approval before destructive commands","Approval before experiments with material risk","Approve/deny/modify plan flow","Real-time progress events","Completion summary and next steps","Paired local-PC endpoint","Consent and access revocation","Persistent resumable task state","Stop control and bounded resource budgets","Doraemon-style closest-feasible prototype framing","Website build workflow","Essay-topic research workflow","Atlas integration workflow"]
FEATURES={279+i:n for i,n in enumerate(NAMES)}
ACTIONS=set(range(284,310))|{322,327,328,329};GATES=set(range(313,321))|{323,325};TRACE={279,280,281,282,283,310,311,312,321,324,326};PREF={4:'Voice Fine-Tuning',6:'Preference Ranking',9:'Human-in-the-Loop Reinforcement (Weekly)'}
DISCLAIMER="Claire exposes concise decision evidence, not hidden chain-of-thought. Claims reflect recorded evidence only; external actions remain approval-gated and verified after execution."
def _base(row,d):
 if row not in FEATURES:raise ValueError('row_id must be 279-329')
 goal=d.get('goal');criteria=d.get('acceptance_criteria',[])
 if not goal or not criteria:raise ValueError('goal and acceptance_criteria are required')
 return {'row_id':row,'concept':FEATURES[row],'goal':goal,'acceptance_criteria':criteria,'status':d.get('status','planned'),'limits':d.get('limits',[]),'review_required':True,'disclaimer':DISCLAIMER}
def _evidence(items):
 out=[]
 for e in items:
  if not e.get('id') or not e.get('provenance'):raise ValueError('evidence needs id and provenance')
  out.append({'id':e['id'],'provenance':e['provenance'],'uri':e.get('uri'),'observed_at':e.get('observed_at'),'claim':e.get('claim'),'verification':e.get('verification','unverified')})
 return out
def _action(row,d):
 o=_base(row,d);plans=d.get('plans',[]);evidence=_evidence(d.get('evidence',[]))
 if not plans:raise ValueError('plans are required')
 steps=[]
 for p in plans:
  risk=p.get('risk','low');approval=p.get('approval',{});requires=risk in ('medium','high','material') or bool(p.get('external_effect'))
  authorized=bool(approval.get('decision')=='approved' and approval.get('scope')==p.get('id')) if requires else True
  steps.append({'id':p.get('id'),'operation':p.get('operation'),'preview':p.get('preview'),'risk':risk,'external_effect':bool(p.get('external_effect')),'requires_approval':requires,'authorized':authorized,'execution_status':'ready' if authorized else 'blocked_pending_approval','dependencies':p.get('dependencies',[]),'rollback':p.get('rollback')})
 o.update({'plans':steps,'evidence':evidence,'alternatives':d.get('alternatives',[]),'model_assignments':d.get('model_assignments',[]),'tests':d.get('tests',[]),'verification_results':d.get('verification_results',[]),'boundary':'Planning and evidence only. This endpoint never reads/writes files, runs shell commands, installs, purchases, deploys, schedules, pairs a device or changes Atlas. Separate scoped approval and execution adapters are required.'});return o
def _gate(row,d):
 o=_base(row,d);request=d.get('approval_request',{});budget=d.get('budget',{})
 if not request.get('id') or not request.get('operation'):raise ValueError('approval_request id and operation are required')
 decision=request.get('decision','pending')
 if decision not in ('pending','approved','denied','modified','revoked'):raise ValueError('invalid approval decision')
 within=all(float(budget.get(k,0))<=float(budget.get('limits',{}).get(k,float('inf'))) for k in ('seconds','cost','attempts'))
 o.update({'risk':d.get('risk',{}),'approval':{'id':request['id'],'operation':request['operation'],'preview':request.get('preview'),'decision':decision,'scope':request.get('scope'),'decided_by':request.get('decided_by'),'decided_at':request.get('decided_at')},'budget':budget,'within_budget':within,'stopped':bool(d.get('stop_requested')) or decision in ('denied','revoked') or not within,'revocations':d.get('revocations',[]),'progress_events':d.get('progress_events',[]),'boundary':'No action occurs from this review. Approval must match the exact operation/scope and remain unrevoked; stop, denial, revocation or exceeded budget blocks execution.'});return o
def _trace(row,d):
 o=_base(row,d);evidence=_evidence(d.get('evidence',[]));criteria=[]
 for c in o['acceptance_criteria']:
  refs=c.get('evidence_ids',[]) if isinstance(c,dict) else []
  verified=bool(refs) and all(any(e['id']==x and e['verification']=='verified' for e in evidence) for x in refs)
  criteria.append({'criterion':c.get('criterion') if isinstance(c,dict) else c,'evidence_ids':refs,'verified':verified})
 complete=bool(criteria) and all(c['verified'] for c in criteria)
 o.update({'evidence':evidence,'criteria_results':criteria,'completion_claim':'complete' if complete else 'not_verified_complete','decision_evidence':d.get('decision_evidence',[]),'plans':d.get('plans',[]),'failure_log':d.get('failure_log',[]),'root_causes':d.get('root_causes',[]),'retry_state':d.get('retry_state',{}),'resume_token':d.get('resume_token'),'next_steps':d.get('next_steps',[]),'honest_limits':d.get('honest_limits',[]),'boundary':'Decision evidence contains inputs, sources, criteria, alternatives and outcomes, never hidden chain-of-thought. Completion is claimed only when every acceptance criterion has verified evidence.'});return o
def claire_owner_workflow_279_329(row_id:int,data:dict[str,Any])->dict[str,Any]:
 if row_id in ACTIONS:return _action(row_id,data)
 if row_id in GATES:return _gate(row_id,data)
 if row_id in TRACE:return _trace(row_id,data)
 raise ValueError('row_id must be 279-329')
def preference_feedback_4_6_9(feature_id:int,data:dict[str,Any])->dict[str,Any]:
 if feature_id not in PREF:raise ValueError('feature_id must be 4, 6 or 9')
 consent=data.get('consent',{});provenance=data.get('provenance',[])
 if consent.get('status')!='granted' or not consent.get('scope') or not provenance:raise ValueError('active scoped consent and provenance are required')
 if consent.get('revoked_at'):raise ValueError('consent has been revoked')
 examples=data.get('examples',[]);holdout=data.get('holdout',[])
 if not examples or not holdout:raise ValueError('training examples and holdout are required')
 prohibited=[]
 for x in examples:
  purpose=str(x.get('purpose','')).lower()
  if 'detector evasion' in purpose or 'impersonat' in purpose:prohibited.append(x.get('id'))
 if prohibited:raise ValueError('detector evasion and impersonation are prohibited')
 candidates=data.get('candidates',[]);ranked=sorted(candidates,key=lambda x:(-float(x.get('score',0)),x.get('id','')))
 baseline=sum(float(x.get('baseline_score',0)) for x in holdout)/len(holdout);candidate=sum(float(x.get('candidate_score',0)) for x in holdout)/len(holdout);promote=candidate>baseline and data.get('owner_decision')=='approved'
 return {'feature_id':feature_id,'concept':PREF[feature_id],'consent':consent,'provenance':provenance,'example_count':len(examples),'ranked_candidates':ranked,'holdout_evaluation':{'baseline':baseline,'candidate':candidate,'improved':candidate>baseline},'owner_decision':data.get('owner_decision','pending'),'behavior_mutated':promote,'promotion_status':'promoted' if promote else 'blocked_pending_owner_approval_or_improvement','revert_token':sha256((str(feature_id)+consent['scope']).encode()).hexdigest()[:16],'boundary':'No silent behavior mutation. Changes require scoped, unrevoked consent, provenance, holdout improvement and explicit owner approval. Never optimize for detector evasion or impersonation.'}
