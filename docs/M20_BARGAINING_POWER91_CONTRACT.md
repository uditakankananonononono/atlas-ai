# BARGAIN91: caller-declared factor model

Source-pinned at public base4088674fcc3f9c7d96d25471575db6b0a9faa193. `audits/additional-2000-features.json` row91 reads "Bargaining Power Assessment", "Evaluates negotiating positions", PARTIAL. Ledger SHA256285cc16c474215b241383fb922c8a2f2abfa9f7cda3592b04dc61141317d83ff. Existing negotiation_behavior_0085_0109.py:224 already implements single-party bargaining arithmetic with fixed weights229, fixed band233 and confidence0.6 at243. Coverage-register's verified label is not independent evidence. This additive standalone module does not replace, wire or edit that cluster or either ledger.

Delta: explicit caller model, multiple parties, exact Fraction component arithmetic, exact ties and competition ranks. This is a heuristic declared model, not empirical negotiating power, persuasion, outcome prediction or evidence verification. No real action, code execution, network, private account access or automatic decision.

## Input and arithmetic

`evaluate_bargaining_power(packet)` takes exactly model/parties. Model has exactly alternatives/resources/time_pressure/dependency. Each factor has weight (nonnegative rational string p or p/q), scale (integer1..1000000) and direction. Alternatives/resources direction benefit, pressure/dependency penalty and flag scale1. At least one positive weight. No weight normalization or fitted weights.

Parties1..64, each id/position/factors plus optional batna_record. Every factor required. Alternatives/resources integer0..declared scale, not bool. Pressure/dependency strict bool. Score=sum(weight*factor/scale), penalties negated. Output exact canonical Fraction strings; no float rounding. Rank descending, equal score shared rank1,1,3 with partyid lexical display ordering. Exact components, model copy, declared positions and tie groups retained. `real_world_power_verified` false. No confidence or uncertainty interval invented.

LIMITS:64parties,2000position characters,100id characters,scale1..1000000,weight numerator/denominator0..1000000 with positive denominator. Bounded nonblank control-free strings. Unknown fields, missing factors, duplicateids, wrong types/scales/directions and bounds refuse with `Bargain91Error` and exact `BARGAIN91:` prefix. Input is not mutated.

## Optional BATNA92 declaration adapter

Neighbor contract pin supplied from review/batna92 tip8858d097d5e76af82fd6fb2936073cf5a88ef69c, docs/M20_BATNA92_CONTRACT.md. Not imported or executed by this module. The joint compatibility scope and evidence status are below. Only supplied to_dict shape used as data: version string1, options_count integer, best_names list, best_utility rational string, is_tie bool, ranking list{name,utility rational string,rank integer}, margin_to_next rational string or null, limits list of five strings. Upper local adapter bound1000options,128rational characters. Checks ranking descending, competitionrank, best names/tie and best-minus-highest-strictly-lower margin; top tie with lower option has positive margin. Names tie order preserved from record. These checks do not prove options exist or author utility is correct.

BATNA declaration is optional and retained separately. It NEVER converts best utility into alternative_strength or changes scores. Factors are caller ratings independent of BATNA utility. No unlanded dependency import, no automatic conversion between different parties' utility units.

## Joint BATNA92 compatibility scope

Compatibility is "cleared within these caps", stricter than BATNA92, not universal compatibility. This wording records the peer-stated interim supplied through the coordinator on 2026-10-11 for BARGAIN91 f01e4ac54391e799390d2c268d2674e3b0a6dde1 and BATNA92 8858d097d5e76af82fd6fb2936073cf5a88ef69c. It is scoped interoperability evidence, not acceptance or landing of either unit. BATNA92 source and raw peer execution logs were not supplied for independent reproduction here.

The declaration adapter expects exactly version/options_count/best_names/best_utility/is_tie/ranking/margin_to_next/limits. Version is the string "1". Ranking uses descending utility and competition ranks; tied names retain record order. best_names must equal the top tied names. margin_to_next is best minus the next strictly lower utility, or null when none exists. limits contains exactly five text declarations. These consistency checks still apply within the caps.

Local caps and text rules:

- options_count is a strict integer from 1 through 1000, and ranking length must equal it.
- Every utility string, including best_utility and a non-null margin_to_next, has at most 128 characters and matches the adapter's signed integer or rational grammar. Fractions are parsed exactly. The adapter takes rational strings, not native float, Decimal or Fraction objects.
- Each ranking name and each of the five limits declarations is a nonblank string with at most 2000 characters. Characters below code point 32 and DEL (127) are refused.

The peer interim reports accepted BATNA92-produced records for single options, ties, negative utilities, Fraction utilities, float-as-exact-Fraction text, Decimal utilities, 1000 options and a 3**80 denominator. These are bounded examples, not a promise that every value in those input categories fits. In particular, larger denominators can exceed the serialized 128-character cap.

The peer interim also reports four records valid for BATNA92 but correctly refused by BARGAIN91: utility text longer than 128 characters, a control-character name, a name longer than 2000 characters, and more than 1000 options. Such a refusal is an intentional local boundary, not evidence that the BATNA92 record itself is invalid. No caps are relaxed, and no records are truncated, sanitized or coerced to fit. Compatibility does not convert utility into bargaining factors, verify real-world alternatives, or authorize action.

## LIMIT note: exact observed Unicode examples

Builder-observed locally against the frozen core on base c07e4b4272f2ed3777e2c20100d42c0e621f5883, Python 3.10.12: both weight parsing and BATNA utility parsing accept the Unicode numerator examples "٣" -> 3, "٣/4" -> 3/4, and "١٢" -> 12. Both refuse the exact non-ASCII denominator example "3/٤" with Bargain91Error. These are observations only, not a recommendation or a general Unicode compatibility claim. No conclusion is stated for the different denominator-tail case "1/١٠". No runtime or tests changed.

## Tests and gaps

Real standalone execution of rational arithmetic; synthetic input packets, not real negotiations. Nine tests cover ranks/ties/components/refusals/exact weights/determinism/copies and optional adapter consistency. Raw RED missing module, GREEN and scratch hand-mutants separately supplied. Interpreter/version explicit in raw. No mounted auth/tenant, existing cluster floor, repository full suite, Python3.12, external validation, empirical power or production wiring run. Local fixture evidence is not a real-life claim. Core/test/doc additions only, no shared edits. No acceptance, landing or full-row fulfillment claimed.

The tests-only child f01e4ac5 adds eleven exact-boundary tests to the original nine, all passing locally on Python 3.10.12. The present docs-only child reruns those twenty tests without changing runtime or tests. The scoped peer interim above does not replace the not-run production, external-validation or full-suite checks.
