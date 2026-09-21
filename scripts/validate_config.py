#!/usr/bin/env python3
from app.platform.config import ProductionConfig,ConfigError
try: ProductionConfig.from_env()
except ConfigError as exc: raise SystemExit(f"invalid Atlas configuration: {exc}")
print("Atlas configuration is valid")
