# Row 60: m21_claire owner_interview.py and training.py mutation deepening

The existing owner-interview test file does not collect on Python 3.10 (the m21_claire package import chain needs StrEnum).
`tests/modules/test_m21_row60_standalone.py` loads both modules by path. owner_interview runs against in-memory SQLite; training.py gets a stub `ApprovalRequest` and a fake approvals store. Offline, 14 tests.

Battery `batteries/b60.py`: 31 mutants. W1-W16 cover owner_interview (consent gates, validation, duplicate answers, revoke scoping, active-answer filter, action-permission flag, claim label, delete scope). X1-X15 cover training (sample bounds, provenance, ranking validation, LoRA-only rule, approval payload flags, action type, status, hash coverage).

Final: 31 CAUGHT, 0 SURVIVED, 0 INVALID; source SHA restored. Receipt: `receipts_b60.txt`.
Preserved earlier runs:
- `receipts_b60_run1_X14_not_applicable.txt`: 29 CAUGHT, 1 NOT-APPLICABLE (the order-stability mutant X14 matched its old text twice; replaced by redesigned X14 and X15, which are first-example hash-coverage mutants).
- `receipts_b60_run2_with_2_survivors.txt`: 29 CAUGHT, 2 SURVIVED (X14, X15: hash tests did not vary later examples). Fixed by `test_dataset_hash_covers_every_example`.
CAUGHT = pytest exits 1 with FAILED lines.

Not covered: the old test file is not run on 3.10; the real ApprovalRequest model and approval storage are stubbed.
Run: `python audits/rows-47-64-deepening/run_mutations.py b60`
