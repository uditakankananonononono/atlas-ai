# Per-project deliverable contract: bounded local checker

## Supplied Doc scope (data, not independent authority)

[P76|L64] For every project, task, module, tool, or research project, produce:

[P77|L65] 1. A separate repository.

[P78|L66] 2. 120+ real datasets where possible.

[P79|L67] 3. 40+ external tools / services / APIs / platforms used, e.g. Benchling, AlphaFold, etc.

[P80|L68] 4. 200+ external tools overall across the program where feasible.

[P81|L69] 5. Vast amounts of code, tests, verification scripts, and mathematical formulas.

[P82|L70] 6. Real-life data wherever possible.

[P83|L71] 7. Rigorous testing and external validation.

[P84|L72] 8. Benchmark comparison against the world’s leading tool in that field.

This package is only a schema and local check mechanism for non-science declarations. It does not fulfill any of these lines. Requested targets remain separate from observations. No datasets, external tool uses or SOTA numbers are minted.

## Contract

`validate_spec(spec)` accepts exact fields project_id, domain, source_lines, repository, requested_targets, artifacts and benchmark. Domain is software/non_science only. Source references use Pn|Ln. Repository is a declared credential-free HTTPS URL, never fetched or created. Requested targets have exactly datasets/project_tools/program_tools, nonnegative integers. They are requested quantities, not achieved counts.

Each artifact declares id, kind, relative path, lowercase SHA256. Kinds: dataset, tool, code, test, verification_script, formula, real_life_data, external_validation, benchmark_output. These are caller labels, not verification of meaning. Duplicate ids/paths fail. At most 10000 declarations. Benchmark metadata is null or comparator/metric/dataset_artifact_id/result_artifact_id/protocol with existing references. It does not assert a leading comparator or measured performance. No metrics are generated.

`check_deliverables(root, spec, max_file_bytes=10000000)` reads existing local files. Paths are relative, contain no traversal, and are opened component-by-component using Linux dirfd, O_NOFOLLOW and directory descriptors. Symlinks and special files are refused. Nonempty regular files are hashed in bounded chunks. Before/after size, modification time and change time are compared; changed files, hash mismatches and unreadable/missing files do not count. Equal content or equal inode identity counts only once, attributed to the first declaration's caller-supplied kind. Counts explicitly mean measured unique nonempty hash-matching file artifacts, not datasets used, tools executed or content validity.

All of repository_created, dataset_use, real_life_data, tool_execution, test_execution, external_validation, benchmark_execution and sota remain UNVERIFIED, even if files exist. doc_lines_fulfilled is false. A test log or benchmark file being present does not prove its execution or truth. The checker never executes artifact code, makes network requests, creates repositories, writes files, imports datasets or publishes output. It does not read private environment values.

## Existing neighbors and gaps

At base 1776396ffece1113e20ef7ca8484cf1b729ed70c:

- scripts/validate_audit_evidence.py:8-32 parses resolvable pytest names, not execution or produced artifacts.
- scripts/generate_implementation_audit.py:6-11 renders declared coverage register statuses.
- backend/app/runtime/capability_audit_13.py:15-20 checks evidence files/module registration and supplied attestations, not hash-bound measured outputs.
- backend/app/modules/m23_study_abroad/evidence_matrix.py:5-18 links application provenance with an explicit truth boundary.

Unit 11's unpublished requirement_matrix_audit (supplied commit 990d1263) is a neighbor awaiting comparison at integration. Its paths backend/app/requirement_matrix_audit.py and tests/audit/test_requirement_matrix.py are neither imported nor edited. Absence from main is not absence of that work.

## Verification limits

Standalone tests use real temporary local files, SHA256, hard links and symlinks, not simulated file-existence success. Mutation script and raw logs are separate evidence. No mounted tenant/auth, full repository suite, Python 3.12, external validation or benchmark execution is claimed. This is Linux-specific and not a hostile-filesystem sandbox. Concurrent rename of already-open directories is not independently detected; caller must control the local root and prevent adversarial mutation. Before/after stat checks cannot prove content truth. Memory/output counts are bounded per declared list/file, not a global runtime cap.

No routes or wiring. No integration or acceptance claimed. No separate repository, actual datasets, actual tools, real-life data, rigorous external validation or leading-tool comparison produced by this package.
