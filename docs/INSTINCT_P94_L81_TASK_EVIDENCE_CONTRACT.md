# P94|L81 Task-execution evidence checker - contract

Source line (verbatim): "Execute all tasks: conduct research, build tools, verify claims, check accuracy, generate results, improve until benchmark-beating and novel"

Source pin: instinct doc P94|L81, line map v4, class NON-SCIENCE, mission "task-list". Context line P93|L80: "Task list" (SECTION HEADER).

The source pins no fields, statuses or codes. Everything below beyond "per task, record evidence for these activities" is an interpretation choice, marked (IC).

Module: `backend/app/modules/instinct_doc/task_evidence_p94.py`. Offline and deterministic: no network, I/O, clock or randomness. It composes two landed modules and does not copy their logic:
- P246 coverage ledger (`line_coverage_p246`): the status words `COVERED_BY_DECLARATION` / `UNCOVERED`, `declared_at` validation, and a coverage check of the emitted line record.
- P65 claim-status check (`app.reports.claim_status`): grades the generated report.

## API (IC)
`check_task_evidence(request)` returns a dict. Request: `{"tasks": [...], "declared_at": "<ISO-8601 with timezone>"}`. Task: `{"task_id": str, "marks": [{"category": str, "evidence_ref": str (optional)}]}`.

## Categories (IC)
Six marks per task, in this fixed order: `research`, `tools`, `verify_claims`, `accuracy`, `results`, `improve_until_benchmark`. They map to the six verb phrases of the source line. "improve until benchmark-beating and novel" is ONE mark; there is no separate `novel` mark.

## Marking (IC)
- A mark with a non-blank evidence_ref is `DECLARED`. Anything else, missing or blank, is `UNVERIFIED` with evidence_ref `""`.
- `DECLARED` is deliberately not `VERIFIED`. The checker verifies nothing, so it never emits `VERIFIED` (P65 honesty semantics). evidence_ref values are copied verbatim from input and never invented.
- A task is `COVERED_BY_DECLARATION` only when all six marks are DECLARED, otherwise `UNCOVERED`, with the `missing` categories listed in category order.
- Tasks sort by task_id. Duplicate task_ids and duplicate categories within a task are refused.

## Output
`tasks`, `counts` (tasks, covered, uncovered, declared_marks, unverified_marks), `coverage_record`, `line_coverage`, `report`, `report_claim_status`, `claims`.
- `coverage_record` is a P246 evidence record for line `P94|L81` with source `self` and the supplied declared_at. Its status is COVERED only if every task is COVERED. It is validated by running P246's `compute_line_coverage` on a one-row map; `line_coverage` returns that ledger's covered/uncovered counts. An invalid declared_at is refused as `P94:bad_declared_at`.
- `report` is markdown with one header line and one line per task and category: `CLAIM: task <task_id> <category> [DECLARED|UNVERIFIED]`. It is graded by P65's `check_text` with the label set {DECLARED, UNVERIFIED} (IC); the result is in `report_claim_status`. evidence_ref values are NOT written into the report.
- `claims` states what is not claimed: `verified`, `task_fulfilled`, `evidence_adequacy_assessed` and `benchmark_beaten_or_novel_assessed` are all `False`.

## Refusals (ValueError, exact text, `P94:` prefix)
`bad_type:<request|tasks|task|task_id|marks|mark|category|evidence_ref|declared_at>`, `unknown_fields:<request|task|mark>`, `empty_tasks`, `limit_exceeded:tasks` (>1024), `empty_field:<task_id|declared_at>`, `text_too_long:<task_id|evidence_ref>` (>64 / >128), `bad_chars:<task_id|category|evidence_ref|declared_at>`, `bad_category:<value>`, `duplicate_task:<task_id>`, `duplicate_category:<task_id>:<category>`, `bad_declared_at`.

First error follows input order (IC). Bool is never accepted as a string.

## Control-character and injection defense
Every interpolated field (task_id, category, evidence_ref, declared_at) is rejected, not escaped, on any Unicode Cc, Zl or Zp character. task_id is also rejected on `[`, `]` and `|`, because they would break the P65 claim grammar. The check runs before any error text carries a value, so every refusal message is one line. Report line count is exactly 1 + 6 x tasks.

## Limits
Output artifact only. It records declared marks. It does not run tasks, read evidence, judge adequacy or accuracy, or assess any benchmark or novelty claim. No persistence. Passing tests is not audit acceptance.
