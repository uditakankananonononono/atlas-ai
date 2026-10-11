# Instinct doc candy gate [P247|L195] contract

Source lines (peer-enumerated from the instinct doc, treated as data): [P247|L195] "6. Only after everything is done, including these final upgrades, send the candy line exactly:". Duplicate: [P263|L210] "Final candy line only after full completion." The emoji line itself ([P248|L196]) is decorative and is not stored or sent by this module.

Module: `backend/app/modules/instinct_doc/candy_gate_p247.py` (stdlib only, offline, pure). The directory has no `__init__.py` by design (PEP 420 namespace; the package marker belongs to another owner). Tests load the module by file path.
Tests: `tests/modules/test_candy_gate_p247.py`

## What exists

A bounded mechanism: `evaluate(spec, observations, now=None)` returns a release decision from gate conditions declared in `spec` and observations supplied by the caller. The module computes each gate's state itself. It returns a decision only (`action: "none"`); it sends nothing and contains no candy line.

This is not a claim that either doc line is fulfilled.

## Gates (max 50)

Declared in `spec = {"gates": [...]}`; each gate has `id`, `kind` and the fields of its kind. Observations are `{gate_id: {...}}`.

| kind | declared | observation | GREEN when |
|---|---|---|---|
| `all_present` | `required`: 1 to 200 unique non-empty strings | `present`: list of at most 1000 strings | every required item is in present |
| `count_equals` | `expected`: non-negative int | `count`: non-negative int (not bool) | count equals expected |
| `digest_equals` | `expected_sha256`: 64 lowercase hex | `sha256`: 64 lowercase hex | equal |
| `fresh_within` | `max_age_days`: 1..3650 | `checked_at`: ISO-8601 with offset | not in the future and age at most max_age_days (exactly the limit is fresh); needs a timezone-aware `now` |

States: GREEN, RED (observed value fails the declared condition), MISSING (no observation for a declared gate), INVALID (observation malformed or carrying any field outside its kind). `release` is true only when at least one gate is declared and every gate is GREEN. An empty gate list never releases.

## Declared inputs, not caller labels

Fields such as status, green, done, passed or approved are not accepted anywhere. In a gate declaration they raise a ValueError. In an observation they make that gate INVALID, so a label can never turn a gate GREEN. An observation for an undeclared gate is an error.

## Gaps and limits, word for word

- GREEN means only that the supplied observation satisfied the declared condition. It is not proof that any work is complete, correct or honest.
- A missing or dishonest declared gate cannot be detected: the module cannot know what should have been declared.
- No live policy or legal enforcement. The doc's own conditions (every task, audit round, benchmark, discovery) are not checkable offline; the module checks only what the caller declares.
- No wiring, no persistence, no network, no sending.

Output is sorted by gate id and independent of input order.
