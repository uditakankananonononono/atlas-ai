# M23 bounded truth and approval repair

Baseline: 313309be. Python 3.12.14. Local branch: repair/m23-truth-approval.

Reproduction:
- Baseline existing M23 suite: 128 passed, one dependency deprecation warning.
- Final added regression tests on untouched baseline: 31 failed, 1 passed.
- Patched M23 suite including 32 added tests: 160 passed, one dependency deprecation warning.
- Commands: python -m pytest tests/modules/test_m23_truth_repair.py -q; python -m pytest tests/modules/test_m23* tests/test_m23_spec_audit.py -q.
- Logs and dependency freeze are included. Collection initially lacked asn1crypto; installed required package and reran successfully. Earlier intermediate logs retained as debugging evidence, not final acceptance.

No full repository test run is claimed. No external actions, model execution or live data checks were performed. This lane does not complete the M23 specification. Independent audit is required before integration.

Approval remains blocked: no exact M23 external executor/M00 action-payload contract exists, and a caller boolean or approval ID is not authority. No invented integration was added.

Monitoring reports independent verified coverage zero; valid URL/calendar metadata coverage is counted separately. It does not claim official-domain, content, freshness or completeness verification. Source metadata is caller input. Admission estimates, when supplied, remain explicitly unverified caller estimates. Missing estimates and missing budget/tuition are unavailable, never zero or reach by default.

All 62 previous full-spec verified-pushed labels are withdrawn to PARTIAL pending requirement-level independent verification. This is not a new 62-row behavioral acceptance result. Prior counts/statuses remain in the ledger. The 4/18/40 intake and later 62 verified claims are retained as conflicting historical reports.

API field changes are intentional: regex entities become entity_candidates; language support becomes a catalog with supported false; claimed encryption count replaces encryption proof; source links replace verified counts; top-100 candidate ranking is named caller-supplied. Consumers must not read old fields as proof.

No final essay prose is generated. No pushes, signups, submissions or third-party communications occur. Main is responsible for separate audit and final owner communication.

## Independent review follow-up

Review against e71f7f7 found invalid URL ports admitted as valid metadata, malformed record elements raising server errors, credential input contents reflected in response, and bool/NaN/negative financial amounts accepted. Added 20 review tests. All 52 truth regression tests on e71f7f7: 19 failed, 33 passed. Patched complete M23 suite: 180 passed, one dependency deprecation warning.

Repairs: parse/range-check URL ports; reject non-object monitoring records with 422; completely redact row58 inputs and return indices rather than untrusted credential identifiers; validate tuition and annual budget as finite nonnegative numeric values excluding bool, at schema and service boundaries. Unknown None stays unknown, explicit zero stays known. Mounted fit rejects malformed budgets with 422. No credential plaintext storage or encryption capability is claimed.

Consumer impact: row58 inputs always returns {redacted:true}; unencrypted_ids/rotation_due become claimed_unencrypted_indices/claimed_rotation_due_indices to prevent reflection of arbitrary secrets. Financial numeric strings and booleans no longer coerce to amounts; invalid financial or source-record inputs receive 422 instead of accepted calculations/500. Bad source ports yield invalid metadata, not verification. Existing repo consumers have not been accepted by this repair lane; external clients remain unknown. Independent reviewer found unauthenticated production access returns 401; development local access is open by design. Neither observation is an approval or production-readiness claim.
