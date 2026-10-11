# M20 Row 706 - Code Comments ("Explains code") contract

Module: `backend/app/modules/m20_general_cognitive_worker/comment_audit706.py`
Algorithm id: `python_comment_audit_v1`. Entry point: `audit(data) -> dict`; refusals raise `ValueError` with an exact message.

## What it does
Extracts every comment from supplied Python source with the standard `tokenize` module (never a regex over text, so `#` inside
strings is not a comment), groups them into blocks, classifies each, attaches mechanical flags, and reports comment coverage per
function/class. Source is parsed and tokenized only. It is never executed, imported or evaluated.

## Input
`{source: str, max_line_length: int 40..200 (default 100), min_lines_for_comment: int 1..500 (default 15)}`. Integers must not be bool.
Unknown or missing keys: `input keys invalid: missing [...] unknown [...]`.

## Refusals (check order)
input must be an object; keys; option ranges (`max_line_length must be an integer 40..200`, `min_lines_for_comment must be an integer 1..500`);
`source must be a string`; `source exceeds 65536 characters`; `source contains NUL`; `source is not UTF-8 encodable`;
`source must use LF or CRLF line breaks` (any bare CR); `source exceeds 2000 lines`; `syntax_error: line L col C: msg`;
`source exceeds 40000 tokens` (tokenize count incl. NEWLINE/NL/ENDMARKER; N accepted, N+1 refused); `more than 500 symbols`.

## Output
`algorithm, status, source_sha256, source_chars, source_bytes, line_count, code_line_count, comment_count, options, position_convention,
comments, blocks, symbols, counts{by_category, by_kind, by_flag}, limits, code_executed=false, semantics_judged=false`.

Comment: `id Cnnnn, line (1-based), col/end_col (0-based code points, end exclusive), kind inline|standalone, text (verbatim after '#'),
category prose|directive|marker|empty, flags (sorted), has_rationale_keyword, block_id, associated_line`.

Categories: directive = shebang on line 1, PEP 263 coding line on lines 1-2, or text starting `type:`, `noqa`, `pragma`, `pylint:`, `fmt:`, `isort:`,
`mypy:`, `pyright:`, `nosec`, `flake8`, `ruff:`; empty = nothing after `#`; marker = uppercase whole-word `TODO|FIXME|HACK|XXX|NOTE` at the start; else prose.

Flags: `commented_out_code_candidate` (prose that parses as Python and has a non-expression statement, or an expression containing a call, await or lambda;
a bare annotation like `why: speed` is a label, not code), `restates_code_candidate` (every comment word occurs among the associated code line's name/number words),
`marker_without_owner_or_ref` (no `(name)`, `ABC-12` or `#42` in the first 80 chars), `long_comment_line` (end_col > max_line_length),
`empty_comment` (empty comment not inside a multi-comment block).

Blocks `Bnnnn`: consecutive standalone comments on adjacent lines at the same column. `associated_line` is the next line only when it is directly adjacent code.
Symbols: each def / async def / class (flat walk, source order): `start_line` (first decorator), `end_line`, `line_span`, `has_docstring`, `leading_block_id`
(block ending on the line before), `inner_comment_count`, flag `long_symbol_without_comments` (span >= min_lines_for_comment, no inner comment, no leading block).

## Not claimed
Whether a comment explains, helps, is correct or current is not judged. The flags are lexical candidates. Not executed; no tests run; grammar is that of the host interpreter.
