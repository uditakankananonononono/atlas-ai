# P258|L205 Research paper files register - contract

Source line (verbatim): "Output: Research paper files"

Source pin: instinct doc P258|L205, line map v4. Related line (flag source), verbatim: P85|L73 "Deliverable 9: 50+ page research paper, Times New Roman, good formatting".

The source pins no fields, flags or codes. Everything below beyond "a registry of research paper files" is an interpretation choice, marked (IC).

Module: `backend/app/modules/instinct_doc/paper_register_p258.py`. Pure stdlib, offline, deterministic. It never opens, renders or inspects a file or PDF. Same family as the P252 progress log and P255 integrations register.

## API (IC, shape from P252/P255)
`create_register()`, `append(register, entry)` (returns a NEW register, never mutates input, a refusal changes nothing), `render(register, project_id=None)`.

## Entry (IC)
- id (<=64, unique across the register), project_id (<=64), path (<=256, unique within its project, exact match, recorded and never opened or resolved).
- page_count_claim: optional integer 0..100000. It is a CLAIM. Bool, float, string and an explicit None are `bad_type`.
- page_evidence_ref: optional, <=128, recorded and never resolved. Blank is stored as "". It is allowed only when a page_count_claim is present.
- font_rule_flag: optional, one of `pass`, `fail`, `unchecked` (default `unchecked`). It is the Times New Roman rule (P85|L73) result SUPPLIED by the caller. This module never computes or infers it, so a path or file name never changes the flag. The 50+ page part of the rule is not checked or flagged either.

## Render (IC)
Projects sort by project_id, papers by path. Header: `project <project_id> (<n> papers)`. Line: `<path> pages=<N|none> <UNVERIFIED|[page_evidence_ref]> font=<flag>`. The page count is shown as `UNVERIFIED` unless an evidence_ref was supplied. Lines join with `\n`, with no trailing newline. An empty register renders as `""`. An unknown project is refused.

## Control-character defense
Every text field (id, project_id, path, page_evidence_ref, font_rule_flag) is rejected, not escaped, when it contains a Unicode Cc, Zl or Zp character (newline, CR, tab, NUL, ESC, DEL, NEL, U+2028, U+2029): `P258:bad_chars:<name>`. This check runs before any check that interpolates a value into an error. One entry therefore always renders as exactly one row, and refusal messages are always single-line.

## Refusals (ValueError, `P258:` prefix)
`unknown_fields:entry`, `empty_field:<name>` (also a missing required field), `bad_type:<name>` (also `entry`, `register`, `project_id`), `bad_chars:<name>`, `text_too_long:<name>`, `out_of_range:page_count_claim`, `bad_flag:<value>`, `evidence_without_claim:<id>`, `duplicate_id:<id>`, `duplicate_path:<path>`, `limit_exceeded:papers_per_project` (>256), `limit_exceeded:projects` (>1024), `unknown_project:<project_id>`.

Check order: entry type, unknown fields, missing required, text types, claim type, control characters, blank, too long, page range, flag, evidence-without-claim, then register state (duplicate id, duplicate path, per-project limit, project limit).

## Limits
Output artifact only. It does not verify page counts, fonts or formatting, never reads a paper, and never states a paper is compliant on its own. The flag only echoes what the caller supplied. No persistence, no network, no clock. Passing tests is not audit acceptance.
