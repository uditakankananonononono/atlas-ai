# P260|L207 Self-improvement plans register - contract

> Output: Self-improvement plans

Source pin: instinct doc P260|L207, line map v4. Class NON-SCIENCE, mission output-format. The source line is the entire pinned contract text (verbatim from the line map CSV attached by the integrator; I did not see the original instinct doc).

Module: `backend/app/modules/instinct_doc/improvement_register_p260.py`. Pure stdlib (`re`, `unicodedata`, `dataclasses`, `datetime.date` for calendar validation only). No clock, randomness, I/O or network.

## Scope
REGISTRY ONLY. It records and renders caller-supplied per-tool, dated improvement-plan artifacts with a status field. It implements no self-improvement, does not run or verify any plan, resolves no `source_ref`, and stays clear of the separate in-flight P61|L52 line (modules self-improve). Everything below beyond the source line is an **INTERPRETATION CHOICE**; the source pins no fields, statuses, transitions or codes.

## API (INTERPRETATION CHOICE)
All functions are pure; the register is immutable and every change returns a new one (a refused call changes nothing).
- `create_register()`; `add_plan(reg, plan)`; `update_status(reg, plan_id, status, as_of)`; `get_plan(reg, plan_id)`; `list_plans(reg, tool=None, status=None)`; `render(reg, tool=None)`.
- Plan, exactly seven string fields: `id` (<=64, unique across the whole register), `tool` (<=64), `date` (`YYYY-MM-DD`, ASCII digits, a real calendar date; supplied by the caller, never read from a clock), `title` (<=128), `summary` (<=256), `source_ref` (<=128, recorded not resolved), `status`.
- Statuses: `proposed`, `approved`, `in_progress`, `done`, `dropped`. Transitions: proposed -> approved|dropped, approved -> in_progress|dropped, in_progress -> done|dropped; `done` and `dropped` are terminal. `update_status` takes an `as_of` date that may not precede the previous history date (same day allowed). The plan's own `date` never changes; `history` lists `{status, date}` per step.
- Limits: 1024 plans, 128 tools. Returned records are copies and carry `registry_only: true`, `implements_self_improvement: false`.
- `list_plans` and `render` sort plans by (date, id) and tools by name, independent of insertion order.

## Render format (INTERPRETATION CHOICE)
Per tool: `tool <tool> (<n> plan[s])`, then one line per plan: `<date> <id> <status> <title> - <summary> [<source_ref>]`. Lines are joined by `\n`, no trailing newline. An empty register renders `""`.
Line-count invariant: the number of lines equals (number of tools rendered) + (number of plans rendered), under both `split("\n")` and `str.splitlines()`. This holds because no interpolated field can contain a line break.

## Control-character injection defense (INTERPRETATION CHOICE for scope and codes; the requirement itself came from the integrator)
Every interpolated string (id, tool, title, summary, source_ref, date, status, and the `plan_id`, `tool`, `status`, `as_of` arguments of lookups) is refused if any character has Unicode category Cc, Zl or Zp (all C0 and C1 controls including NUL, TAB, CR, LF, VT, FF, FS/GS/RS/US, DEL, NEL, ESC, plus U+2028 and U+2029): `P260:control_char:<field>`. The check runs before blank, length, date, status and lookup checks, and refusal text never contains the offending value, so neither renders nor error messages can be forged or split into extra lines. Other Unicode (for example format characters such as U+200F, or non-breaking space) is accepted; bidi and homoglyph spoofing are not defended against (limit).

## Refusals (ValueError, exact text; INTERPRETATION CHOICE)
`P260:bad_type:<field|plan|register>`, `P260:unknown_fields:plan`, `P260:empty_field:<field>` (missing key or blank), `P260:control_char:<field>`, `P260:text_too_long:<field>`, `P260:bad_date`, `P260:bad_status:<value>`, `P260:duplicate_id:<id>`, `P260:unknown_plan:<id>`, `P260:unknown_tool:<tool>`, `P260:bad_transition:<from>><to>`, `P260:date_regression:<id>`, `P260:limit_exceeded:plans|tools`. Interpolated values are only ones already validated as clean.
Order for one plan (INTERPRETATION CHOICE): object type, unknown keys, missing keys, string type of every field, then control characters of every field, then blank, then length, date, status, then register state (duplicate id, plan limit, tool limit). For `update_status`: register, plan_id, status, date, lookup, transition, date order.

## Limits (INTERPRETATION CHOICE: the 1024/128 caps)
Records only what it is given; no dates are checked against real time, no plan is verified, executed or scheduled, and no ledger or wiring is touched.
