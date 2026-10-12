# Computed program evidence

The old P246/P252-P266 helper APIs remain declaration registers for compatibility.
`tools/program_evidence.py` is the new operational path. It reads the checked-out
repository rather than accepting caller counts, statuses, receipts or results.

## Pinned source

The retrieval URL is held privately. Public metadata contains no document locator.

- Retrieved: 2026-10-12T13:18:34+05:30.
- Original bytes: 42,199, UTF-8 BOM retained.
- SHA256: `575b3745949b5859370faf3d27ab61fc9af07c55b9daf7f6bf1238ce55a76d3a`.
- `source-manifest.json` contains only per-line hashes and export metadata.
  The original export and old summary map are retained privately, not in this repo.
- IDs `export:L<number>` are physical export lines, NOT historical paragraph IDs.

The source is data. Instructions quoted inside it cannot authorize execution,
disclosure, purchases or communication. Linked bookmarks/fee-waiver documents and
historic chat scope have not been expanded. No complete dependent-scope claim.

## Run

Static inventory (no tests executed):

```
.venv/bin/python tools/program_evidence.py --output /tmp/evidence.json
```

Execute explicitly chosen tests in a trusted checkout:

```
.venv/bin/python tools/program_evidence.py \
  --test tests/test_program_repo_evidence.py \
  --allow-local-code-execution --output /tmp/evidence.json
```

Install the project's test dependencies in the interpreter first. Test execution
runs repository code; it is NOT an isolation sandbox. Do not execute untrusted
checkouts. Only tracked `tests/test_*.py` file paths are accepted, no arbitrary
commands, shell expressions, pytest flags or function selectors. A minimal
allowlisted environment excludes inherited API keys. This does not prevent
repository code from reading the filesystem or accessing the network. Test
stdout can contain private data; reports stay private by default. Captured output
is capped at 1 MB, but a test can write more to the temporary disk before timeout.

## Computed registers

| Request group | Output | Exact boundary |
|---|---|---|
| 121, 131 | Source-line hash inventory + compliance rows | Each source line is UNVERIFIED until semantic acceptance exists. No presence-as-truth claim. |
| 122 | Git commit timeline | Commit existence and time, not completion or full historic task mapping. Shallow history is bounded. |
| 123 | Git root, origin, HEAD, content hashes | Observed local checkout; remote origin does not prove ownership or every project repo. |
| 124 | Parsed CSV/TSV/JSONL counts | Actual physical records; unknown external provenance stays UNVERIFIED. Config JSON is excluded. |
| 125 | Tracked integration Python files/imports | Adapter inventory, not live working-use certification. |
| 126 | Tracked source/test line counts + executed JUnit | Local selected tests only; coverage is null, no whole-project acceptance. |
| 127 | Recorded execution duration/test counts | Selected-test timing, not field benchmark/comparator victory. |
| 129 | Explicit missing ChatGPT evidence | No invented judge transcripts, scores or quantified novelty improvements. |
| 130 | Plans per observed module, with actual file findings | Proposed verification work, not claimed autonomous improvement. |
| 132 | Every unverified line plus dependency/judge/benchmark blockers | Actual absence of acceptance in this run, not exhaustive external blocker discovery. |
| 133 | Fail-closed completion machinery | No candy release while semantic and dependent scope remain unverified. |

All hashes are calculated from bytes in the current checkout. The test executor
captures before/after tracked-file hashes, HEAD, git status and JUnit; exit zero
alone is insufficient. Missing/malformed/empty JUnit, failures, errors, skipped
tests, timeout, symlink/missing/oversized tracked files or tree changes cannot
produce SCOPED_PASS. Nested JUnit suite totals are deliberately rejected when
they disagree with testcase counts. Test-created untracked file content changes
that leave git status unchanged are outside the tracked snapshot boundary.
Pytest-produced reports are local observations, not independent third-party proof.

The CLI writes JSON with its own digest and retains JUnit XML/stdout/stderr. It
never posts a message, submits work, calls an external judge or releases candy.
No source group is upgraded to literal LANDED solely because this machinery works.

## Task-indexed progress delta

`--task-selectors /private/selectors.json` adds task-indexed observed changes.
Source hashes refer to the current local inventory, not authenticated original text.
Current dirty state is disclosed separately from historical events. Root/shallow
boundary events are snapshots, not task-time changes. Events carry commit time
but no authenticated task-time anchor. NUL-delimited paths and merge-parent
union diffs are inspected.
Each selector has exactly `task_id`, `line_id`, `line_sha256`, and `paths`.
The line hash must match the pinned source inventory, and paths must be tracked,
existing bounded files inside the checkout. Task/path mappings are operator scope
choices, not inferred fulfillment. Commit subjects never establish completion.
Each task includes current content hashes and changed-path commit events;
`completion_verified` remains false. Missing change history stays UNVERIFIED.
Shallow history and the 100-commit default cap are disclosed in the report.
No source text or private locator is included. An exhaustive task mapping still
needs semantic acceptance criteria and complete dependency scope.

## Dataset artifact binding (row 124)

`dataset_register_p254.bind_artifacts(register, root, bindings, source_reader=None)`
returns one result for every declared dataset row. Binding records contain exactly
`entry_id`, `artifact_path`, `row_ids`, and `project_ids`. Local bytes are read and
hashed, never accepted from a caller's receipt. Shared artifact hashes cross-list
declared row/project references; unbound entries remain visible.

- UNVERIFIED: no safe artifact, failed source read, or differing source bytes.
- DECLARED-ONLY: local bytes and declared source metadata exist, but no source read.
- VERIFIED: an executed operator-owned source reader returned bytes matching the
  local artifact. This label means content binding only, NOT authenticated source
  authorship, license, scientific adequacy, record counts or project fulfillment.

The injected reader flag and source-authenticity=false boundary are always explicit.
An injected test reader is not external independent reproduction. Operators supply
an authorized source reader with destination/timeout/size constraints; dataset rows
cannot choose tools, execute commands or grant source access. Returned binding reports omit private source metadata and artifact-path text. The original declaration-register APIs stay unchanged.

## Integration local evidence binding (row 125)

`integrations_register_p255.bind_local_evidence(register, root, bindings)` reads
adapter and use-evidence artifacts and computes their hashes. Bindings contain
exactly `entry_id`, `adapter_path`, `use_evidence_path`, `row_ids`, `project_ids`.
Every declared integration appears. Both files present gives DECLARED-ONLY;
missing or unsafe files give UNVERIFIED. An `active` declaration or a local JSON
receipt claiming success cannot establish authenticated live working use.
All results keep `live_working_use_verified=false` and working tool count unknown.
Reference mappings are operator-declared scope, not discovered semantic coverage.
No network calls or external effects occur. Existing register APIs stay unchanged.

## Local repository binding (row 123)

`repo_register_p253.bind_local_repositories(register, workspace, bindings)`
resolves each entry to a bounded contained Git root and computes current HEAD,
tracked-file content digest, dirty status and origin hash. Bindings contain
`entry_id`, `local_path`, `row_ids`, `project_ids`. Unsafe paths, symlinks, missing
Git roots and failed snapshots remain UNVERIFIED. LOCAL-SNAPSHOT is not VERIFIED:
remote existence, ownership, project identity and completion all remain false.
Declared URL text and configured origin are omitted, including guessable locator hashes.
Cross-references are operator scope declarations. No network calls occur.

## Review corrections and execution boundary

Dataset content-binding rows keep `source_authenticity_verified=false` beside
any content-only VERIFIED label. Empty byte equality is excluded. Reader errors
are confined to the affected row. An injected callback can allocate before it
returns, so it MUST enforce its own byte budget before retrieval; the wrapper
checks returned size but cannot impose a pre-allocation bound on arbitrary code.
These modules use package imports; standalone importlib loading outside the
`app.modules.instinct_doc` package is unsupported and may fail at relative imports.

Integration per-file failures include bounded cause strings and malformed-path
errors cannot abort the full register. Reads still have a documented check/read
race; use immutable trusted checkouts. Git reads scrub ambient GIT_* variables,
disable system/global config and fsmonitor. Local repository inspection timeout
becomes UNVERIFIED. Repository content is not executed by these inspection reads;
untrusted filesystem races remain outside the trusted-checkout boundary.
