# DESEXP1539: two-level fractional factorial plan structure (ledger row 1539)

Provenance line: cross-account builder package, provenance held privately.
Status: local review branch, not accepted, not landed. Full test suite not run (only this unit's test file).

## Ledger source pin
audits/additional-2000-features.json, id 1539: requirement "Design of Experiments", status verified-pushed (historical builder attribution, not current proof), description "" (empty).
The description is empty, so the requirement title is the whole spec. This contract proposes the exact behavior below.

## Delta against the existing mechanism
backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py:180 (`_doe`) builds a full-factorial run matrix over arbitrary level lists, with a run-count cap. It has no fractional designs, no defining relation, no resolution and no alias structure. This unit (new files, shared cluster file untouched) covers two-level designs only, adding fractions 2^(k-g) from caller generators, the defining relation, the design resolution and the alias classes. Refusals carry the exact prefix `DESEXP1539: `.

## Mechanism
`plan_two_level_design(payload)` in `backend/app/modules/m20_general_cognitive_worker/design_of_experiments1539.py`. Input `{design_id, factors: 2..12 unique names (non-blank, no '*'), generators: 0..6 records {factor, product_of}}`. Each generator names a declared factor as the product of 2 or more distinct declared BASE factors (a generated factor cannot be used in a product). At most 8 base factors, so at most 256 runs. Output: the coded (-1/+1) run matrix in standard order (the first base factor changes fastest; generated columns are the product of their base columns; run order is NOT randomized); the defining relation (every word of the defining contrast subgroup, sorted by length then factor order, factors joined by `*`); the resolution (length of the shortest word, null for a full factorial); and the alias classes, each a group of two or more main effects and two-factor interactions that the design cannot separate (higher-order aliases are not listed). Labels: experiment_executed false, causal_claims_made false, randomization_required true.

## Text fields (Unicode rule)
`design_id` and every factor name are text of at most 128 characters (checked first), then Unicode-checked: no Unicode control, line/paragraph separator or bidi/format characters (categories Cc, Zl, Zp, DEL, and the format characters U+200B-200F, U+202A-202E, U+2066-2069, U+FEFF); ordinary spaces and printable non-ASCII are allowed. Factor names also exclude `*`. Refusals `invalid_design_id` and `invalid_factor` name the field, never the value; the generator and duplicate-name refusals no longer echo factor names. There is no decimal arithmetic and no numeric text input in this unit, so the number-grammar and decimal-context rules do not apply here.

## LIMITS
Plan structure over supplied factors and generators only. Two levels only; no centre points, no blocking, no response-surface, Plackett-Burman or mixed-level designs, no run randomization, no power or sample-size analysis, no analysis of results. No experiment is executed, no effect size, significance or causal claim is made, and no physical test, certification or release authority is implied. No wiring, no routes, no existing file edited.

## Mutation audit (builder-run, hand-written, one at a time)
63 mutants over the module. Round 1 killed 60 with 3 survivors; tests were then added after seeing the survivors (so round-2 kills are not independent). Final: 62 killed, 1 survivor (effects of size 3 also scanned as alias seeds): claim for the auditor that it is equivalent, because members are filtered to size 1..2 and a size-3 seed only yields classes already produced by their size 1..2 members. Nothing here is accepted or closed. Raw logs are in the package.

## Unicode child
Test-first: red 18:42:15 (8 failing) before the core change. Cleanup in this child: the committed 1539 test file had duplicated test definitions (a block repeated, so the later copy silently replaced the earlier); duplicates removed, one weak assertion (`resolution == 4 or resolution == 2`) removed, and the resolution-two test that had been shadowed is kept under its own name.
Mutation (this child, 38 hand-written mutants on the new text rule, single round, no tests added afterwards): 36 killed, 2 survived, both claims for the auditor: dropping the explicit DEL test (U+007F is category Cc) and widening the second format range down to U+2029 (category Zp). The earlier 63-mutant history above is unchanged.

## Cap-first child
After the type check the first operation on `design_id` and every factor name is the raw length check (128), before strip, the `*` scan, or the Unicode scan: `_text` is type check, then length, then blank or `*`, then Unicode. Breaking-order note: an all-blank or all-`*` name longer than 128 characters is now refused as too long (previously as blank or `*`). Tests pin a 10 MB string refused as oversize with peak allocation under 1 MB (tracemalloc) for both fields, and the first two operations in the source. Red 18:45:47 (3 failing), then green; 5 hand-written mutants (strip-first, `*` scan first, dropped blank check, dropped `*` check, cap 129), all killed.
Open finding, not changed: each generator `product_of` list has no length cap, and its entries are compared with `repr` and membership tests before the 2-or-more/declared checks; a very long list or very long non-string entries is unbounded work. A length bound for `product_of` is a new cap, so it is left for the author to decide (the declared factors are at most 12, so a cap of 12 would be the natural candidate). No numeric input exists in this unit.

## product_of cap (child fix4)

Ledger pin: live main 605be42e49605b4e8fecc5b28d2bb9b3886a8e43 at 18:54 IST by ls-remote; 1539 paths are absent there, so this child sits on the review/doe1539-fix3 lineage (fix3 tip fc633ee9, superseding its cap of 12).

Delta (design_of_experiments1539.py, `_product` helper, called from `_generators`): per generator, in order: exact list type, `type(value) is list` (a subclass, tuple or any other iterable is refused as invalid_product_of before length or iteration, so no subclass code runs), then length at most 8 (invalid_count), then at least 2 (invalid_count), before any entry is touched. Each entry: exact str, length at most 128, Unicode check, exact membership in a frozenset of declared names; then distinctness. No repr, no value, no index in any refusal. The outer generator cap of 6 still runs first. No numeric interface and no change to the base-factor limit of 8.

The cap equals the base-factor maximum: 8 entries are valid end to end, 9 are refused by count. The earlier 12-entry fixture and text are removed.

Evidence: RED 18:54:08 (2 failed, 35 passed); mutants listed in the package logs.

no Unicode control, line/paragraph separator or bidi/format characters

Provenance line: cross-account builder package, provenance held privately.

LIMITS: full suite unrun; only the 1539 test file ran. Compose check is a throwaway merge only. No push.
