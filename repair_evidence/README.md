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
