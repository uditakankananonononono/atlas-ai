# M14 direct render and export label binding

Base: 914a449d. This closes the direct-renderer and alternate README export wiring
label-check gaps, not artifact validity or general factual verification.

Released selector:

    PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest tests/modules/test_m14_report_gate.py tests/modules/test_m14_reports.py tests/modules/test_m14_exports.py tests/modules/test_m14_wiring.py -q

Result: 80 passed, two environment/deprecation warnings. Tests use real pgserver
lifecycle where selected, fake project generation, and private local export directories.
No network, artifact publication or remote repository writes.

Both public renderers validate their actual output through report_gate before returning.
README carries an explicit UNVERIFIED provenance claim; milestone State is not a claim
label column (previous Status column would be mistaken for VERIFIED/UNVERIFIED labels).
Service export additionally gates the exact README bytes, including alternate renderer
output, and obtains gated STATUS bytes before creating directories or writing artifacts,
README, STATUS, manifest or zip. Tests inject real supplied-goal CLAIM markers into both
direct renderers and service export, separately test alternate renderers, assert no files
exist on refusal, and compare SHA-256 ledger digests to exported README/STATUS bytes.

Mutation receipts: five exact replacements, CAUGHT=5, SURVIVED=0, INVALID=0,
NOT-APPLICABLE=0. CAUGHT requires rc=1 plus FAILED ids and no collection/internal error,
crash or timeout; every source file is restored and SHA-256 checked. The first early-write
mutant hit a different method and survived; it was narrowed to export_project and rerun.

Limits: claim_status grammar covers explicit CLAIM markers and qualifying label tables,
not arbitrary prose. VERIFIED says a validator computed its result, not artifact goodness.
Renderer-supplied context remains caller-declared, not independently authenticated. Direct
renderer validation is transient (no durable ledger); service records are in memory without
a persistence sink. Generic write_project_files/create_zip are low-level byte utilities,
not gated arbitrary-document exporters. SCOPE and artifact payloads are not report-gated.
No control-flow proof of every future caller. Failure after admission or filesystem writes
is not an atomic rollback guarantee. Report-id truncation in status_report remains for the
separate identity patch; this patch does not claim to fix it.
