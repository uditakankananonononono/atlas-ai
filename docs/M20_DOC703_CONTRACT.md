# M20-DOC703-AST-01: Documentation Generation from a Python AST

Candidate target: row703 "Documentation Generation" / "Creates docs" (audits/additional-2000-features.json;
title and description verified against the source Google Doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY
on 2026-10-11, base 7885256e). Existing owner: `software_practice_685_709.py::_docs`, which only reformats
caller-supplied symbol dicts and parses nothing. This unit is a bounded SCOPED capability, not full title closure.
Rows 702/704 and the 707 naming and 709 lint cores are untouched. Wiring, ledgers and STATUS belong to the integrator.

## What it does
`ast_documentation703.generate({source, filename?, expected_sha256?})` parses supplied Python source text with
`ast.parse` only. It never compiles, executes or imports the source and never resolves names. For every `def`,
`async def` and `class` statement, found at any nesting (inside classes, functions, if/try/for/while/with/match)
it reports facts as written:
- id (`qualname#occurrence`, occurrence counted in source order), kind (function, async_function, class), name,
  qualname (`f.<locals>.g` convention), parent_id, depth, scope (module, class, function), def_line.
- Functions: ordered parameters with kind (positional_only, positional_or_keyword, var_positional, keyword_only,
  var_keyword), annotation text, default text, has_default; return annotation text; `signature_text` rebuilt
  from those parts (`/` and `*` markers); type_params text.
- Classes: base and keyword texts, type_params; `constructor_signature: "not_derived"`.
- decorators: exact source text and range (no semantics interpreted; `decorator_semantics: "not_interpreted"`).
- docstring: only a leading string-literal expression statement; `raw` and `cleaned` (ast.get_docstring, no
  other processing) and range. f-strings, bytes, later strings and expressions are not docstrings.
- Module docstring.
- Range of each symbol (from the `@` of its first decorator, or the def/class keyword, to the end of its body)
  and `range_sha256` of that exact source text.
Order is source order (pre-order), strictly increasing by start position, with one disclosed exception:
within try statements that have handlers, symbols are emitted try body, else, finally, then handler
bodies, so handler-defined symbols do not follow strict source order there. This is a known defect,
pinned by a strict-xfail test and queued for a runtime fix as a separate unit.

## Missing and unknown, never invented
`missing` marks: docstring (absent or empty after cleaning), return_annotation, unannotated_parameters.
Parameter `description` and `return_description` are always null with `semantics: "unknown"`;
`unknown_semantics` lists what the source cannot tell (parameter descriptions, return meaning, raises, side
effects, behavior, thread safety). Docstring text is preserved verbatim and never parsed into sections.
`semantics_derived`, `code_executed`, `imports_resolved` are always false.

## Position convention
Lines 1-based. Columns 0-based Unicode code points (not UTF-8 bytes, which is what `ast` reports), end
exclusive. Line breaks are LF, CRLF or CR; form feed is not a line break. Tabs count as one column.
Combining marks count as separate code points. `source_bytes` is the UTF-8 length; `source_sha256` is the
SHA-256 of the UTF-8 bytes. If `expected_sha256` (64 lowercase hex) is supplied and differs, generation is refused.

## Refusals (ValueError, 422 once mounted) and bounds (N accepted, N+1 refused)
source must be a string; unknown/missing keys; filename 1..128 of `[A-Za-z0-9_./-]`; source <= 65536
characters; no NUL; UTF-8 encodable (no lone surrogates); <= 2000 lines (LF/CRLF/CR); parse must succeed
(`syntax_error: line L col C: msg`, parser-reported position; leading BOM is a syntax error); parser recursion or
memory exhaustion is `resource_limit`; <= 20000 AST nodes; <= 500 symbols; scope nesting <= 8; hash mismatch.

## Residual limits
Result depends on the grammar of the interpreter running Atlas (e.g. `type` params need 3.12+).
Decorator effects, dynamic attributes, inheritance, star-imports, `__all__`, conditional definition truth,
overloads, string annotations and docstring conventions are not interpreted. Lambdas are not symbols.
Source authenticity is the caller's: the hash binds output to supplied text, not to a repository revision.
Output is a documentation fact sheet, not rendered prose docs. Does not close other rows.

## Wiring (separate, unapplied patch)
`POST /api/v1/api/modules/20/ast-documentation703/generate` via `ast_documentation_routes703.py`, included from `routes.py`,
with a mounted OIDC auth test (401 unauthenticated, 200 equals `generate()`, 422 malformed).
