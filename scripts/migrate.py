#!/usr/bin/env python3
"""Production-safe schema entry point. Never calls create_all in production."""
import os,subprocess,sys
if os.getenv("ATLAS_ENV","development")=="production":
 raise SystemExit(subprocess.call([sys.executable,"-m","alembic","upgrade","head"]))
from app.core.database import Base,engine
from app.modules import registry as _registry  # noqa: F401
Base.metadata.create_all(engine)
print("development schema ready")
