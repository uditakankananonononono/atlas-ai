# Row 55 mutation deepening (M22 blog, podcast and GitHub collectors)

Scope literal: test hardening only. Row 55 stays as the crosswalk records it; nothing here widens it. No production code
changed. No network: every collector call uses an injected fetch or a patched urlopen. This patch uses the harness
`run_mutations.py` from batch A (README.md in this directory).

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m22_source_collectors.py tests/modules/test_m22_phase2_features.py tests/modules/test_m22_row55_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b55`
  (writes `receipts_b55.txt`; mutants in `batteries/b55.py`, exact old/new text). CAUGHT only on pytest rc 1 with FAILED
  lines; rc 2/4/5, timeout or no FAILED line is INVALID; rc 0 is SURVIVED; an old text not found exactly once is
  NOT-APPLICABLE; SHA-256 restore check on every mutated file. Commit before running.

## Results
- 22 mutants M1-M22 on `m22_tools_hub/sources.py` and `collectors.py`: URL building (tag slug, quoting), non-JSON handling,
  kind assignment, result caps (DEV.to, iTunes, GitHub), summary truncation and HTML stripping, WordPress title, Hacker News
  fallback URL, iTunes genre/URL/artist rules, recency windows, byte cap, GitHub url field, registry membership.
- First run: CAUGHT=6, SURVIVED=16 (the existing tests checked only the first parsed name and shared field presence). The
  first-run receipt is preserved as `receipts_b55_run1_with_16_survivors.txt`.
- Repair: new `tests/modules/test_m22_row55_deepening.py` (9 tests) asserts exact URLs, caps, summaries and byte-cap
  behavior. Final run: CAUGHT=22, SURVIVED=0, INVALID=0, NOT-APPLICABLE=0, SHA restore True.

## Limits: what stays untested
- The crosswalk note that the pinned collectors returned 20 DEV.to blogs, 20 iTunes podcasts and 20 GitHub repositories for
  "python" came from a live run. It is not repeated here and these tests do not show live behavior.
- WordPress, Hacker News, GitLab, Codeberg, Medium and Podcast Index parsers are only partly covered (M9 and M10 touch two
  spots). Feed parsing, OPML, feed discovery and FeedWatcher are not mutated in this batch.
- Field names follow fixtures; a live API change would not be caught.
- The recency test uses the real clock with margins of days.
- A green run shows the tests notice these 22 edits, not that the collectors are correct or complete.
- Receipts are recorded local harness runs, not independently re-run.
