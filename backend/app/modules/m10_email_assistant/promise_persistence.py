"""Transactional persistence orchestration for verified promise reconciliation."""
from __future__ import annotations
from pydantic import BaseModel
from .promise_reconciliation import PromiseReconciliationRequest,reconcile_promise_state
class PersistPromiseReconciliationRequest(BaseModel):reconciliation:PromiseReconciliationRequest
def persist_reconciliation(body:PersistPromiseReconciliationRequest,repository)->dict:
 result=reconcile_promise_state(body.reconciliation)
 thread_id=result['reconciled_snapshot']['thread_id']
 row=repository.persist_promise_snapshot(thread_id=thread_id,previous_snapshot_sha256=result['previous_snapshot_sha256'],snapshot_sha256=result['reconciled_snapshot_sha256'],snapshot=result['reconciled_snapshot'])
 return {**result,'persisted':True,'persisted_at':row.updated_at.isoformat(),'boundary':'The verified reconciliation snapshot is transactionally persisted with tenant/thread compare-and-swap. First persistence trusts the supplied prior hash as lineage; later writes require the stored head. This does not authenticate reviewers or source-message bytes, create tasks, draft, remind, or send.'}
