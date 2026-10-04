"""Operator-owned third-party accounts (API keys/tokens in process env) are NOT user credentials.

Presence of an env key is configuration, not a grant that every tenant may spend that account/quota or act through it.
A tenant may use the operator's accounts only if its id is listed exactly in ATLAS_OPERATOR_ACCOUNT_TENANTS (comma separated,
no wildcard). Whoever deploys decides that list; this code never populates it. Unlisted tenants fail closed.
"""
from __future__ import annotations
import os


def operator_account_granted(tenant_id: str | None) -> bool:
    if not tenant_id:
        return False
    granted = {t.strip() for t in os.getenv("ATLAS_OPERATOR_ACCOUNT_TENANTS", "").split(",") if t.strip()}
    return tenant_id in granted
