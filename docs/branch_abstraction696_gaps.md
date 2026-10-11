# Row 696 Branch by Abstraction: disclosed gaps

Module: backend/app/modules/m20_general_cognitive_worker/branch_abstraction696.py
(at base commit 84d91217, sha256 c7cb4a38b4c3049066fb16c4514b34e216fa57ffecddd6c43465d2b283872116).

| ID | Location | Gap | Current pin | Desired-behaviour test |
|----|----------|-----|-------------|------------------------|
| G1 | line 85 (set_route) | REPAIRED in this commit: bool refused | test_canary_percent_refuses_booleans | ordinary test |
| G2 | line 48 (__init__) | REPAIRED in this commit: bool refused | test_min_equivalence_cases_refuses_booleans | ordinary test |
| G3 | lines 164-190 (scan_direct_usage) | REPAIRED (bounded): ast.Import matched by full dotted name or last segment; asname of Import and ImportFrom tracked and later uses reported as kind "alias" | plain-import, dotted, alias tests | ordinary tests |

Fix sketch for G1/G2: add `and not isinstance(v, bool)`. Fix sketch for G3: handle `ast.Import` and match `alias.name.split(".")` against the symbol. Neither is applied; the module is untouched on this branch.
Scope limits remain: the scan is static single-file AST only (no dynamic access, getattr, or string-built names).

Module sha256: c7cb4a38... (base) -> ca51851b... (G1/G2 bool guards) -> 2dff517ec334d21e08f5370bbe7c2b454ff8924b3183ff512b82ae0a76de5961 (G3 import/alias tracking).

## Named residuals (not fixed; the scan is static and per-file, not a whole-program proof)

Dynamic access is not detected: getattr(m, "Old"), string references, `from m import *`, importlib / __dict__ access. Pinned by test_KNOWN_RESIDUAL_dynamic_access_is_not_detected_static_scan_only.
Further residuals reported by an independent audit, not pinned or changed here:
- R1: scan_direct_usage({}, symbol) with an empty sources dict satisfies the scan-recorded gate.
- R2: a later scan with a different symbol replaces the earlier findings, which clears a dirty scan.
- R3: allowed_files uses `path in allowed_files` with no path normalisation ("./a.py" != "a.py"), and a plain string matches by substring.
- R4: `import other as OldPricer` is not reported at the import line (only later uses as kind "name"); string annotations are not flagged.
- R5: false positive: any attribute named like the symbol (e.g. `cfg.OldPricer = 1`) is flagged as kind "attribute".
- R6: aliasing is single-hop and name-based: `y = x` where x is an alias is reported at the use of x, but y is not tracked.
- R7: findings come in ast.walk (breadth-first) order, not source order, within a file.

## Scan pins added in the tests-only follow-up

tests/modules/test_branch_abstraction696_scan_pins.py pins: dotted symbol (full-name match), whole-segment suffix match (no `xOld`, no `pkg.OldX`), case sensitivity (Import and ImportFrom), several names per import line, imports and aliases inside functions and classes. Pinned as current behaviour and documented limits, not goals: a dotted symbol never matches an ImportFrom name; the old name in a non-final dotted segment (`import pkg.Old.sub`, `import Old.sub as q`) is not matched; `from Old import z` is not flagged; alias tracking is scope-blind (a parameter named like the alias is reported) and does not notice rebinding (`X = 5` is reported).
Correction to an earlier note: dropping the full-name comparison is NOT equivalent, because a dotted old symbol (`pkg.Old`) only matches through the full-name comparison; it is now covered by a test.

## Removal-gate meaning and declared limits (tests/modules/test_branch_abstraction696_residual_pins.py)

A CLEAR can_remove_old means only that none of the caller-supplied files showed a static reference. It never means no reference exists anywhere. The scan cannot tell that the supplied inventory is complete.

Over-report (fail-safe, KNOWN LIMIT, not a goal): scope-blind aliases, rebinding (`X = 5`), and `X.Old` after an alias import (alias Name and Attribute both reported). These block removal; they do not let it through.

Fail-open, DECLARED NOT DETECTED: getattr / importlib / string references, `from m import *`, `from Old import z`, the old name in a non-final dotted segment, a dotted symbol against `from pkg import Old`, and any file missing from the supplied inventory. The gate stays CLEAR in all of these.

Inventory and scan state: an empty `{}` inventory satisfies the scan gate and a partial inventory is not detected as partial (KNOWN QUIRK). A later scan replaces the previous result, so a scan with a different symbol clears a dirty scan: last scan wins (KNOWN QUIRK; no core fix approved).

allowed_files: exact string match, no normalisation ("./a.py", "A.py", "a.py " and "svc/a.py" do not match "a.py"). If a bare str is passed instead of a list, `path in allowed_files` is a substring test, so "svc/a.py" skips "a.py" (KNOWN QUIRK, fail-open; refusing a bare str needs core approval, not granted).

Mutation note: for min_equivalence_cases the only guard narrowing that is equivalent is "refuse only True" in place of the bool check, because False < 1 is already refused.
