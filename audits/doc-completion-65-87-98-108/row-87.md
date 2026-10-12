# Row 87 evidence sheet

Base: atlas-ai origin/main 27511b4a (checked 2026-10-13 IST). Source for fields below: the Oct 12 audit table (historical, pinned 4163f497) and the crosswalk disposition map 20261013. Neither is the owner doc text.

## (b) Literal request, as the audit table words it

Train models on information from 10 admissions-style websites

Doc source line refs in the table: 50,176. The doc text itself was not re-read for this sheet; the line above is the table's paraphrase.

## (a) Existing files and tests on main

- present: `backend/app/modules/m23_study_abroad/ADMITTED_CASES.md` (30 lines)
- present: `backend/app/modules/m21_claire/training.py` (28 lines)
- test files that import the named modules or name them as `<module>.py` (import/filename match only; results not run for this sheet): 2
  - `tests/modules/test_m21_personalization.py`
  - `tests/test_shared_model_layer.py`
- other files in backend/docs/audits mentioning "row 87": `audits/coverage-register.json`, `audits/evidence-resolution-report.json`, `audits/rebuild-20261009/m10-binding-dispatch/final-collection.log`, `audits/technical-spec-line-by-line.json`, `backend/app/modules/m20_general_cognitive_worker/moral_hazard87.py`, `backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py`, `docs/IMPLEMENTATION_AUDIT.md`, `docs/M20_MORAL_HAZARD87_CONTRACT.md`

## Crosswalk state

- state: LANDED-SCOPED; mutation deepening ASSIGNED
- evidence ids: B4 arc landed-scoped (rest staged/landed earlier per map)
- note: doc group PARTIAL (B4 assigned doc completion 00:57); literal row PARTIAL

## Tip-state update (second pass, origin/main d8668c19)

Source: `audits/instinct-groups-77-87/README.md` on main (base 4163f497, read 2026-10-12). Its own row for group 87, as a whitespace-normalized quote (spaces around the pipe separators removed, wording otherwise copied):

> | 87 |Add info to train models from 10 websites like AdmitSee | Actually fitted multinomial naive-Bayes advice-topic model, token/class counts, serialized artifact checksums, held-out per-class coverage, training-domain count, rights receipts and owner-consent route | PARTIAL: executed on synthetic author-owned fixtures, not licensed content from ten admissions-provider sites; not LoRA/LLM training or admissions success prediction |

The module paths in section (a) came from the Oct 12 table and may not be the mechanism that README describes. Compare the two before relying on (a). That README states it "does not change literal group verdicts to LANDED". Verdict stays PARTIAL. Tests were not run in this pass.

## (c) Verdict

**PARTIAL.**

Missing scope from the Oct 12 audit table (HISTORICAL, superseded by the tip-state update above where one is given): Public links explicitly not licensed training data; proposed datasets, not executed model training.

CLOSEABLE delta: none proposed. This process has not established literal acceptance for this row. This sheet makes no completion claim.
