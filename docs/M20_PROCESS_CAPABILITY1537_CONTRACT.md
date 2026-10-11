# PROCAP1537: exact capability indices (ledger row 1537)

Provenance line: cross-account builder package, provenance held privately.
Status: local review branch, not accepted, not landed. Full test suite not run (only this unit's test file).

## Ledger source pin
audits/additional-2000-features.json, id 1537: requirement "Process Capability", status verified-pushed (historical builder attribution, not current proof), description "" (empty).
The description is empty, so the requirement title is the whole spec. This contract proposes the exact behavior below.

## Delta against the existing mechanism
backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:167 (`_capability`): float `pstdev` used as the "within" sigma, both limits required, only Cp and Cpk, zero variation refused by a ValueError. This unit (new files, shared cluster file untouched): exact decimal arithmetic (64 significant digits, outputs rounded half-even to 9 places); two separate sigmas, within = MRbar/1.128 and overall = sample standard deviation (n-1); Cp/Cpk (within) and Pp/Ppk (overall), each with the one-sided Cpu/Cpl parts; one-sided specifications; `lower_spec < upper_spec` enforced. Refusals carry the exact prefix `PROCAP1537: `.

## Mechanism
`capability_indices(payload)` in `backend/app/modules/m20_general_cognitive_worker/process_capability1537.py`. Input: `study_id` text, `values` 2..500 decimal strings (finite, |v| <= 10^12, in time order for the moving range), `lower_spec` and/or `upper_spec` (at least one; decimal strings, same bound). Output: n, mean, sigma_within, sigma_overall, then cp (needs both limits), cpu = (USL-mean)/(3 sigma), cpl = (mean-LSL)/(3 sigma), cpk = min of the available one-sided values, and the same four with the overall sigma as pp/ppu/ppl/ppk. A missing limit gives null for the indices that need it. A series with no variation refuses. A mean on a limit gives index 0; past it, a negative index. Labels: normality_assumed true, stability_established false, process_acceptance_claimed false.

## Input grammar and arithmetic context
Input is exact: parsed numbers are never rounded. Every number (values, lower_spec, upper_spec) must fully match `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` in ASCII (no exponent, inf, nan, plus sign, leading zero, whitespace or underscore). Checks run on the text before any Decimal operation: length <= 80 (`number_too_long`), shape (`invalid_number`), at most 64 significant digits from the first nonzero digit and at most 64 fraction digits (`number_precision`, refused never rounded), then |v| <= 10^12 by exact `copy_abs` compare (`number_range`). `study_id` is non-blank text of at most 128 characters (checked first), then Unicode-checked: no Unicode control, line/paragraph separator or bidi/format characters (categories Cc, Zl, Zp, DEL, and the format characters U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF); ordinary spaces and printable non-ASCII are allowed. Refusal `invalid_study_id` names the field, never the value. The 500-point cap is stricter than a 1000 cap. Refusal text is `PROCAP1537: <code>: <message>`; payload, count, spec-order and zero-variation messages are unchanged.
Derived values (mean, sigmas, indices) are 64 significant digits rounded, not exact, then output rounded half-even to 9 places. All arithmetic runs in a fully specified local context (prec 64, ROUND_HALF_EVEN, Emin -999999, Emax 999999, capitals 1, clamp 0, traps InvalidOperation, DivisionByZero, Overflow, Underflow; Inexact not a trap), so the ambient context cannot change output. A trapped condition is refused as `PROCAP1537: arithmetic: computation could not complete`, never a raw decimal exception.
Bounded domain for the zero-variation check: with these bounds the smallest nonzero deviation is 1e-64 and Emin is -999999, so no deviation or squared deviation can underflow or cancel to zero; distinct values therefore always give both sigmas above zero, and the zero-variation refusal fires only for a series of identical values. An index too large to quantize (for example a 1e-64 sigma against a 1e12-wide window) is the mapped arithmetic refusal. The earlier argument that rested on unbounded exponents (1E-600000) is withdrawn: that input is now an invalid_number refusal.

## LIMITS
Index arithmetic over supplied data only. Normality and stability are assumed, not tested or established. No confidence intervals, no non-normal methods, no target-based index (Cpm), no acceptance, qualification or release claim, no physical measurement, no certification. Not a statement about any real process. No wiring, no routes, no existing file edited.

## Mutation battery (builder's own, 48 hand-written mutants, one at a time)
Round 1: 46 killed, 2 survived (the two halves of the zero-variation check). I then added one test (an underflowed overall sigma refuses instead of dividing) after seeing them, so round 2 is not independent of round 1.
Disposition of the remaining survivor, a builder claim for the auditor to check, not a fact: dropping the sigma_within == 0 half of the check cannot change any output, since sigma_within is zero only when every moving range is zero, i.e. all values equal, which also makes the overall sigma zero (the overall sigma underflows to zero no later than the within sigma). Claimed equivalent.
Process note: tests were written first and run red (collection error, module missing) before the module existed.

## Hardening child
Policy not applicable: pure offline, no spend/outreach/fakeacct/autopost/scrape/trade surface. The original unit's tests-first red run is kept as recorded above; this child also ran its tests first (red at 18:36:06, 10 failing, before any core change). Mutation counts for this child are in the section below if present; the original 48-mutant history is unchanged.

## Hardening child mutation battery
55 more hand-written mutants over the new code, one at a time, single round (no tests added afterwards). 51 killed, 4 survived. Dispositions, claims for the auditor only: removing `re.ASCII` (pattern uses only explicit `[0-9]` classes); and three variants of the zero-variation condition (`or` to `and`, dropping either sigma test), claimed equivalent only inside the bounded domain above, where the two sigmas are zero together. Outside that domain (not reachable through the grammar) the claim would not hold, which is why the domain is stated.

## Unicode rule child
Covered field: study_id (the only echoed text field; numbers are ASCII-only by grammar). Length cap first, then the Unicode check, before use. 23 hand-written mutants on the check: 21 killed, 2 survived, both claimed equivalent for the auditor: dropping the explicit DEL test (U+007F is category Cc, already refused) and widening the second format range down to U+2029 (that code point is category Zp, already refused). Test-first: red 18:38:19 (2 failing) before the core change.

## Cap-first child
After the type check the first operation on `study_id` and on every number (values, lower_spec, upper_spec) is the raw length check, before strip, regex, Unicode scan or parse: `_study_id` is type check, then `len > 128`, then blank, then Unicode; `_parse` is type check, then `len > 80`, then grammar. Breaking-order note: an all-blank study_id longer than 128 characters is now refused as too long (previously as blank); the cap was already on the raw length. Tests pin a 10 MB string refused as oversize with peak allocation under 1 MB (tracemalloc) for study_id and all three numeric fields, and the first two operations in the source. Input types unchanged from the original unit (decimal strings only). Red 18:45:28 (3 failing), then green; 5 hand-written mutants (strip-first, dropped blank check, length after Unicode, regex-before-length, cap 129).
