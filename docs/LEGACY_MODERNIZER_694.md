# Ledger row 694: Legacy Code Modernization (contract)

Module: `backend/app/modules/m20_general_cognitive_worker/legacy_modernizer694.py`
Tests: `tests/modules/test_m20_legacy_modernizer694.py`

## Scope and its source

The ledger text for row 694 is one line: "Updates old systems". This scope was proposed by the builder from that line. It was not taken from a longer specification, and it has not been ruled on. The feature document that was consulted ("Category 1: Executive Function & Meta-Cognition (100 features)") numbers the same title 685, not 694. The repo ledger (coverage register, additional-2000-features, implementation audit) numbers it 694. The 9-row offset is unresolved. The row number is verified from the repo register only.

At base the row status is PARTIAL, and the recorded scope says no code transformation is performed. This module adds one narrow, real code transformation. It does not change that status or any ledger file.

## What it does

`modernize(source, rules=None, check=None)` takes Python source text and returns a `ModernizationResult`. It finds spans with the standard `ast` module and rewrites only those spans. Everything else stays unchanged. Rewrites repeat until no more apply (at most 10 passes), so nested cases work.

| rule | rewrite | assumption carried in each Change |
|---|---|---|
| `has_key` | `d.has_key(k)` to `k in d` (parenthesized unless the context makes that unnecessary) | receiver is a mapping; type is not known |
| `unittest_aliases` | `self.assertEquals` etc. to the current name (11 aliases, see `UNITTEST_ALIASES`) | `self` is a `unittest.TestCase` |
| `collections_abc` | `from collections import Mapping` to `from collections.abc import Mapping` when every imported name is an ABC | none |
| `string_module` | `string.lower/upper/strip(x)` to `x.lower()` etc.; `string.join(w[, sep])` to `sep.join(w)` | plain `import string`, never rebound |
| `getcwdu` | `os.getcwdu()` to `os.getcwd()` | plain `import os`, never rebound |
| `xrange` | `xrange(...)` to `range(...)` | name not defined or rebound in the module |
| `dict_iter` | `iteritems/iterkeys/itervalues()` to `items/keys/values()` only as the iterable of a `for` or comprehension, or the first argument of sorted, list, tuple, set, frozenset, sum, min, max, any, all, enumerate | receiver is a dict |

## What it refuses (reported in `refusals`, source left as is)

- Python 2 only syntax (`print x`, `except X, e`): `syntax_error`.
- `has_key` with zero, two or more arguments, keyword or starred arguments.
- `string.*` calls with extra arguments.
- `from collections import` that mixes ABC and non-ABC names. The statement is not split.
- `collections.Mapping` attribute form: it would need `import collections.abc`, which is not added.
- `iteritems()` and friends used in any other way (stored, passed on, `next()`ed), or called with arguments.
- Pending rewrites after 10 passes: `max_passes`.

## Verification

`compiled_ok` is the result of `compile()` on the output. `verified` is true only if the output compiles and a caller-supplied `check(new_source)` returns true. No check means `verified` is false. A check that raises counts as failed and its error is in `check_error`. `characterization([(function_name, args, expected), ...])` builds a check that executes the new source in a fresh namespace and calls those functions. That executes the input source, and nothing is sandboxed. The caller owns that risk.

## Position reporting

`Change.line` is the line in the text of the pass that made the change. When no rewrites nest, that is the line in the original. Passes after the first can shift lines if an earlier rewrite collapsed a multi-line call. `Change.col` is the ast UTF-8 byte offset. `Refusal` positions refer to the final text.

## Not covered

- Python 2 syntax conversion, type inference, `unicode`/`long`/`basestring`/`print` handling, `%` formatting, integer division, `dict.keys()` list semantics, `map`/`filter`/`zip` laziness, relative imports, and removed modules other than the ones above.
- No file or repository walking. It works on a string.
- No authentication, tenant or HTTP layer. A wiring patch exists separately and is unapplied and untested.
- The existing `legacy_code_modernization` method in `software_practice_685_709.py` is unchanged.
