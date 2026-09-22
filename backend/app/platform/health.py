from __future__ import annotations
from dataclasses import dataclass
from typing import Callable


def readiness(database_probe: Callable[[], bool], redis_probe: Callable[[], bool], migration_current: Callable[[], bool]) -> tuple[bool, dict[str, bool]]:
    """Evaluate the three dependencies required before receiving traffic."""
    checks = {
        "database": _safe_probe(database_probe),
        "redis": _safe_probe(redis_probe),
        "migrations": _safe_probe(migration_current),
    }
    return all(checks.values()), checks


def _safe_probe(probe: Callable[[], bool]) -> bool:
    try:
        return bool(probe())
    except Exception:
        return False


def live_readiness() -> tuple[bool, dict[str, bool]]:
    """Probe configured dependencies and the Alembic revision without leaking errors/secrets."""
    return readiness(_database_ok, _redis_ok, _migration_ok)


def _database_ok() -> bool:
    from sqlalchemy import text
    from app.core.database import engine
    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1


def _redis_ok() -> bool:
    import os
    from redis import Redis
    client = Redis.from_url(os.getenv("ATLAS_REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=2, socket_timeout=2)
    try:
        return bool(client.ping())
    finally:
        client.close()


def _migration_ok() -> bool:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from app.core.database import engine
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    expected = set(script.get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    return bool(expected) and current == expected
