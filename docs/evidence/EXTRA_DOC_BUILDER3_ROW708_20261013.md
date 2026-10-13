# Extra-doc row708 builder reproduction

Source: extra doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY, live read October 13 2026.
Requirement: Code Formatting. Existing row708 only compared declarations and
explicitly did not run a formatter.

New route: POST /code-formatting/708/format-python within the existing M20 router.
Real Black Python formatter, AST comparison including type comments, actual second
pass, hashes and unified diff. Signed-owner tenant/actor binding and no cross-owner
resource references. Source is never executed and no files are read or written.
Install the optional code-formatting dependency group, Black 26.10.1.

Builder reproduction: Python 3.12.14; focused new and compatibility tests, 85 passed.
Independent audit: pending. Main landing: not performed. Deployed runtime: unverified.
Verdict: PARTIAL for literal broad code-formatting row, Python capability built.
No other languages, repository application, runtime semantics proof or release
clearance. AST equality does not prove source-introspection or line-number parity.
