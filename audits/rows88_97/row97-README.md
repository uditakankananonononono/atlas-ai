# Row 97 exact wire preview

Exact selector: tests/apply/test_pitch_execution.py, --noconftest -q -rf,
Python 3.12, per-run timeout 45 seconds. Core mutations: descriptor-bound RFC
Message-ID, wire SHA, exact subject, non-authority preview status and attachment
refusal. Initial run: attachment-refusal mutant SURVIVED. Added a valid
attachment-descriptor negative; all five rerun CAUGHT by FAILED tests. Both
run receipts are retained externally. Source SHA restored each time.

UNTESTED: live send, real destination verification, delivered status, provider
lookup/reconciliation, manuscript attachments and full-repository regression.
Message-ID is not provider idempotency or permission to retry ambiguity.
Existing M00/claim guards unchanged; literal row stays PARTIAL.
