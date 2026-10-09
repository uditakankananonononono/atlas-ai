"""Configuration protection and synthetic-provider integration, not release proof."""
import asyncio
from dataclasses import replace
import pytest
from pydantic import BaseModel
from app.modules.m21_claire.runtime.configuration import ConfigurationError, ConfiguredReadOnlyWorker, WorkerConfiguration
from app.modules.m21_claire.runtime.tools import Tool
from app.modules.m21_claire.runtime.types import ToolRisk
from app.modules.m21_claire.runtime.goals import GoalStore
from app.modules.m21_claire.runtime.model_adapter import LocalSharedModel
from app.modules.m21_claire.runtime.types import AgentDecision, ToolCall


def config(tmp_path):
    return WorkerConfiguration(f"sqlite:///{tmp_path}/g.db", "hermes", "http://127.0.0.1:8000/v1", "test-model", "w", development_schema=True)


@pytest.mark.parametrize("change", [
    {"database_url":"sqlite://"}, {"database_url":"sqlite:///:memory:"},
    {"database_url":"sqlite:///file:test?mode=memory&uri=true"},
    {"database_url":"mysql://u:secret@h/db"}, {"database_url":"postgresql://host"},
    {"provider":"hosted"}, {"model_url":"http://user:secret@localhost:8000/v1"},
    {"model_url":"http://example.com:8000/v1"}, {"model_name":""}, {"worker_id":""},
    {"lease_seconds":True}, {"lease_seconds":1}, {"model_timeout":120},
    {"tool_timeout":119.9}, {"model_timeout":float("nan")}, {"tool_timeout":float("inf")},
    {"model_timeout":True}, {"development_schema":"1"},
])
def test_invalid_configuration_is_safe(tmp_path, change):
    with pytest.raises(ConfigurationError) as caught: replace(config(tmp_path), **change)
    assert str(caught.value) == "invalid Claire worker configuration"
    assert "secret" not in str(caught.value)


def test_repr_redacted_and_postgres_allowed(tmp_path):
    c = replace(config(tmp_path), database_url="postgresql://user:secret@localhost/db")
    assert repr(c) == "WorkerConfiguration(redacted)"


def test_environment_explicit_and_schema_opt_in(tmp_path):
    env = {"ATLAS_CLAIRE_RUNTIME_DB":f"sqlite:///{tmp_path}/x.db", "ATLAS_CLAIRE_MODEL_PROVIDER":"hermes",
           "ATLAS_CLAIRE_MODEL_URL":"http://localhost:8000/v1", "ATLAS_CLAIRE_MODEL_NAME":"m", "ATLAS_CLAIRE_WORKER_ID":"w"}
    assert not WorkerConfiguration.from_environment(env).development_schema
    for key in env:
        missing = dict(env); del missing[key]
        with pytest.raises(ConfigurationError): WorkerConfiguration.from_environment(missing)
    with pytest.raises(ConfigurationError): WorkerConfiguration.from_environment({**env, "ATLAS_CLAIRE_WORKER_DEV_SCHEMA":"1"})
    assert WorkerConfiguration.from_environment({**env, "ATLAS_CLAIRE_WORKER_DEV_SCHEMA":"1", "ATLAS_ENV":"development"}).development_schema


class Args(BaseModel): key: str
class Lookup(Tool):
    name, arguments_model = "lookup", Args
    def run(self, arguments): return {"value":arguments.key}
class Write(Lookup): risk = ToolRisk.WRITE


def test_empty_or_write_tools_refused(tmp_path):
    for tools in ([], [Write()]):
        with pytest.raises(ConfigurationError): ConfiguredReadOnlyWorker(config(tmp_path), tools)


def test_configured_worker_consumes_separate_store_and_bounded_drain(tmp_path, monkeypatch):
    class Script:
        async def decide(self, messages):
            if len(messages) == 2:
                return AgentDecision(tool_call=ToolCall(name="lookup", arguments={"key":"k"}))
            return AgentDecision(final="transport test only")
    monkeypatch.setattr(LocalSharedModel, "select", lambda *a: Script())
    c = config(tmp_path)
    worker = ConfiguredReadOnlyWorker(c, [Lookup()])
    api_store = GoalStore(c.database_url)
    ids = [api_store.create("tenant", "actor", "lookup k", [{"kind":"tool_receipt", "tool":"lookup", "min_count":1}], 3) for _ in range(2)]
    try:
        assert len(asyncio.run(worker.drain(1))) == 1
        statuses = [api_store.get("tenant", "actor", gid)["status"] for gid in ids]
        assert sorted(statuses) == ["completed", "queued"]
        assert len(asyncio.run(worker.drain(5))) == 1
        assert asyncio.run(worker.drain(1)) == []
        for gid in ids:
            body = api_store.get("tenant", "actor", gid)
            assert body["status"] == "completed"
            assert body["report"]["receipts"][0]["content"] == {"value":"k"}
        assert worker.store.owner_may_self_approve is False
        for limit in (True, 0, 101):
            with pytest.raises(ConfigurationError): asyncio.run(worker.drain(limit))
    finally: worker.close(); api_store.close()
    fresh = GoalStore(c.database_url)
    assert all(fresh.get("tenant", "actor", gid)["status"] == "completed" for gid in ids)
    fresh.close()


@pytest.mark.parametrize("driver", ["sqlalchemy", "psycopg"])
def test_database_startup_operational_error_is_sanitized(tmp_path, monkeypatch, driver):
    from sqlalchemy.exc import OperationalError
    from psycopg import OperationalError as PsycopgError
    from app.modules.m21_claire.runtime import configuration
    import traceback
    raw = "driver host=private.example port=5544 password=secret"
    error = OperationalError("connect", {}, RuntimeError(raw)) if driver == "sqlalchemy" else PsycopgError(raw)
    def unavailable(*args, **kwargs): raise error
    monkeypatch.setattr(configuration, "GoalStore", unavailable)
    with pytest.raises(ConfigurationError) as caught:
        ConfiguredReadOnlyWorker(config(tmp_path), [Lookup()])
    assert str(caught.value) == "Claire runtime database is unavailable"
    rendered = "".join(traceback.format_exception(caught.value))
    assert not any(s in rendered for s in ("private.example", "5544", "password=secret"))
    assert caught.value.__suppress_context__ is True
