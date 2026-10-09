"""Bounded supervisor logic protections. Fault doubles are not live PG evidence."""
import asyncio
from types import SimpleNamespace
import pytest
from sqlalchemy.exc import OperationalError
from psycopg import OperationalError as PsycopgError
from app.modules.m21_claire.runtime.configuration import ConfigurationError,supervise_read_only


class Script:
    def __init__(self,items): self.items=iter(items);self.calls=0
    async def run_once(self):
        self.calls+=1;item=next(self.items)
        if isinstance(item,BaseException):raise item
        return item


def wrapper(items,dispose=None):
    disposed=[]
    return SimpleNamespace(worker=Script(items),store=SimpleNamespace(lease_seconds=3,engine=SimpleNamespace(dispose=dispose or (lambda:disposed.append(True))))),disposed


def test_database_retry_waits_full_lease_and_returns_safe_status(monkeypatch):
    waits=[]
    async def sleep(seconds):waits.append(seconds)
    monkeypatch.setattr(asyncio,'sleep',sleep)
    raw='host=private port=5432 password=secret'
    worker,disposed=wrapper([OperationalError('connect',{},RuntimeError(raw)),'goal',None])
    result=asyncio.run(supervise_read_only(worker))
    assert result.status=='queue_empty' and result.goals==('goal',) and result.database_failures==1
    assert waits==[3.2] and disposed==[True]
    assert 'private' not in repr(result) and 'secret' not in repr(result)


def test_failure_budget_is_global_and_finite(monkeypatch):
    waits=[]
    async def sleep(seconds):waits.append(seconds)
    monkeypatch.setattr(asyncio,'sleep',sleep)
    worker,disposed=wrapper([PsycopgError('secret')]*3)
    result=asyncio.run(supervise_read_only(worker,max_database_failures=3))
    assert result.status=='database_unavailable' and result.database_failures==3
    assert worker.worker.calls==3 and len(waits)==2 and len(disposed)==3


def test_job_limit_stops_and_unexpected_bug_stays_loud():
    worker,_=wrapper(['one','two',None])
    assert asyncio.run(supervise_read_only(worker,max_jobs=1)).status=='job_limit'
    assert worker.worker.calls==1
    worker,_=wrapper([TypeError('bug')])
    with pytest.raises(TypeError):asyncio.run(supervise_read_only(worker))


def test_disposal_failure_is_safe_terminal_status():
    def dispose():raise PsycopgError('secret diagnostic')
    worker,_=wrapper([PsycopgError('private')],dispose)
    result=asyncio.run(supervise_read_only(worker))
    assert result.status=='database_unavailable' and 'secret' not in repr(result)


def test_cancellation_during_recovery_propagates(monkeypatch):
    async def sleep(seconds):raise asyncio.CancelledError()
    monkeypatch.setattr(asyncio,'sleep',sleep)
    worker,_=wrapper([PsycopgError('private')])
    with pytest.raises(asyncio.CancelledError):asyncio.run(supervise_read_only(worker))
    assert worker.worker.calls==1


@pytest.mark.parametrize('limits',[{'max_jobs':True},{'max_jobs':0},{'max_jobs':101},{'max_database_failures':True},{'max_database_failures':0},{'max_database_failures':11}])
def test_bad_limits(limits):
    worker,_=wrapper([])
    with pytest.raises(ConfigurationError):asyncio.run(supervise_read_only(worker,**limits))
