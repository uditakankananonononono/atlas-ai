"""Explicit read-only worker assembly. No production service installation."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from collections.abc import Mapping, Sequence
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from psycopg import OperationalError as PsycopgOperationalError
from instinct_models.providers import ProviderError, require_loopback_url
from .bounded import CANCEL_GRACE
from .engine import Engine
from .goals import GoalStore
from .model_adapter import LocalSharedModel
from .tools import ReadOnlyToolRegistry, Tool
from .types import ToolRisk
from .worker import Worker


class ConfigurationError(ValueError):
    """Safe diagnostic: no raw environment values or credentials."""


def _fail() -> None:
    raise ConfigurationError("invalid Claire worker configuration") from None


@dataclass(frozen=True, repr=False)
class WorkerConfiguration:
    database_url: str = field(repr=False)
    provider: str
    model_url: str = field(repr=False)
    model_name: str = field(repr=False)
    worker_id: str = field(repr=False)
    lease_seconds: int = 120
    model_timeout: float = 30
    tool_timeout: float = 30
    development_schema: bool = False

    def __repr__(self) -> str:
        return "WorkerConfiguration(redacted)"

    def __post_init__(self) -> None:
        # Validation is also mandatory for direct construction, not just env.
        try:
            if not isinstance(self.database_url, str):
                _fail()
            url = make_url(self.database_url)
            if url.get_backend_name() == "sqlite":
                if not url.database or url.database == ":memory:" or url.query:
                    _fail()
            elif url.get_backend_name() != "postgresql" or not url.database:
                _fail()
            if self.provider not in ("ornith", "inkling", "hermes"):
                _fail()
            if not isinstance(self.model_url, str):
                _fail()
            require_loopback_url(self.model_url)
            if any(not isinstance(v, str) or not v.strip() or len(v) > 200
                   for v in (self.model_name, self.worker_id)):
                _fail()
            if type(self.lease_seconds) is not int or not 2 <= self.lease_seconds <= 3600:
                _fail()
            for timeout in (self.model_timeout, self.tool_timeout):
                if type(timeout) not in (int, float) or not math.isfinite(timeout) or not .05 <= timeout <= 3600:
                    _fail()
                if timeout + CANCEL_GRACE >= self.lease_seconds:
                    _fail()
            if type(self.development_schema) is not bool:
                _fail()
        except (ValueError, TypeError, ProviderError):
            _fail()

    @classmethod
    def from_environment(cls, env: Mapping[str, str]) -> WorkerConfiguration:
        # No inherited generic model settings or hosted fallback.
        try:
            schema = env.get("ATLAS_CLAIRE_WORKER_DEV_SCHEMA", "0")
            if schema not in ("0", "1") or (schema == "1" and env.get("ATLAS_ENV") != "development"):
                _fail()
            return cls(
                database_url=env["ATLAS_CLAIRE_RUNTIME_DB"],
                provider=env["ATLAS_CLAIRE_MODEL_PROVIDER"],
                model_url=env["ATLAS_CLAIRE_MODEL_URL"],
                model_name=env["ATLAS_CLAIRE_MODEL_NAME"],
                worker_id=env["ATLAS_CLAIRE_WORKER_ID"],
                lease_seconds=int(env.get("ATLAS_CLAIRE_LEASE_SECONDS", "120")),
                model_timeout=float(env.get("ATLAS_CLAIRE_MODEL_TIMEOUT", "30")),
                tool_timeout=float(env.get("ATLAS_CLAIRE_TOOL_TIMEOUT", "30")),
                development_schema=schema == "1",
            )
        except (KeyError, ValueError, TypeError):
            _fail()


class ConfiguredReadOnlyWorker:
    """Operator owns tools. No env-based Python plugin imports or default registry.

    No caller tenant header: existing claims supply tenant/actor/lease. Not a daemon
    or process supervisor; bounded drain may wait for at most its configured calls.
    """

    def __init__(self, config: WorkerConfiguration, tools: Sequence[Tool]):
        if not tools or any(t.risk is not ToolRisk.READ for t in tools):
            raise ConfigurationError("a nonempty read-only tool set is required")
        registry = ReadOnlyToolRegistry(call_timeout=config.tool_timeout)
        for tool in tools:
            registry.register(tool)
        model = LocalSharedModel.select(config.provider, config.model_url, config.model_name)
        try:
            self.store = GoalStore(config.database_url, lease_seconds=config.lease_seconds,
                                   create_schema=config.development_schema, owner_may_self_approve=False)
        except (SQLAlchemyOperationalError, PsycopgOperationalError):
            raise ConfigurationError("Claire runtime database is unavailable") from None
        self.worker = Worker(self.store, lambda claim: Engine(model, registry, max_steps=claim.max_steps,
                              model_timeout_seconds=config.model_timeout), config.worker_id)

    async def drain(self, limit: int) -> list[str]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ConfigurationError("drain limit must be between 1 and 100")
        goals = []
        for _ in range(limit):
            goal = await self.worker.run_once()
            if goal is None:
                break
            goals.append(goal)
        return goals

    def close(self) -> None:
        self.store.close()


@dataclass(frozen=True)
class SupervisionResult:
    status: str  # queue_empty | job_limit | database_unavailable
    goals: tuple[str, ...]
    database_failures: int


async def supervise_read_only(worker: ConfiguredReadOnlyWorker, *, max_jobs: int = 10,
                             max_database_failures: int = 3) -> SupervisionResult:
    """Bounded in-process DB recovery, not an OS process/service supervisor.

    Only declared DB OperationalError is retried. One full lease wait prevents a
    still-live failed claim being treated as an empty queue and abandoned. Existing
    fencing and effect reconciliation decide whether work is safe to retry.
    Waiting is cancellable; sync DB calls themselves have no wall-time bound here.
    """
    import asyncio
    if type(max_jobs) is not int or not 1 <= max_jobs <= 100:
        raise ConfigurationError("max_jobs must be between 1 and 100")
    if type(max_database_failures) is not int or not 1 <= max_database_failures <= 10:
        raise ConfigurationError("max_database_failures must be between 1 and 10")
    goals: list[str] = []
    failures = 0
    while len(goals) < max_jobs:
        try:
            goal = await worker.worker.run_once()
        except (SQLAlchemyOperationalError, PsycopgOperationalError):
            failures += 1
            # Dispose drops stale idle connections; already checked-out handles
            # may outlive disposal. It neither resets goals nor clears effects.
            try:
                worker.store.engine.dispose()
            except (SQLAlchemyOperationalError, PsycopgOperationalError):
                return SupervisionResult("database_unavailable", tuple(goals), failures)
            if failures >= max_database_failures:
                return SupervisionResult("database_unavailable", tuple(goals), failures)
            await asyncio.sleep(worker.store.lease_seconds + CANCEL_GRACE)
            continue
        if goal is None:
            return SupervisionResult("queue_empty", tuple(goals), failures)
        goals.append(goal)
    return SupervisionResult("job_limit", tuple(goals), failures)
