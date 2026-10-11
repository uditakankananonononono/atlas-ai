# Row 708 - Code Formatting (CODEFO708)

Ledger source pin: `audits/coverage-register.json`, row 708, category "Technical & Engineering".
Verbatim requirement: "Code Formatting".
Verbatim description: "Ensures style".
Ledger status (`audits/additional-2000-features.json`): PARTIAL.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/software_practice_685_709.py:89`
(`_format`): lists the paths of supplied files whose raw `before` and `after`
differ, and pins `idempotence_required` and `semantics_must_not_change` to True.
It has no input validation or bounds, no declared style, and reports no hashes or counts.

This unit's delta, and only this (new files only; the shared cluster file is not edited):
1. A declared style is an input and is validated: name, indent (`spaces` or `tabs`),
   indent width 1..16, max line length 20..400, line ending (`lf` or `crlf`), final newline.
2. Every container is count-checked before any iteration (request 16 keys, style 16 keys, file entry 8 keys, 64 files)
   and every text has its raw length cap checked before strip or any Unicode check (style name 64, path 256,
   100000 characters per text, 1000000 in total). Relative paths may not contain `..`, `\`, `:`.
   Text that is echoed (style name, path) or hashed (before, after, second_pass) is refused if it holds any
   Cc, Cf, Zl or Zp character; Zs (for example U+00A0, U+3000) is accepted. In file contents only LF, CR and TAB
   are allowed among the control characters, because code needs them.
3. Per file: exact `changed`, SHA-256 and character counts for before and after, and
   `whitespace_only_change` (equal after removing all whitespace).
4. Declared-style observations on the `after` text only, with exact counts and at most 20
   listed line numbers per kind: long lines, trailing whitespace, indent character mismatch,
   indent width, line endings, final newline.
5. An optional caller-supplied `second_pass` is compared to `after` and reported as
   `second_pass_equal`, `second_pass_differs` or `second_pass_not_supplied`.
6. Non-claims are pinned False: `formatter_executed`, `semantics_verified`,
   `style_authority`, `idempotence_proven`.

## Interface
`run(request) -> dict`, in `code_formatting708.py`. Keys: `style` (object, all six fields
required) and `files` (list of `{path, before, after[, second_pass]}`).
The unit is bounded declared-diff bookkeeping over caller-supplied text. It never runs a
formatter, any caller code, a repository test suite or any external tool.

## Refusal codes (ValueError, prefix `CODEFO708:`)
`BAD_TYPE:<field>` (strict builtin `type(x) is ...`; subclasses refused; bool refused where a number is expected, `style.final_newline` must be exactly bool), `UNKNOWN_KEY:request|style|file` (fixed reasons, the caller key is never echoed; non-str keys land here too), `MISSING:<field>`, `BAD_STYLE:indent`,
`BAD_STYLE:line_ending`, `BAD_RANGE:style.<field>`, `BAD_PATH`, `DUPLICATE:path`,
`OVERSIZE:style.indent|style.line_ending` (raw cap 8 before enum membership), `OVERSIZE:keys|style.keys|file.keys|files|path|content|total|style.name`, `CONTROL_CHARS:style.name|before|after|second_pass`,
`ENCODING:<field>`,
`EXEC_REQUEST:<name>` (run, command, execute, formatter_command, apply, write, commit, push),
`CLAIM_REQUEST:<name>` (certify, approve, style_authority, release).

## Limits
- Surrogates (category Cs) get no new refusal. The only handling is the pre-existing encode guard: a lone
  surrogate in file contents cannot be hashed and is refused with `ENCODING:<field>`. A lone surrogate in the
  style name or in a path is not refused (residual, disclosed). A leading BOM (U+FEFF, category Cf) is refused
  as part of the Cf rule.
- Co (private use) and Cn (unassigned) characters are likewise accepted, not refused: they sit
  outside the refused categories (Cc, Cf, Zl, Zp) and follow the same residual path as Cs.
- No formatter or other tool is run and no code is rewritten; contents are only what the
  caller supplied.
- Whitespace-only means equal after removing all whitespace. Whitespace can be meaningful in
  some languages, so no semantic equivalence is claimed.
- A second pass equal to the after text is caller-supplied evidence; idempotence is not proven.
- Style observations apply the declared style to the after text only. They are not a style
  authority, lint or quality claim.
- Counts and listings are over supplied text; nothing is verified against any repository.
  Human review governs any use. No closure of row 708 is claimed.
- Not run by the builder: the full repository suite. Test evidence is the hermetic stdlib
  file `tests/modules/test_m20_code_formatting708.py` only.

## Evidence chronology (permanent)
- The first 32 tests were written before the module existed and were RED (collection failed with the module file absent).
- The 7 post-green pins (class `Pins`) were added after the first green run and had no RED run before the module; their evidence is mutant kills only.
- The initial 22 surviving mutants of the first mutation run were console-only: no raw TSV of that run was kept.
- The 9 text-policy tests (class `TextPolicy`, plus the changed path-boundary pin) were written RED first against the first version of the module (7 failures recorded), then the module was patched.
- Mutants are the builder's own generator output, not an independent battery; no completeness claim.
- v3: 7 tests in class `StrictTypesAndFixedReasons` plus 5 changed expectations were written RED against the v2 module (12 failures recorded), then the module was patched. Strict type checks now run before the count check; counts still precede any iteration or key inspection on plain containers.
