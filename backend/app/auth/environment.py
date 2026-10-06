"""One fail-closed environment policy for auth and platform configuration."""
from __future__ import annotations
import os
from collections.abc import Mapping


def atlas_environment(env: Mapping[str,str] | None = None) -> str:
    e=os.environ if env is None else env
    return e.get('ATLAS_ENV','production').strip().lower() or 'production'


def insecure_development_auth_enabled(env: Mapping[str,str] | None = None) -> bool:
    e=os.environ if env is None else env
    # Explicit allowlist. Unknown/deployed environment names never bypass auth.
    return e.get('ATLAS_DEV_NO_AUTH')=='1' and atlas_environment(e) in {'development','local'}
