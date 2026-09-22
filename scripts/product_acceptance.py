#!/usr/bin/env python3
"""Production acceptance harness for Atlas AI.

Every check lands in exactly one bucket:

- accepted:   verified against the live system (a probe ran and passed)
- configured: the artifact or setting exists, but no live evidence backs it
- missing:    unaccepted - neither live evidence nor configuration

The report never upgrades "configured" to "accepted": a green check means a
real probe passed, not that a file exists. Exit code is 1 when any check is
missing; --require-live also fails configured-but-unproven checks.

Usage: python scripts/product_acceptance.py [--json] [--require-live]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

ACCEPTED = "accepted"
CONFIGURED = "configured"
MISSING = "missing"


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Probers:
    """Live probes. Each returns True/False, or None when it cannot run."""
    database: Callable[[], bool | None]
    redis: Callable[[], bool | None]
    migrations: Callable[[], bool | None]
    oidc_jwks: Callable[[], bool | None]
    workers: Callable[[], bool | None]


def _unavailable() -> None:
    return None


def default_probers() -> Probers:
    def database() -> bool | None:
        try:
            from sqlalchemy import text
            from app.core.database import engine
            with engine.connect() as connection:
                return connection.execute(text("SELECT 1")).scalar_one() == 1
        except Exception:
            return None

    def redis() -> bool | None:
        try:
            from redis import Redis
            client = Redis.from_url(
                os.getenv("ATLAS_REDIS_URL", "redis://localhost:6379/0"),
                socket_connect_timeout=2, socket_timeout=2)
            try:
                return bool(client.ping())
            finally:
                client.close()
        except Exception:
            return None

    def migrations() -> bool | None:
        try:
            from alembic.config import Config
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory
            from app.core.database import engine
            config = Config("alembic.ini")
            head = ScriptDirectory.from_config(config).get_current_head()
            with engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
            return current is not None and current == head
        except Exception:
            return None

    def oidc_jwks() -> bool | None:
        issuer = os.getenv("ATLAS_OIDC_ISSUER", "").strip()
        if not issuer:
            return None
        try:
            import httpx
            from app.auth.context import OIDCVerifier
            verifier = OIDCVerifier(issuer, os.getenv("ATLAS_OIDC_AUDIENCE", ""))
            response = httpx.get(verifier.jwks_uri, timeout=5)
            return response.status_code == 200 and bool(response.json().get("keys"))
        except Exception:
            return None

    def workers() -> bool | None:
        try:
            from app.workers.celery_app import celery_app
            replies = celery_app.control.inspect(timeout=2).ping()
            return bool(replies)
        except Exception:
            return None

    return Probers(database=database, redis=redis, migrations=migrations,
                   oidc_jwks=oidc_jwks, workers=workers)


def _live_or_configured(name: str, probe: Callable[[], bool | None],
                        configured: bool, configured_detail: str) -> Check:
    result = probe()
    if result is True:
        return Check(name, ACCEPTED, "live probe passed")
    if result is False and configured:
        return Check(name, MISSING, "live probe failed against the configured target")
    if configured:
        return Check(name, CONFIGURED, configured_detail)
    return Check(name, MISSING, "not configured and no live evidence")


def check_auth_config(env: dict[str, str], jwks_probe: Callable[[], bool | None]) -> Check:
    try:
        from app.platform.config import ProductionConfig
        config = ProductionConfig.from_env(env)
    except Exception as exc:
        return Check("auth_config", MISSING, f"production config rejected: {exc}")
    if config.environment == "production":
        live = jwks_probe()
        if live is True:
            return Check("auth_config", ACCEPTED,
                         f"OIDC issuer {config.oidc_issuer} serves reachable JWKS")
        return Check("auth_config", CONFIGURED,
                     f"OIDC issuer {config.oidc_issuer} configured; JWKS not live-verified")
    return Check("auth_config", CONFIGURED,
                 f"environment={config.environment}; production auth requirements not in force")


def check_workers(env: dict[str, str], probe: Callable[[], bool | None]) -> Check:
    redis_url = env.get("ATLAS_REDIS_URL", "").strip()
    if not redis_url:
        return Check("workers", MISSING, "ATLAS_REDIS_URL unset; no broker configured")
    live = probe()
    if live is True:
        return Check("workers", ACCEPTED, "celery worker answered ping")
    if live is False:
        return Check("workers", MISSING, "broker configured but no worker answered ping")
    return Check("workers", CONFIGURED, f"broker {redis_url!r} configured; no live worker evidence")


def check_adapters() -> Check:
    from app.runtime.production import build_runtime
    runtime = build_runtime()
    handlers = getattr(runtime, "handlers", {})
    count = len(handlers)
    if count == 0:
        return Check("adapters", MISSING, "production runtime registry has no adapters")
    modules = {key[0] for key in handlers} if all(isinstance(k, tuple) for k in handlers) else set()
    uncovered = [m for m in range(26) if m not in modules]
    detail = (f"{count} production adapter operations registered across "
              f"{len(modules)} modules (static configuration, not live invocation evidence)")
    if uncovered:
        detail += f"; modules without any adapter: {uncovered}"
    return Check("adapters", CONFIGURED, detail)


def check_monitoring(repo_root: Path, env: dict[str, str]) -> Check:
    artifacts = ["deploy/otel/collector.yaml", "deploy/grafana/dashboard.json", "docs/SLO_ALERTS.md"]
    present = [a for a in artifacts if (repo_root / a).exists()]
    endpoint = env.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if len(present) == len(artifacts) and endpoint:
        return Check("monitoring", CONFIGURED,
                     "collector, dashboard and SLO rules present, OTLP endpoint set; "
                     "no live alert-firing evidence")
    missing = [a for a in artifacts if a not in present]
    return Check("monitoring", MISSING,
                 f"missing artifacts: {missing or 'OTEL_EXPORTER_OTLP_ENDPOINT'}")


def check_backup_restore(repo_root: Path) -> Check:
    runbook = repo_root / "docs/runbooks/BACKUP_RESTORE.md"
    if not runbook.exists():
        return Check("backup_restore", MISSING, "no backup/restore runbook")
    evidence = list((repo_root / "docs").glob("**/*restore*drill*")) + \
        list((repo_root / "docs").glob("**/*backup*evidence*"))
    if evidence:
        return Check("backup_restore", CONFIGURED,
                     f"runbook plus drill record {evidence[0].relative_to(repo_root)}; "
                     "provider operation IDs not re-verified")
    return Check("backup_restore", MISSING,
                 "runbook exists but no restore-drill evidence; the repo makes no backup claim")


def run(env: dict[str, str] | None = None, probers: Probers | None = None,
        repo_root: Path | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    probers = probers or default_probers()
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    db_configured = bool(env.get("ATLAS_DATABASE_URL", "").strip())
    redis_configured = bool(env.get("ATLAS_REDIS_URL", "").strip())
    checks = [
        check_auth_config(env, probers.oidc_jwks),
        _live_or_configured("database", probers.database, db_configured,
                            "ATLAS_DATABASE_URL set; no live query evidence"),
        _live_or_configured("migrations", probers.migrations, db_configured,
                            "database configured; revision match not live-verified"),
        _live_or_configured("redis", probers.redis, redis_configured,
                            "ATLAS_REDIS_URL set; no live ping evidence"),
        check_workers(env, probers.workers),
        check_adapters(),
        check_monitoring(repo_root, env),
        check_backup_restore(repo_root),
    ]
    by_status = {ACCEPTED: [], CONFIGURED: [], MISSING: []}
    for check in checks:
        by_status[check.status].append(check.name)
    if by_status[MISSING]:
        verdict = "unaccepted"
    elif by_status[CONFIGURED]:
        verdict = "configured_unaccepted"
    else:
        verdict = "accepted"
    return {
        "verdict": verdict,
        "accepted": by_status[ACCEPTED],
        "configured_unaccepted": by_status[CONFIGURED],
        "missing": by_status[MISSING],
        "checks": [vars(c) for c in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    parser.add_argument("--require-live", action="store_true",
                        help="fail unless every check is live-accepted")
    args = parser.parse_args(argv)
    report = run()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in report["checks"]:
            print(f"[{check['status']:>10}] {check['name']}: {check['detail']}")
        print(f"verdict: {report['verdict']}")
    if report["missing"]:
        return 1
    if args.require_live and report["configured_unaccepted"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
