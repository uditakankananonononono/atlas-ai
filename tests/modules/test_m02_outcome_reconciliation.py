import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Lock
from app.modules.m02_competition_manager.models import ActionState,ApplicationStatus,ApplicationWorkspace,StagedBrowserAction
from app.modules.m02_competition_manager.repository import InMemoryCompetitionRepository,ConflictError
from app.modules.m02_competition_manager.lane_service import CompetitionManager,payload_digest
class Verifier:
 def __init__(self,answer=True):self.answer=answer
 def verify(self,action,evidence):return self.answer
class Executor:
 def __init__(self,error=None):self.calls=0;self.error=error
 def execute(self,*args):
  self.calls+=1
  if self.error:raise self.error
  return {'returned':'not independently confirmed'}
class OutcomeTest(unittest.TestCase):
 def setUp(self):
  self.repo=InMemoryCompetitionRepository();self.manager=CompetitionManager(self.repo)
  self.ws=self.repo.save_workspace(ApplicationWorkspace('competition','Title',['source'],status=ApplicationStatus.STAGED))
  self.action=StagedBrowserAction(self.ws.id,'submit_application','https://example.org/form',{'answer':'reviewed'},state=ActionState.APPROVED)
  self.action.payload_digest=payload_digest(self.action.action,self.action.target_url,self.action.payload)
  self.action.approved_digest=self.action.payload_digest;self.action.approval_id='review'
  self.repo.save_action(self.action)
 def receipt(self,outcome='confirmed_success'):
  return {'action_id':self.action.id,'payload_digest':self.action.payload_digest,'outcome':outcome,'attempt_terminal':True,'source':'browser_readback','external_reference':'receipt-1','evidence':'readback captured'}
 def test_returned_result_not_submission_confirmation(self):
  ex=Executor();action=self.manager.execute_action(self.action.id,ex)
  self.assertEqual(action.state,ActionState.EXECUTOR_RETURNED)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status,ApplicationStatus.STAGED)
  with self.assertRaises(PermissionError):self.manager.execute_action(self.action.id,ex)
  self.assertEqual(ex.calls,1)
 def test_exception_unknown_and_never_retry(self):
  ex=Executor(TimeoutError('sensitive raw error'))
  with self.assertRaises(TimeoutError):self.manager.execute_action(self.action.id,ex)
  action=self.repo.get_action(self.action.id)
  self.assertEqual(action.state,ActionState.OUTCOME_UNKNOWN);self.assertNotIn('sensitive',action.error)
  with self.assertRaises(PermissionError):self.manager.execute_action(self.action.id,ex)
  self.assertEqual(ex.calls,1)
 def test_verified_success_reconciles_workspace_only(self):
  ex=Executor();self.manager.execute_action(self.action.id,ex)
  action=self.manager.reconcile_action(self.action.id,self.receipt(),Verifier())
  self.assertEqual(action.state,ActionState.SUCCEEDED)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status,ApplicationStatus.SUBMITTED)
  self.assertEqual(self.manager.reconcile_workspace(self.action.id).status,ApplicationStatus.SUBMITTED)
  self.assertEqual(ex.calls,1)
 def test_no_effect_failure_still_needs_fresh_review(self):
  ex=Executor(TimeoutError())
  with self.assertRaises(TimeoutError):self.manager.execute_action(self.action.id,ex)
  action=self.manager.reconcile_action(self.action.id,self.receipt('confirmed_no_effect'),Verifier())
  self.assertEqual(action.state,ActionState.FAILED)
  with self.assertRaises(PermissionError):self.manager.execute_action(self.action.id,ex)
 def test_wrong_subject_or_unverified_refused(self):
  self.manager.execute_action(self.action.id,Executor())
  wrong=self.receipt();wrong['payload_digest']='wrong'
  with self.assertRaises(ValueError):self.manager.reconcile_action(self.action.id,wrong,Verifier())
  with self.assertRaises(PermissionError):self.manager.reconcile_action(self.action.id,self.receipt(),Verifier(False))
  self.assertEqual(self.repo.get_action(self.action.id).state,ActionState.EXECUTOR_RETURNED)
 def test_success_save_failure_stays_executing_reconciliable(self):
  original=self.repo.save_action
  def save(action,expected_version=None):
   if action.state==ActionState.EXECUTOR_RETURNED:raise OSError('fixture persistence failure')
   return original(action,expected_version)
  self.repo.save_action=save;ex=Executor()
  with self.assertRaises(OSError):self.manager.execute_action(self.action.id,ex)
  self.assertEqual(self.repo.get_action(self.action.id).state,ActionState.EXECUTING)
  with self.assertRaises(PermissionError):self.manager.execute_action(self.action.id,ex)
  self.manager.reconcile_action(self.action.id,self.receipt(),Verifier())
  self.assertEqual(ex.calls,1)
 def test_workspace_failure_retains_confirmation_and_bookkeeping_retry(self):
  self.manager.execute_action(self.action.id,Executor());original=self.repo.save_workspace
  self.repo.save_workspace=lambda *args,**kwargs:(_ for _ in ()).throw(ConflictError('fixture'))
  with self.assertRaises(ConflictError):self.manager.reconcile_action(self.action.id,self.receipt(),Verifier())
  self.assertEqual(self.repo.get_action(self.action.id).state,ActionState.SUCCEEDED)
  self.repo.save_workspace=original
  self.assertEqual(self.manager.reconcile_workspace(self.action.id).status,ApplicationStatus.SUBMITTED)
 def test_approved_never_executed_cannot_be_reconciled(self):
  with self.assertRaises(ValueError):self.manager.reconcile_action(self.action.id,self.receipt(),Verifier())
  self.assertEqual(self.repo.get_action(self.action.id).state,ActionState.APPROVED)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status,ApplicationStatus.STAGED)
 def test_receipt_bound_to_exact_action(self):
  self.manager.execute_action(self.action.id,Executor())
  wrong=self.receipt();wrong['action_id']='other-action'
  with self.assertRaises(ValueError):self.manager.reconcile_action(self.action.id,wrong,Verifier())
  self.assertEqual(self.repo.get_action(self.action.id).state,ActionState.EXECUTOR_RETURNED)
 def test_workspace_reconcile_requires_verified_success(self):
  with self.assertRaises(PermissionError):self.manager.reconcile_workspace(self.action.id)
  self.manager.execute_action(self.action.id,Executor())
  with self.assertRaises(PermissionError):self.manager.reconcile_workspace(self.action.id)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status,ApplicationStatus.STAGED)
 def test_concurrent_claim_only_one_executor(self):
  original=self.repo.get_action;gate=Barrier(2)
  def get(aid):
   action=original(aid)
   if action.state==ActionState.APPROVED:gate.wait(timeout=5)
   return action
  self.repo.get_action=get;ex=Executor()
  def run(_):
   try:return self.manager.execute_action(self.action.id,ex).state
   except ConflictError:return 'claim-lost'
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
  self.assertEqual(ex.calls,1);self.assertIn('claim-lost',results)
 def test_preflight_ineligible_no_call(self):
  ws=self.repo.get_workspace(self.ws.id);ws.status=ApplicationStatus.WITHDRAWN;self.repo.save_workspace(ws)
  ex=Executor()
  with self.assertRaises(ValueError):self.manager.execute_action(self.action.id,ex)
  self.assertEqual(ex.calls,0)
 def test_nonterminal_receipt_refused(self):
  self.manager.execute_action(self.action.id,Executor());receipt=self.receipt();receipt['attempt_terminal']=False
  with self.assertRaises(ValueError):self.manager.reconcile_action(self.action.id,receipt,Verifier())
 def test_reconciliation_cas_conflict_retains_original_return(self):
  self.manager.execute_action(self.action.id,Executor());repo=self.repo;aid=self.action.id
  class ChangingVerifier:
   def verify(self,action,evidence):
    changed=repo.get_action(aid);changed.updated_at=action.updated_at;repo.save_action(changed,expected_version=changed.version)
    return True
  with self.assertRaises(ConflictError):self.manager.reconcile_action(aid,self.receipt(),ChangingVerifier())
  self.assertEqual(repo.get_action(aid).state,ActionState.EXECUTOR_RETURNED)
 def test_altered_attempt_subject_cannot_be_reconciled(self):
  self.manager.execute_action(self.action.id,Executor());changed=self.repo.get_action(self.action.id)
  changed.target_url='https://example.org/other';self.repo.save_action(changed,expected_version=changed.version)
  with self.assertRaises(PermissionError):self.manager.reconcile_action(self.action.id,self.receipt(),Verifier())
 def test_existing_api_ambiguous_error_is_not_known_failure(self):
  ex=Executor(TimeoutError('fixture after possible click'))
  with self.assertRaises(TimeoutError):self.manager.execute_action(self.action.id,ex)
  self.assertEqual(self.repo.get_action(self.action.id).state.value,'outcome_unknown')
  self.assertEqual(self.repo.get_workspace(self.ws.id).status.value,'staged')
 def test_existing_api_return_does_not_assert_submission(self):
  ex=Executor();self.manager.execute_action(self.action.id,ex)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status.value,'staged')
  self.assertEqual(self.repo.get_action(self.action.id).state.value,'executor_returned')
 def test_existing_api_concurrent_snapshots_no_double_dispatch(self):
  original=self.repo.get_action;gate=Barrier(2)
  def get(aid):
   action=original(aid)
   if action.state.value=='approved':gate.wait(timeout=5)
   return action
  self.repo.get_action=get;ex=Executor()
  def run(_):
   try:self.manager.execute_action(self.action.id,ex);return 'returned'
   except (ConflictError,PermissionError,ValueError):return 'refused'
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(2)))
  self.assertEqual(ex.calls,1)
 def test_generic_transition_cannot_bypass_confirmation(self):
  with self.assertRaises(PermissionError):self.manager.transition(self.ws.id,ApplicationStatus.SUBMITTED)
  self.assertEqual(self.repo.get_workspace(self.ws.id).status,ApplicationStatus.STAGED)
 def test_unverified_status_observation_cannot_bypass_confirmation(self):
  from app.modules.m02_competition_manager.models import StatusObservation,utcnow
  observation=StatusObservation(self.ws.id,ApplicationStatus.SUBMITTED,'browser_readback',utcnow(),'unverified caller text')
  with self.assertRaises(PermissionError):self.manager.record_status_observation(observation)
  self.assertEqual(self.manager.status_history(self.ws.id),[])
