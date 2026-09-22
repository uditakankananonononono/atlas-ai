from .revision_acceptance import RevisionAcceptance,verify_revision_acceptance
def persist_revision_acceptance(body:RevisionAcceptance,store):
 result=verify_revision_acceptance(body);row=store.persist(result);return {**result,'persisted':True,'persisted_at':row.persisted_at.isoformat(),'boundary':'Persists the verified owner-review acceptance as an append-only version chain. It does not edit, publish, disclose, send, or enforce a publication adapter; audience crossing still requires disclosure_approved.'}
