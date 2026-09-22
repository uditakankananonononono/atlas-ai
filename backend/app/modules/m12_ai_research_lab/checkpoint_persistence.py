from .reproducible_run import ReproducibleRunRequest,checkpoint
def checkpoint_and_enqueue(body:ReproducibleRunRequest,queue):
 result=checkpoint(body);row=queue.enqueue(result);return {**result,'queue_state':row.state,'enqueued_at':row.enqueued_at.isoformat(),'boundary':'Validates and transactionally queues a tenant-scoped checkpoint. A run cannot have two different queued heads. It does not execute nodes, verify dataset bytes, authenticate receipts, or resume work.'}
