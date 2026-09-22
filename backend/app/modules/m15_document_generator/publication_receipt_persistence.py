from .provider_receipt import VerifyProviderPublication,verify_provider_publication
def verify_and_persist_publication(body:VerifyProviderPublication,store):
 verified=verify_provider_publication(body);row=store.persist(verified);return {**verified,'persisted':True,'persisted_at':row.persisted_at.isoformat(),'boundary':'Authenticates and persists the tenant-scoped private-publication receipt append-only. Approval IDs and provider object keys cannot be reused to replace evidence. It does not render, upload, inspect remote bytes, or consume approval.'}
