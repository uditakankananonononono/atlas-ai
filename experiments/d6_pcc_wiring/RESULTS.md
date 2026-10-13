# D6: proof-carrying conclusions wired into the improvement gate and Claire (Atlas)

Source pin: atlas-ai main f7ae6fe7 + the audited e6/e7/e8 v2 patch (pcc.py). New files only. Python 3.12.14, pytest 9.1.1, bubblewrap on a 2-core Linux box. Fixtures and adversarial cases are authored here.

## What was built
- `backend/app/self_improve/proof_carrying.py`: e8's four kinds (factorization, analysis, code_change, sourced_quote) with VERIFIED / UNVERIFIED / VERIFICATION_IMPOSSIBLE; confidence is returned separately and never read. `analysis` and `code_change` run evidence code under bubblewrap (new net namespace, read-only system mounts, private work dir, cleared env, rlimits CPU/AS/FSIZE/NOFILE/NPROC/CORE, wall timeout, process-group kill). If bwrap is missing or cannot start (probe `sandbox_ok`), those kinds fail closed: UNVERIFIED, SANDBOX_UNAVAILABLE, evidence never executed. Changes vs pcc.py: analysis runs twice (non-deterministic scripts rejected); code_change accepts only on exit 0 plus junit XML (exact N, no failure/error/skip) plus an agreeing stdout summary; bool/float/size-cap checks.
- `backend/app/self_improve/proof_gate.py`: `ProofCarryingGate(ImprovementGate)`. `authorize(plan, evidence, conclusions, advisory=())` requires a non-empty list of conclusions, each bound to the plan digest and VERIFIED; refusal code PLAN_REFUSED_UNPROVEN; ledger records `proofs_verified` (status, reason, confidence separately) before `authorized`. Advisory conclusions are recorded with real status and never gate.
- `backend/app/modules/m21_claire/claim_proofs.py`: `ProofGatedActionPolicy(ActionPolicy)` for `ExecutionOrchestrator(policy=...)` (the orchestrator re-calls it at execute time): a consequential action (approval verb or HIGH risk) needs a `claims` list with at least one `action_driving` claim and every such claim VERIFIED. `enforce_claim_labels` downgrades `verified_from_cited_source` / `supported` labels that have no VERIFIED proof, keeping the original label on the record; `prove`, `require_verified`.

## Claims
| Claim | Status |
|---|---|
| 45 sandbox/checker tests, 15 gate tests, 15 Claire tests pass (75 total, ~17 s) | VERIFIED (ran) |
| Network, host files, env, writes, CPU, memory, file size, open files, fork bomb, orphan processes, timeout, output flood are contained for analysis/code_change evidence (one test each) | VERIFIED for those behaviours on this host |
| Without bwrap, or with bwrap that cannot start (stub), exec kinds fail closed and the evidence never runs | VERIFIED (simulated by monkeypatch and a failing stub; not tested on a real host without user namespaces) |
| Confidence 0.999 on bad evidence stays UNVERIFIED and is refused by the gate and the policy | VERIFIED |
| Forged pytest summary plus early exit, skip, xfail, zero tests, replayed conclusion from another plan, evidence swapped after review: rejected | VERIFIED |
| Gate is enforced for every caller | OVERSTATED if claimed: improvement_gate.py is unchanged; plain `ImprovementGate` and plain `ExecutionOrchestrator()` still authorize/run without proofs (pinned by tests). Gated only where the new classes are used. |
| Hostile test author cannot forge results | UNSUPPORTED. Known limit pinned by `test_documented_limit_in_process_forgery_of_the_junit_file_is_not_defended`: code inside the checked pytest process can write /out/junit.xml and the stdout summary itself. Also not covered: disk volume written to the work dir, kernel escapes. |
| Coverage is four evidence kinds; no proof assistant, no source fetching | SCOPED |

## Mutation run (generator: experiments/e5_gate_quality/mutants.py, unmodified; runner run_mutation.py)
Pass 1 (before the survivors fix): proof_gate 13 mutants: 10 killed, 3 survived. claim_proofs 31: 25 killed, 6 survived. proof_carrying 153: 95 killed, 58 survived.
- The 9 survivors in proof_gate and claim_proofs are docstring/comment text edits ("and" to "or" inside prose): equivalent, declared.
- Most proof_carrying survivors were a test-harness flaw: the skip condition used the module's own probe, so a mutant that broke the sandbox made the sandbox tests skip. Fixed (the skip now uses an independent bwrap check). Added tests for argv structure, rlimits, defaults, probe logic, text-size boundaries, reason strings and two-run determinism.
- Pass 2 (the 58 survivors re-run against the new tests, mutation_pass2_proof_carrying_survivors.json): 56 killed, 2 survived. Survivors: index 0 (docstring text edit, equivalent) and index 21 (`n = 0` to `n = 1` in the process counter, which only shifts a cap that has 48 slots of slack; equivalent for behaviour, declared).
- Final count for proof_carrying (153 mutants): 95 + 56 = 151 killed, 2 survived (both declared equivalent). Combined with the other two files: 185 mutants, 176 killed, 9 docstring survivors + 2 = 11 survived, all declared equivalent (text-only or slack-only). Caveat: the 95 pass-1 kills ran against the earlier test set; the tests only grew, and pass 2 re-ran only pass-1 survivors, so the full 153 were not re-run in one pass against the final tests. The proof_gate/claim_proofs numbers are from pass 1 on unchanged tests.

## Run
`pip install pytest cryptography fastapi pydantic httpx sqlalchemy jsonschema regex numpy scipy prometheus-client pyyaml` then
`python -m pytest -q tests/self_improve/test_proof_carrying_sandbox.py tests/self_improve/test_proof_gate.py tests/modules/test_m21_claire_claim_proofs.py`
Needs `bwrap` for the sandbox tests; they skip (with reason) where it cannot start, and the fail-closed tests run everywhere.
