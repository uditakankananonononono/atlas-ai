# ATLAS-SCRIPTS-AUDIT-NODE-SCOPE-01

PREPARATION ONLY. NOT RUN, NOT WIRED, not a completed repair.
Base efa5649f7cbee5800e1cb38d0d38fbd3e5c55eca. Fix package identity: AST-SCOPE-01-FIX-01.

Existing scripts/validate_audit_evidence.py lines 8-12 flatten all test function
names with ast.walk. Lines 23-27 compare that set with an entire scoped node.
This can confuse method/nested function scope and reject explicit class paths.
The existing script remains untouched. No runtime or ledger-incidence claim.

## Standalone interface

source_index.py exports structural_paths(source) and validate_reference(reference,
root=Path). The first parses text to a frozenset of source declaration path tuples;
the second reads a root-contained relative .py file as UTF-8 with optional BOM and returns frozen
SourceResult. Only structural_source_match is the positive evidence field.
parameter_case_verified is always false. Never label a result collection or pass.

Only direct declarations in a module or class body are indexed. Function bodies
are never traversed. Async functions follow the same rule. Explicit class names
are kept in the path, even if a class is not collectible by pytest. Conditional,
inherited, aliased and dynamic declarations are not indexed. Repeated direct declaration, assignment and import
bindings are excluded conservatively. Decorators/metaclasses, later deletes,
conditional rebinding and custom collection are not evaluated: a match describes
syntax, not runtime survival or callable identity.

Grammar: relative .py filename followed by ::-separated ASCII identifiers ending
in test_*. One final nonempty [parameter-id] suffix is syntactically accepted.
Nested brackets, newlines and :: within parameter IDs are intentionally unsupported.
This never checks a parameter case exists. Absolute/traversal references fail;
symlinks escaping root fail. Static root containment is not a race-proof sandbox.

Reasons: malformed_reference, source_path_outside_root, source_missing,
source_not_regular_file, source_unreadable, source_decode_error,
source_syntax_invalid, node_path_not_found, structural_source_match.
Malformed/missing/unreadable/syntax-invalid remain distinct. No target module is
imported and no test body is executed. No CLI, ledger adapter or product wiring.

## Peer commands planned, NOT RUN here

- python -m py_compile scripts/audit_node_scope_01/source_index.py scripts/audit_node_scope_01/test_source_index.py
- pytest -q scripts/audit_node_scope_01/test_source_index.py

Target fixture is text and contains top-level and body execution traps; tests
copy it to a temporary source path. Direct import loads only the helper. Acceptance
covers module/class scope, nested/nonexistent rejection, async, malformed input,
missing/directory/unreadable/decoding/syntax reasons, suffix caveats, symlink escape,
rebindings and conditional exclusion. Peer owns execution and independent verdict.

## Fix-01 audit limits

Embedded NUL filenames return malformed_reference on filesystem ValueError.
UTF-8 BOM is supported by utf-8-sig decoding. Structural matches still do not
prove runtime binding: for-targets, with-as, except-as, walrus and del are NOT
included in the conservative binding counter. Their presence does not remove
otherwise indexed declarations. An authored test records this limitation; this
fix does not expand the approved direct-declaration indexing scope. Direct
assignment/import/declaration rebinding exclusion is not a general Python binding
analysis. No peer results from the earlier parent are inherited by this head.
