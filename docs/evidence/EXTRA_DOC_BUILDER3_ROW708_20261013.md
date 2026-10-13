# Extra-doc row708 test reproduction

Source: extra doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY, live read October 13 2026.
Requirement: Code Formatting. Existing row708 only compared declarations and
explicitly did not run a formatter.

New route: POST /code-formatting/708/format-python within the existing M20 router.
Real Black Python formatter, Black safe-mode normalized AST comparison, actual second
pass, hashes and unified diff. Signed-owner tenant/actor binding and no cross-owner
resource references. Source is never executed and no files are read or written.
Install the optional code-formatting dependency group, Black 26.10.1.

Test reproduction: Python 3.12.14; focused new and compatibility tests, 89 passed plus route reachability regression.
Deployed runtime: unverified.
Verdict: PARTIAL for literal broad code-formatting row, Python capability built.
No other languages, repository application, runtime semantics proof or release
clearance. Black safe-mode AST equality permits docstring normalization (__doc__ changes) and does not prove source-introspection or line-number parity.
