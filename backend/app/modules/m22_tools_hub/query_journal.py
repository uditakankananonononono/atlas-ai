"""Tenant SQL journal for completed M22 queries, independent of approvals.

A single tenant row is the compare-and-swap transaction boundary. Snapshot,
latest diff and bounded history commit together, or fail without a partial
in-memory success. Ordering is commit order, not remote request start order.
Lost compare-and-swap races are retried with bounded jittered backoff (64
attempts, capped sleeps, worst case well under a second plus database work);
permanent errors (validation, capacity) raise immediately without retry.
No collector credentials/errors/configuration are stored. Query text and
candidate display names ARE stored in the tenant database, not encrypted here.
"""
from __future__ import annotations
import copy
import json
import random
import time
from sqlalchemy import JSON, Integer, String, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, SessionLocal, engine

MAX_QUERIES=200
MAX_HISTORY=200
MAX_CANDIDATES=1000
MAX_NAME=300
MAX_QUERY=500

class QueryJournalError(RuntimeError):
    pass

class QueryJournalRow(Base):
    __tablename__='m22_query_journals'
    tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    state:Mapped[dict]=mapped_column(JSON,nullable=False)

class QueryJournal:
    def __init__(self,tenant_id,*,session_factory=None,db_engine=None):
        if type(tenant_id) is not str or not tenant_id.strip() or len(tenant_id)>120:
            raise ValueError('invalid tenant identity')
        self.tenant_id=tenant_id
        self.sessions=session_factory or SessionLocal
        QueryJournalRow.__table__.create(db_engine or engine,checkfirst=True)

    def read(self):
        with self.sessions() as db:
            row=db.get(QueryJournalRow,self.tenant_id)
            return copy.deepcopy(row.state) if row else {'queries':{},'history':[]}

    def history(self):
        return self.read()['history']

    def diff(self,query):
        row=self.read()['queries'].get(query)
        return copy.deepcopy(row['diff']) if row else None

    def preflight(self,query):
        if type(query) is not str or not query or len(query)>MAX_QUERY:
            raise ValueError('query must have 1..500 characters')
        state=self.read()
        if query not in state['queries'] and len(state['queries'])>=MAX_QUERIES:
            raise QueryJournalError('query journal capacity exceeded')

    def record(self,query,snapshot,*,at,kinds=None):
        if type(query) is not str or not query or len(query)>MAX_QUERY:
            raise ValueError('query must have 1..500 characters')
        if type(snapshot) is not dict or len(snapshot)>MAX_CANDIDATES:
            raise ValueError('query snapshot capacity exceeded')
        for key,name in snapshot.items():
            if (type(key) is not str or len(key)!=64 or any(c not in '0123456789abcdef' for c in key)
                    or type(name) is not str or len(name)>MAX_NAME):
                raise ValueError('invalid query snapshot')
        if type(at) is not str or not at or len(at)>64:
            raise ValueError('invalid query timestamp')
        if kinds is not None and (type(kinds) is not list or any(
                type(k) is not str or not k or len(k)>40 for k in kinds) or len(kinds)>32):
            raise ValueError('invalid query kinds')
        for attempt in range(64):
            contended=False
            with self.sessions() as db:
                row=db.get(QueryJournalRow,self.tenant_id)
                state=copy.deepcopy(row.state) if row else {'queries':{},'history':[]}
                previous=state['queries'].get(query)
                if previous is None and len(state['queries'])>=MAX_QUERIES:
                    raise QueryJournalError('query journal capacity exceeded')
                before=previous['snapshot'] if previous else {}
                diff={'first_run':previous is None,
                      'added':[snapshot[k] for k in snapshot if previous is not None and k not in before],
                      'removed':[before[k] for k in before if k not in snapshot]}
                state['queries'][query]={'snapshot':dict(snapshot),'diff':diff}
                state['history']=(state['history']+[{'query':query,'kinds':copy.deepcopy(kinds),
                                                   'at':at,'count':len(snapshot)}])[-MAX_HISTORY:]
                if len(json.dumps(state,ensure_ascii=True).encode('utf-8'))>4*1024*1024:
                    raise QueryJournalError('query journal byte capacity exceeded')
                if row is None:
                    db.add(QueryJournalRow(tenant_id=self.tenant_id,revision=1,state=state))
                    try:db.commit()
                    except IntegrityError:
                        db.rollback();contended=True
                else:
                    changed=db.execute(update(QueryJournalRow).where(
                        QueryJournalRow.tenant_id==self.tenant_id,
                        QueryJournalRow.revision==row.revision).values(revision=row.revision+1,state=state))
                    if changed.rowcount!=1:
                        db.rollback();contended=True
                    else:
                        db.commit()
                if not contended:
                    return copy.deepcopy(diff)
            time.sleep(random.uniform(0,min(0.008,0.0005*(2**min(attempt,4)))))
        raise QueryJournalError('query journal concurrent update conflict')
