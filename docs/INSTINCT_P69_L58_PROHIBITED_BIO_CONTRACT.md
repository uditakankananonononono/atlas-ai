# INSTINCT P69|L58 prohibited-bio-content rule pack

Source pin: instinct doc P69|L58, contract text verbatim:

> Do not produce wet-lab protocols, pathogen enhancement, harmful biological
> instructions, or anything that could cause harm.

Companion to P68|L57.

## Scope a reviewer cannot miss

This module is a lexical exact-phrase screen only: a `clear` verdict means
exactly one thing - no listed pattern matched - and nothing more. It is not a
safety judgment, not a harm classifier, and not evidence that content is safe.
"Anything that could cause harm" is deliberately NOT implemented as a
catch-all: an unbounded harm classifier cannot be specified or tested honestly,
so the module blocks only the three enumerable categories below.

## Surface

Pure stdlib, no I/O, no network, no ML, no mutation of caller input.

`screen(document) -> verdict dict`. A document has exactly the fields `id`,
`kind`, `text` - no others:

- `id`: string, nonblank, at most 64 characters.
- `kind`: exactly one of `protocol`, `instruction`, `claim`, `other`.
- `text`: string, nonblank, at most 4096 characters.

The verdict dict carries `id`, `verdict`, `category`, `matched_pattern`,
`offset`. `verdict` is exactly `clear` or `blocked:<category>`, recording the
matched pattern string and its character offset in the caller's original text.
Blocked content is a verdict, never a refusal.

`screen_batch(documents) -> list of verdicts`, screened in sorted-id order
(stable; malformed documents without a string id sort first). The batch is
refused on the first malformed document encountered in that order.

## Matching

Case-insensitive exact-phrase (substring) matching against the closed pattern
list below; no fuzzy matching, no scoring, no stemming. The first match in
documented pattern order wins - category order first, then pattern order
within the category - regardless of where patterns appear in the text.

The closed pattern list (data inside the module, mirrored by the test;
extending it is a contract change):

1. `wet_lab_protocol`: `incubate at`, `centrifuge`, `pipette`,
   `culture medium`, `inoculate`
2. `pathogen_enhancement`: `gain of function`, `enhance transmissibility`,
   `increase virulence`
3. `harm_instruction`: `how to synthesize`, `how to culture`, `weaponiz`

## Refusals

All refusals are `ValueError` with the exact code as the message:

- `P69:unknown_fields:document` - document fields are not exactly
  {id, kind, text} (missing or extra).
- `P69:empty_field:<name>` - `id` or `text` empty or whitespace-only.
- `P69:bad_kind:<value>` - kind is not one of the four declared values.
- `P69:bad_type:<name>` - document is not a dict (`document`), a batch is not
  a list (`documents`), or `id`/`kind`/`text` is not a string.
- `P69:text_too_long:text` - text longer than 4096 characters.
- `P69:id_too_long:id` - id longer than 64 characters (analogous code, named
  here since the model bounds id length).

## Limits

Lexical screen over a fixed list; paraphrases, translations, encoded text, and
unlisted harmful content pass as `clear` by design. No repository state, no
persistence, no external calls.
