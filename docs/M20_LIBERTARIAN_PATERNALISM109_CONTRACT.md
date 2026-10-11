# Row 109 Libertarian Paternalism - contract

## Ledger source pin
audits/additional-2000-features.json, id 109: requirement "Libertarian Paternalism"; description "Guides without restricting freedom"; status PARTIAL (read from main).

## Delta against the existing mechanism
Existing (delta base): `_libertarian`, backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:582, reached through `run()` in that file. This module is a new file; the existing file, routes and tests are not edited.
Behavior differences, each a deliberate refusal or change here and not a defect finding:
- `set()` over options raised a TypeError for an unhashable option: here every option is type-checked first and the refusal is typed.
- `population_shares` did not have to sum to 1: here they must sum to exactly 1 as fractions.
- `float()` coercion of utilities and shares: here utilities are exact integers or plain decimal strings and shares are plain decimal strings or the integers 0 or 1; floats and bool are refused.
- One arbitrary best option was reported on ties: here all tied options are listed, sorted.
- A fixed plus/minus 10 percent interval was emitted that was not derived from data: removed.
- `bool()` on the three autonomy flags: here each must be exactly true or false.
- Welfare and regret were rounded floats: here they are exact reduced fractions plus decimal strings rounded to 6 places half-even from the exact value.

## Interface
`review({"options", "default", "easy_opt_out", "transparent", "alternatives_visible", "expected_utilities", "population_shares"})`. Options: 2 to 20 unique strings of 1 to 100 characters. Utilities: one entry per option, an integer with absolute value at most 10^12 or a string matching `-?[0-9]{1,12}(\.[0-9]{1,6})?` (ASCII). Shares: one entry per option, a string matching `[0-9](\.[0-9]{1,6})?` with value at most 1, or the integer 0 or 1.
Returns `row`, `options`, `default`, `expected_population_welfare` and `_decimal`, `default_regret` and `_decimal`, `utility_maximizing_options` (all ties, sorted), `autonomy_preserved`, `deployment_allowed`, `limits` (three strings). Regret is the best utility minus the default's utility. `deployment_allowed` is true only when all three autonomy declarations are true and the regret is exactly 0.

## Refusals (prefix `LIBPAT109:`, exception LibertarianError)
Messages name the schema field and never include a supplied value: non-mapping input; too many keys (before any key is read); unknown key; missing key; non-bool flags; `options` not a list of 2 to 20, an option that is not a string, blank, over 100 characters (cap before strip and scan) or with a forbidden character, duplicate options; `default` not one of the options; `expected_utilities` or `population_shares` not a mapping, not exactly one entry per option (size checked before any key is read; a dict subclass is refused untouched), keys that are not the options, or a value outside the grammar; shares that do not sum to exactly 1. Control, format, line-separator and paragraph-separator characters are refused in options; ordinary spaces are allowed.

## Limits
Supplied declarations and numbers only; nothing here judges whether the utilities are right. Guidance must preserve a costless informed exit. The unit decides nothing for anyone, never sends or posts anything, measures no behavior and gives no advice. Boundaries pinned at N and N+1: options 2/1 and 20/21, option length 100/101, utility magnitude 10^12/10^12+1, share sums 1 and one millionth off.

## Status
Independent gate: separate record. Full test suite not run: only this row's tests were run.
