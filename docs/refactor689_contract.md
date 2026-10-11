# Refactoring: restricted local rename (repo row 689)

## Source and numbering

The live feature Doc at
https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY
says "Refactoring - Improves without changing behavior" at ordered-list item 680.
Its item 689 is Trunk-Based Development. The repo coverage register and audit
label Refactoring as row 689. This package uses the repo row only; the differing
Doc ordinal remains unresolved, not a verified Doc row-689 match.

## Real operation

`rename_local(source, old, new)` parses submitted Python, rejects unsupported
syntax and conflicting names, renames all matching local Name nodes, emits
Python source, reparses it, inversely renames the result, and checks exact AST
alpha-equivalence. The output includes SHA-256 hashes and occurrence count.
The operation does not execute submitted code or write files. Renaming a
misleading variable is the caller's choice; no automatic readability score or
claim of quality improvement is made.

Only one plain function is supported. The old name must have a local assignment;
parameters and function names cannot be changed. The replacement must be unused
(including global references and parameters). Calls, reflection, nested scopes,
comprehensions, attributes, imports, global/nonlocal statements, decorators,
annotations, defaults and variadic arguments are rejected, not approximated.
Identifiers use the ASCII non-keyword subset starting with a letter.

Behavior boundary: the same ordinary return values and raised exceptions under
local-name alpha-renaming. Formatting and comments are changed by ast.unparse.
Traceback source text, line numbers, code objects and external debugger inspection
of local names can change. No promise of complete observational equivalence under
introspection or tracing is made. Python user objects are not exhaustively
characterized. An AST check is structural evidence, not an exhaustive behavioral
proof; repository_behavior_verified is always false.

## Evidence and limits

20 unittest tests ran using /tmp/refactor689-venv/bin/python, Python 3.10.12.
Tests execute before and after functions for negative, zero, positive and float
values, loops and augmented assignments, and ZeroDivisionError preservation.
A valid RED was recorded before the module existed. Seven independently applied
hand-written mutants were killed on the final run, with raw outputs saved;
restored tests passed. The initial collision-check mutant survived because the
inverse AST check also rejected collisions. The collision test was then strengthened
to require the specific input-validation error, and the full mutation run repeated.
Both runs and the exact scripts are preserved.
This does not mean broad refactoring, all of row 689, or the existing software
cluster is independently accepted. Review classification: SCOPED.

No existing source, register, tests or wiring was edited. No route is added and
no wiring patch is supplied. Router mounting, auth/tenant behavior, existing
repository test floor, Python 3.12, production inputs, full suite, and integration
with software_practice_685_709 were not run. A separate integrator must decide
whether and how to expose the function. No merge, release, deployment or push.
