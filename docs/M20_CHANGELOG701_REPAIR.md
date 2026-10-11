# Row701 changelog validation repair

Audit found malformed input accepted or raising incidental AttributeError/TypeError:
non-dict entries, category non-string/unknown, blank/non-string descriptions and
empty changes. The old setdefault also invented buckets for unknown categories.
Now exact nonempty changes list, exact dict entries, string category stripped and
casefolded into the six existing buckets; nonblank string description required.
Description text is preserved unchanged. Missing category no longer silently
becomes changed; caller supplies a recognized category. Invalid inputs ValueError.

Five test groups24 cases, RED24 failed on current public4da7f8e5. Final24 unit,
real3.12.14 unchanged conftests neighbor floor130 passed, one dependency deprecation.
Own8/8 named mutations killed. Atomic scoped _changelog-only runtime/test/doc change;
no release publishing, version validation, universal input-policy or full-suite claim.
Independent gate: separate record. Supplied strings are not independently verified facts.
