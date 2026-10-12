# Computed program evidence

The old P246/P252-P266 helper APIs remain declaration registers for compatibility.
`tools/program_evidence.py` is the new operational path. It reads the checked-out
repository rather than accepting caller counts, statuses, receipts or results.

## Pinned source

- Export URL: https://docs.google.com/document/d/1VRD84FClUlTk5pX8kcW6ZFxGfbAR6MwH8EoWdkCzlss/export?format=txt
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
