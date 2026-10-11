Source pin: instinct doc P76|L64, line map v4. Verbatim: "Every project/task/module/tool/research project must produce the following deliverables,"

# P76|L64 Deliverables manifest validator - contract

Module: `backend/app/modules/instinct_doc/deliverables_manifest_p76.py`. Pure stdlib, deterministic, fully offline. No clock, randomness, I/O, filesystem or network. Same input gives byte-identical output. No wiring: no route, no registration.

## The 15 deliverables (pinned from line map v4 rows P77..P91, verbatim summaries)
1. a separate repository per project
2. 120+ real datasets where possible
3. 40+ external tools/services/APIs per project (Benchling, AlphaFold, etc.)
4. 200+ external tools across the program where feasible
5. vast code, tests, verification scripts, mathematical formulas
6. real-life data wherever possible
7. rigorous testing and external validation
8. benchmark comparison against the world-leading tool in the field
9. 50+ page research paper, Times New Roman, good formatting
10. ChatGPT-as-judge review loop improving novelty, rigor, benchmark performance
11. a new discovery/diagnosis/method/breakthrough where claimed
12. self-improvement mechanisms per tool/module
13. evidence of passing all requirements exactly, no thin construction
14. scope each project at ~5 years of human time
15. beat all relevant world benchmarks, best in world per field

## API
- `validate_manifest(manifest)` returns the canonical declaration rollup dict. The input is never mutated. A refused manifest changes nothing; incomplete manifests are refused with exact codes.
- `DELIVERABLES`: the 15 summaries above, in order.

## Manifest shape
Exactly three fields, no unknown or missing keys, no truncation, no coercion:
- `project_id`: nonblank string 1..64 chars.
- `kind`: exactly one of `project`, `task`, `module`, `tool`, `research_project` (the five subjects named in the source line).
- `deliverables`: a list of declaration records, each exactly `number` (strict int 1..15, bool refused) and `evidence_ref` (nonblank string 1..128 chars; recorded verbatim, never resolved).

## Completeness rule
Every number 1..15 must be declared exactly once. A duplicate is refused `P76:duplicate_deliverable:<n>` (first repeat in input order). Any missing numbers refuse `P76:missing_deliverables:<csv>` with all missing numbers sorted ascending (empty list declares nothing and reports all 15). A valid manifest returns deliverables sorted by number, `deliverable_count` 15, `complete` True.

## Injection defense
Every free-text field (project_id, evidence_ref) rejects Unicode categories Cc, Zl and Zp, refused `P76:unsafe_chars:<name>`. `kind` is enum-checked, which refuses control characters by construction.

## Honesty shape
`status` exactly `declared_manifest_only`; `evidence_verified` and `deliverables_produced` exactly False always. Boundary verbatim: "Only the supplied manifest is checked. All 15 deliverables are caller declarations; declaration is not production, evidence refs are recorded but never resolved, and validation never touches a repository, dataset, tool or paper."

## Composition (no duplication)
Per-deliverable verification lives in the landed siblings and is NOT re-implemented here: P77 (repo_per_project) covers deliverable 1 structure, P81 (deliverable5_audit) covers deliverable 5 presence, P253/P255/P258 registers own repository links, tool integrations and paper declarations, P88 owns self-improvement consistency (deliverable 12). This validator consumes only the manifest as data; evidence_ref values are where sibling outputs are referenced. No sibling module is imported (family convention, per P81's docstring).

## Refusals (ValueError, exact text, P76: prefix)
`P76:bad_type:manifest`, `P76:unknown_fields:manifest`, `P76:empty_field:<name>`, `P76:bad_type:project_id`, `P76:text_too_long:project_id`, `P76:unsafe_chars:<name>`, `P76:bad_type:kind`, `P76:bad_kind:<value>`, `P76:bad_type:deliverables`, `P76:bad_type:deliverable`, `P76:unknown_fields:deliverable`, `P76:bad_type:number`, `P76:number_out_of_range:number`, `P76:duplicate_deliverable:<n>`, `P76:missing_deliverables:<csv>`.

## Order of checks
Manifest type, unknown fields, missing fields (FIELDS order), project_id (type, blank, length, unsafe chars), kind (type, enum), deliverables type, then per record in input order (shape, unknown fields, missing fields, number type, number range, evidence_ref), then duplicates, then missing.

## Interpretation choices (flagged for review - the source line pins only the header sentence)
- Manifest shape (3 fields, per-deliverable number + evidence_ref records) is invented in the family register style; `P76:` refusal prefix follows the P254/P256 convention.
- The five `kind` values come straight from the source line's "project/task/module/tool/research project".
- Limits invented: project_id 64 (family id limit), evidence_ref 128 (P255/P258 evidence_ref limit).
- One-shot validator (not an append-log): the line is a requirement statement, so the artifact is a validation verdict; matches P81's consumes-data style.
- Duplicate-before-missing check order is deterministic and documented.
- Only Cc/Zl/Zp rejected (family injection-defense convention); other invisible categories out of scope.

## Limits
Declaration validator only. It never verifies that any deliverable was actually produced, that evidence refs resolve, or that a manifest was not fabricated. Passing tests is not audit acceptance.
