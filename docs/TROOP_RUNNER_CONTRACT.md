# Troop runner contract (addendum to the commit that added `backend/app/troop`)

This file is documentation only. It adds no code and changes no test. Code and test bytes are
unchanged from the commit it sits on.

## 1. What this is

A FIXED-TEMPLATE LOCAL CALLABLE RUNNER ONLY. The planner maps a task kind to a fixed list of steps, the
worker calls registered Python functions, the reviewer applies declarative checks. It is NOT model
agents, NOT autonomy, NOT product parity with any named product, and NOT fulfilment of the doc line it
was built for. It is a bounded mechanism.

## 2. Mutation evidence

- Author campaign: 30 hand-written mutants, one at a time, raw log per mutant. Final run: 29 reported KILLED by the script, of which one (m20, cycle guard disabled) was ended by a timeout, plus 1 SURVIVED (m28). The script labels exit status only, so "29 killed" is not "29 assertion kills".
- Author campaign classification independently inspected: 28 ordinary rejections, 1 TIMEOUT, 1 SURVIVOR; m28 independently reconstructed and tested.
- Independent fresh set of 20 AST mutants: 14 killed by an assertion, 4 killed by an error, 2 killed by timeout, 0 survived. The two timeouts: runner mutant 7 (line 47, cycle guard disabled, the layer loop never ends on an empty layer) and runner mutant 16 (line 51, `remaining` flipped, processed forever).
- TIMEOUT IS ITS OWN FINDING CLASS. A mutant that makes the program loop forever is stopped by the harness clock, not by a test assertion. It shows the mutation is detectable as a hang, not that a test asserts the correct behavior. Timeouts are counted separately from assertion kills and error kills everywhere in this contract.
- Test count: author 36 tests on Python 3.10.12; independent runs reported 36 and 37 passing, the latter on Python 3.12.14, with no core defect found.
- A dependence on `max_attempts` for blocking was reproduced by the independent review.

## 3. m28 equivalence (scoped)

Mutant m28 changes `_run_step` so a failed step returns its last output instead of `None`. It survives. It is equivalent ONLY for inputs that reach the return through the public `run`: `run` discards the output of any step whose status is not `completed` (lines 94-95 of `runner.py` at this commit: `if st == "completed": outputs[s.id] = out`; the review cited lines 103-104, which do not exist in this 98-line file, so the line numbers here were re-read from the committed file). It is not equivalent in general. A caller that calls `_run_step` directly would see the difference. No test covers that private call.

## 4. Survey status

`docs/yc_survey.md` is ATTRIBUTED vendor self-description taken from public pages on 2026-10-11. It is not audited product fact. Prices, plan limits and page contents were not verified live beyond that single read and may have changed.

## 5. Trusted-caller limits (not handled)

- The constructor caller is trusted. `max_attempts`, `max_workers` and `max_steps` are not validated. A non-positive `max_attempts` makes a step fail with zero worker calls; a non-positive `max_workers` is rejected by the thread pool only at run time.
- Reviewer exceptions ESCAPE `run`. Only worker exceptions are captured and retried.
- No isolation between steps (shared process, shared memory), no per-step timeout, no cancellation, no persistence.
- The planner reads the task dict directly and does not validate fields beyond `id` and `kind`.
- Not wired into any route or registry.
