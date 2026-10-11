# NAMING707: bounded Python identifier naming check

Targets ledger row 707 "Naming Conventions" (extra Google Doc entry
"Naming Conventions - Creates consistency") for SCOPED acceptance only. It checks the
identifiers an author wrote in one Python source string against naming rules the caller
declares. It is not an organisational style inference, not a linter replacement, and
not a claim about languages other than Python. Row 709 Linting is untouched: this core
does not edit or reuse any linter file. The unit name NAMING707 is routing shorthand.

New file `naming_checker707.py`, stdlib only (`ast`, `re`, `hashlib`, `bisect`,
`unicodedata`, `warnings`), Python 3.10+. `check_naming(source, rules)` returns a
report; `NamingRefusal` (a `ValueError`, with `.code` and `.detail`) is raised on refusal.
The source is only parsed with `ast.parse`; it is never executed, imported or compiled.
No route is mounted by this unit: row wiring is a separate, unapplied patch.

## Rules (all explicit, nothing inferred)

`{"rules": [...], "acronyms": [...], "forbid_shadowing": false}`; unknown keys refuse.
Each rule: `id` (non-empty str, <=64 chars, unique, `SHADOW` reserved), `kinds`
(non-empty, unique, from function, method, class, parameter, local, module_variable,
class_attribute, import_alias), `style` (snake_case, UPPER_SNAKE, PascalCase,
camelCase), optional `scope` (module, class, function; comprehensions count as
function), `allow_leading_underscore` (bool, default false; allows 1 or 2),
`allow_trailing_underscore` (bool, default false; allows 1), `dunder` ("flag" default or
"exempt"), `acronyms`. Declared acronyms (>=2 uppercase letters, unique) are the only
runs of 2+ capitals PascalCase/camelCase accept; a run followed by a lowercase letter
gives its last capital to the next word (HTTPServer needs HTTP; ABc needs nothing).
Top-level acronyms apply to every rule. A name is judged by the first problem in this
order: dunder, no_letters, leading_underscore, trailing_underscore, style_mismatch,
undeclared_acronym. `_` alone is an exempt placeholder (counted, not reported). A dunder is
a name of 5+ characters that starts and ends with `__`.

Symbols: function and method defs (method = def directly in a class body), classes,
parameters (incl. `*args`, `**kwargs`, keyword-only, lambda), locals (assignment, for,
with, except-as, walrus, comprehension targets), module variables, class attributes,
and the `as` name of import aliases. Only the first binding of a name in a scope is
checked; later rebindings are not. Names declared `global`/`nonlocal` are not locals.
`forbid_shadowing` adds rule id `SHADOW` findings when a function, lambda or
comprehension binding reuses a name bound in an enclosing function or module scope
(class scopes are skipped; builtins are not considered).

## Report

`schema`, `source_sha256`, `position_unit`, `rules_applied`, `style_inferred` (always
false), `checked_count`, `exempt_count`, `position_unverified_count`, `checked`
(name, kind, position, rule_ids), `findings`, `compliant`, `not_inspected`, `limits`.
Findings carry `rule_id`, `kind`, `name`, `line`, `col`, `end_line`, `end_col`, `reason`,
`expected` (the style), `detail`, sorted by line, column, rule id. Positions are
1-based lines, 1-based columns in Unicode code points, end column exclusive; lines
split on `\n`, `\r\n`, `\r` as Python does. Names are reported as written in the source
(before Python's NFKC normalisation). Output does not depend on the order of rules,
kinds or acronyms in the request.

## Limits and refusals

Source <=262144 UTF-8 bytes; <=20000 syntax nodes; <=32 rules; <=64 acronyms per list;
rule id <=64 chars. Exactly at a limit is accepted, one over refuses. Codes:
`invalid_rules` (exact message names the offending id, kind, style, scope or key),
`invalid_source` (not str, null byte, lone surrogates), `syntax_error` (line in
`detail`), `resource_limit` (size, node count, parser or analysis nesting).

## Not inspected

Attribute and subscript targets, `del` targets, match-pattern captures, names inside
strings and comments, imports without `as`, non-Python source, type or semantic
correctness, whether a style is the right one for any organisation. A clean report means
only that the inspected symbols matched the declared rules. If an identifier's source
position cannot be re-found by pattern, it is reported at the node start and counted in
`position_unverified_count`.

## Tests

`tests/modules/test_m20_naming707_ast.py` (stdlib unittest, runs under pytest too, loads
the core by file path): every symbol kind with exact positions, Unicode columns, CRLF/CR/
form-feed lines, NFKC names, underscore and dunder policy, acronyms, shadowing, refusals,
exact N/N+1 bounds, exact rule errors, order determinism, and an exhaustive oracle over
every name of length 1-5 from the alphabet `aA_1` for all four styles and all option
combinations. Mounted auth/tenant tests belong to the integrator after wiring.
