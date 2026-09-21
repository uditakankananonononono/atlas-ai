from __future__ import annotations
import os
from dataclasses import dataclass
from urllib.parse import urlparse

class ConfigError(ValueError): pass

@dataclass(frozen=True)
class ProductionConfig:
    environment: str
    database_url: str
    redis_url: str
    secret_provider: str
    oidc_issuer: str
    oidc_audience: str
    rate_limit_per_minute: int
    request_timeout_seconds: float
    log_level: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ProductionConfig":
        e = dict(os.environ if env is None else env)
        def required(name: str) -> str:
            value=e.get(name,"").strip()
            if not value: raise ConfigError(f"{name} is required")
            return value
        environment=e.get("ATLAS_ENV","development")
        database_url=e.get("ATLAS_DATABASE_URL","sqlite:///./atlas.db")
        redis_url=e.get("ATLAS_REDIS_URL","redis://localhost:6379/0")
        provider=e.get("ATLAS_SECRET_PROVIDER","environment")
        issuer=e.get("ATLAS_OIDC_ISSUER","")
        audience=e.get("ATLAS_OIDC_AUDIENCE","")
        try:
            limit=int(e.get("ATLAS_RATE_LIMIT_PER_MINUTE","120")); timeout=float(e.get("ATLAS_REQUEST_TIMEOUT_SECONDS","30"))
        except ValueError as exc: raise ConfigError("rate limit and timeout must be numeric") from exc
        if limit < 1 or timeout <= 0: raise ConfigError("rate limit and timeout must be positive")
        if provider not in {"environment","platform-environment","gcp-secret-manager","vault-literal"}: raise ConfigError("unsupported ATLAS_SECRET_PROVIDER")
        if environment == "production":
            database_url=required("ATLAS_DATABASE_URL"); redis_url=required("ATLAS_REDIS_URL")
            issuer=required("ATLAS_OIDC_ISSUER"); audience=required("ATLAS_OIDC_AUDIENCE")
            if urlparse(database_url).scheme not in {"postgresql","postgresql+psycopg"}: raise ConfigError("production database must be PostgreSQL")
            if urlparse(redis_url).scheme not in {"redis","rediss"}: raise ConfigError("production cache must be Redis")
            if provider == "environment": raise ConfigError("production requires an external secret provider")
            if provider == "platform-environment" and e.get("ATLAS_TRUST_PLATFORM_SECRETS") != "1": raise ConfigError("platform environment secrets require explicit trust")
        return cls(environment,database_url,redis_url,provider,issuer,audience,limit,timeout,e.get("ATLAS_LOG_LEVEL","INFO"))
