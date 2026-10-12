# M14 complete report identity

Base: direct-render/export patch on 914a449d. Replaces status-report prefix truncation
and unbound README UUID with SHA-256 of the complete kind, tenant, project ID, timezone-
aware subsecond generated time and body. Result is a valid 64-character report id;
long project IDs sharing their first 90 characters no longer collapse to one id.

Released selector:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m14_report_identity.py tests/modules/test_m14_report_gate.py tests/modules/test_m14_wiring.py -q

Result: 58 passed, two environment/deprecation warnings. Final mutation receipts:
CAUGHT=6, SURVIVED=0, INVALID=0, NOT-APPLICABLE=0; source SHA-256 restore true.
CAUGHT requires pytest rc=1 and FAILED IDs, not collection/setup error, crash or timeout.

Limits: this is report identity, not a replay/spend token. Identical complete identities
can intentionally produce the same id; report_gate does not deduplicate them. SHA-256
collision resistance is assumed, not empirically proved. The actual bytes have a
separate report_sha256 in the ledger. Tenant identity comes from the project object,
not new authentication. Ledgers remain in memory without a persistence sink. Direct
renderer checks use private transient UUIDs, not the service's provenance ledger. No
claim that report labeling verifies artifact quality or arbitrary prose.
