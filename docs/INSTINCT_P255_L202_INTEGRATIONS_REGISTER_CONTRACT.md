# P255|L202 External tool integrations register - contract

Source pin (verbatim, the only source text): P255|L202 "Output: External tool integrations," Context P254|L201: "Output: Dataset counts and sources,". The source pins no fields, statuses or codes. Everything below beyond "a catalog of external tool integrations" is an interpretation choice, marked (IC), set by Main's "go defaults".

Module: `backend/app/modules/instinct_doc/integrations_register_p255.py`. Pure stdlib. No network, I/O, clock or randomness. It performs no live integration call. A register entry is a declaration, not evidence of a working connection.

## API (IC: shape reused from P252 progress log)
- `create_register()`, `append(register, entry)` (returns a NEW register, never mutates input, a refusal changes nothing), `render(register, project_id=None)`.

## Entry (IC)
Fields: id (<=64, unique across the register), project_id (<=64), name (<=64, unique within its project), purpose (<=256), status (declared|planned|active|deprecated), evidence_ref (optional, <=128). Text must be nonblank except evidence_ref. Bool, number and None are `bad_type`. `evidence_ref` is recorded, never resolved or authenticated. A missing or blank evidence_ref is stored as "".

## Render (IC)
Projects sort by project_id, integrations by name. Header: `project <project_id> (<n> integrations)`. Line: `<name> <status> <purpose> <evidence>`. Evidence is `[<evidence_ref>]` when present and the literal `UNVERIFIED` when empty. Lines join with `\n`, with no trailing newline. An empty register renders as `""`. An unknown project_id is refused. Nothing in the module's output claims "connected" or "verified". `active` only records a declared status.

## Refusals (ValueError, `P255:` prefix, IC)
`unknown_fields:entry`, `empty_field:<name>` (also for a missing required field), `bad_status:<value>`, `duplicate_id:<id>`, `duplicate_name:<name>`, `text_too_long:<name>`, `limit_exceeded:integrations_per_project` (>256), `limit_exceeded:projects` (>1024), `bad_chars:<name>`, `unknown_project:<project_id>`, `bad_type:<name>` (also `entry`, `register`, `project_id`).

Check order: entry type, unknown fields, missing required fields, field types in field order, control characters (`bad_chars`), blank, too long, status, then register state: duplicate id, duplicate name, per-project limit, project limit.

## Control characters (R2 repair, IC)
Every text field (id, project_id, name, purpose, evidence_ref) is REJECTED, not escaped, if it contains any Unicode control or line character: category Cc (includes newline, carriage return, tab, NUL, ESC, DEL, NEL), Zl (U+2028) or Zp (U+2029). Refusal: `P255:bad_chars:<name>`. This keeps one entry to exactly one rendered row, so caller data cannot forge extra project headers or integration rows.

## Limits
Output artifact only. It does not discover, call, test or authenticate any integration, and does not verify that the stated purpose or status is true. No persistence. Passing tests is not audit acceptance.
