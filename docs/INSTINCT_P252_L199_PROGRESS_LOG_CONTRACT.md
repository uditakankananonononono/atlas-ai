# P252|L199 Progress log by task - contract

Source pin: instinct doc P252|L199, verbatim: "- Progress log by task." Context P251|L198: "Provide:" (output-format section header).

Module: `backend/app/modules/instinct_doc/progress_log_p252.py`. Pure stdlib. No clock, randomness, I/O or network. Same call sequence gives byte-identical output.

## API
- `create_log()` returns an empty log.
- `append(log, entry)` returns a NEW log. The input log and entry are never mutated. A refused append changes nothing.
- `task_status(log, task_id)` returns `open`, `completed`, `failed` or `unknown`. It is a query and never refuses.
- `render(log, task_id=None)` returns text. Tasks sort by task_id and entries by seq. Task header: `task <task_id> (<n> entries, <open|completed|failed>)`. Entry line: `<seq> <status> <message> [<source_ref>]`. Lines are joined by `\n` with no trailing newline. An empty log renders as `""`. An unknown task_id is refused.

## Entry
Exactly six fields: id (<=64, unique in the whole log), task_id (<=64), seq (int >=0, strictly increasing per task_id), status (started|progress|blocked|completed|failed|note), message (<=256), source_ref (<=128; recorded, never authenticated or resolved). Text fields must be nonblank (whitespace only counts as blank). `completed` and `failed` close the task.

## Refusals (ValueError, exact text)
`P252:unknown_fields:entry`, `P252:empty_field:<name>`, `P252:bad_status:<value>`, `P252:duplicate_id:<id>`, `P252:non_monotonic_seq:<task_id>`, `P252:task_closed:<task_id>`, `P252:limit_exceeded:tasks` (>1024 task_ids), `P252:limit_exceeded:entries_per_task` (>4096), `P252:text_too_long:<name>`, `P252:unknown_task:<task_id>`, `P252:bad_type:<name>`.

## Order of checks for one entry
non-dict (`bad_type:entry`), unknown fields, missing field (`empty_field:<name>`), per-field type (bool anywhere is `bad_type`), blank, too long, status, then log state: duplicate id, task closed, seq, entries_per_task, tasks. Fields are checked in id, task_id, seq, status, message, source_ref order.

## Interpretation choices (flagged for review)
- Negative seq is refused as `non_monotonic_seq:<task_id>`.
- A missing field is refused as `empty_field:<name>`.
- `append` takes one entry, so "competing bad entries follow sorted entry ids" has no observable surface. There is no batch API.
- `bad_type:log` is raised for a non-log first argument. It is outside the brief's list.

## Limits
Output artifact only. It records and renders supplied entries. It does not track real work, verify claims or fabricate progress, and never emits `completed` by itself. No persistence, no timestamps. Passing tests is not audit acceptance.
