"""No-total newest-ID window. One LIMIT scan, no full-match COUNT query.

Python materializes at most scan_cap+1 rows. SQL may examine more rows to satisfy
filters; no DB CPU/index/latency guarantee. Probe row not scored or cursor-consumed.
"""
from sqlalchemy import select
from .persistent_journal import JournalEntry,lexical_vector
from .bounded_journal_retrieval import validate_retrieval_bounds,_predicates


def cursor_retrieve(session,*,tenant_id,actor_id,query,limit=5,kind='decision',since=None,until=None,after_id=None,before_id=None,scan_cap=500):
    if not isinstance(tenant_id,str) or not isinstance(actor_id,str) or not tenant_id.strip() or not actor_id.strip():raise ValueError('authenticated tenant and actor required')
    b=validate_retrieval_bounds(query,limit,kind,since,until,after_id,before_id,scan_cap)
    scanned=list(session.scalars(select(JournalEntry).where(*_predicates(tenant_id,actor_id,b)).order_by(JournalEntry.id.desc()).limit(b.scan_cap+1)))
    has_more=len(scanned)>b.scan_cap
    rows=scanned[:b.scan_cap]
    q=lexical_vector(b.query)
    scored=[(sum(a*c for a,c in zip(q,row.vector)),row) for row in rows]
    scored.sort(key=lambda x:(-x[0],x[1].id))
    positive=[(score,row) for score,row in scored if score>0]
    hits=[{'id':row.id,'decision':row.decision,'reason':row.reason,'source_reference':row.source_reference,'score':round(score,4),'created_at':row.created_at.isoformat() if row.created_at else None,'retrieval':'lexical_not_semantic'} for score,row in positive[:b.limit]]
    oldest=min((row.id for row in rows),default=None)
    return {'hits':hits,'matched_total':None,'total_status':'unknown_not_counted',
            'has_more':has_more,'next_before_id':oldest if has_more else None,
            'oldest_scanned_id':oldest,'newest_scanned_id':max((row.id for row in rows),default=None),
            'rows_materialized':len(scanned),'probe_rows':int(has_more),'rows_scored':len(rows),
            'omitted_by_limit':len(positive)-len(hits),'omitted_by_scan_cap':None,
            'global_top_k_claimed':False,'retrieval':'lexical_not_semantic','external_action_permission':False,
            'window':{'kind':b.kind,'limit':b.limit,'scan_cap':b.scan_cap,'since':b.since.isoformat() if b.since else None,'until':b.until.isoformat() if b.until else None,'after_id':b.after_id,'before_id':b.before_id,'scan_order':'id_desc_newest_first'}}
