# Builders

One line per builder claim. Claim a distinct component before building so parallel branches do not collide. Integrator merges branches after the full suite passes.

| Builder | Branch | Component claimed | Files owned | Claimed |
|---|---|---|---|---|
| PB5 | pb5 | M22 Tools Hub durable install pipeline: tenant-persisted proposals and tool portfolio; worker job that runs the SecurityScanner and ToolInstaller only after a consumed approval and writes the receipt itself (no caller-supplied receipts); rollback from the stored receipt | `backend/app/modules/m22_tools_hub/pipeline*.py`, new M22 tests, M22 migration | 2026-09-24 11:12 IST |
