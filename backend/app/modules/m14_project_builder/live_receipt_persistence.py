from .live_receipt_verification import VerifyLiveReceipts,verify_live_receipts
def verify_and_persist_live_receipts(body:VerifyLiveReceipts,store):
 verified=verify_live_receipts(body);stored=[]
 for receipt in verified['receipts']:
  row=store.persist(receipt);stored.append({'receipt_id':row.receipt_id,'persisted_at':row.persisted_at.isoformat()})
 return {**verified,'persisted_receipts':stored,'boundary':'Verifies and persists each tenant-scoped live receipt append-only. Duplicate receipt IDs cannot replace prior evidence. It does not deploy, run acceptance tests, inspect proof bytes, or independently authenticate issuers beyond configured keys.'}
