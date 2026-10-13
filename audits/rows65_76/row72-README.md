# Row 72 evidence sheet

Code under test: `m02_competition_manager/integrated_application.py`.
Covered behavior: Owner-corpus draft, voice pass, review package, separate final-submit flag.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_rows65_76_sensitivity.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row72.json OUT` (5 exact-site mutations).
Final: 3 CAUGHT of 5. Not caught: facts_check_dropped, unhumanized_draft_used. facts_check_dropped and unhumanized_draft_used survive: the downstream ApplicationAnswerPipeline.prepare_review runs the same voice pass and refusal, so the flow-level check is redundant at API level (masked, not dead code).
First run (receipts in run1_receipts/row72.json, preserved): 3 SURVIVED. Added `tests/modules/test_rows65_76_sensitivity.py` (new tests only, no product code changed). The older `test_m02_integrated_application.py` is no longer in this selector: its two flow tests need the shared approval database table and fail on a fresh database, so the sensitivity file owns its approvals fake instead.

Receipt: `receipts/row72.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: m21 training.py is mapped but has no test on this base; actual-model quality and authentic owner-thinking validation. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.

Reconciliation with a replay on a newer base (integrator receipt for this row, selector `test_m02_integrated_application.py` plus `test_rows65_76_sensitivity.py`): that replay shows 4 CAUGHT, 1 SURVIVED.
- unhumanized_draft_used: SURVIVED in both runs (raw log of the replay: 21 passed under the mutant). No divergence.
- facts_check_dropped: SURVIVED here, CAUGHT there. Cause is a base difference, not selector order or an interruption. The replay base has `tests/modules/test_m02_integrated_application.py::test_first_voice_fact_loss_refused_and_source_ids_pinned`, which is absent from the 3-test version of that file on the tip181 base. That test killed the mutant. The tip181 selector for this sheet no longer includes the m02 file (fresh-database baseline failure), so it cannot see that test.
- Authoritative result per base: tip181 selector = 3 CAUGHT, 2 open (`receipts/row72.json`); replay base with the m02 file = 4 CAUGHT, 1 open (unhumanized_draft_used). On the newer base the m02 file's flow tests must also run against a database that has the approval table, or its baseline is not released.
- unhumanized_draft_used stays open on both: the downstream pipeline repeats the voice pass, so staging the raw draft instead of the humanized text is not visible at this API level.
