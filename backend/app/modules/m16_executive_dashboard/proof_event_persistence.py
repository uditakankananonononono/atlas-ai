from .authenticated_proof_events import VerifyProofEvents,verify_proof_events
def verify_and_persist_proof_events(body:VerifyProofEvents,store):
 verified=verify_proof_events(body);stored=[]
 for event in verified['events']:
  row=store.persist(event);stored.append({'event_id':row.event_id,'persisted_at':row.persisted_at.isoformat()})
 return {**verified,'persisted_events':stored,'boundary':'Authenticates and persists each tenant-scoped producer event append-only. Duplicate event IDs cannot replace prior proof. It does not subscribe to producers, inspect proof bytes, deploy, or independently authenticate producers beyond configured keys.'}
