# Group 123 recoverable local repository artifact

Numbering: docs/program-evidence/README.md maps group 123 to repository links /
paths and local Git metadata. The live source doc output-format line asks for
"Repository links / paths." This adds actual recoverable repository output.
It does not certify hosted links, ownership, public access or product completion.

build_release(root, output) inspects a clean trusted-local checkout, creates
repository.bundle plus a content-hash manifest, independently clones into a fresh
bare Git repo, reads restored object bytes and modes, then rechecks source state
and worktree bytes before placing the release directory. replay_release(output)
repeats bundle hash, HEAD and file/mode replay later. No worktree checkout or
repository code execution; hooks and fsmonitor are disabled and ambient GIT_*
redirects excluded. Symlinks, submodules and dirty/untracked state are refused.
Failed builds remove their staging directory. Original files are not modified.

## Evidence

```sh
PYTHONPATH=backend python -m pytest --noconftest -p no:cacheprovider tests/test_repository_release_g123.py tests/test_program_repo_evidence.py -q -rf
python scripts/release/scoped_mutations.py audits/group123-release/mutations.json OUTPUT
```

Builder run: 44 passed in these two selectors (17 new release tests, 27 existing
program evidence tests), Python 3.12.14. Real locally authored Git repos and actual
Git bundles/clones are used, not an injected clone implementation. Six final
mutants CAUGHT with failed test IDs and byte-verified restores. Initial
source_change mutant SURVIVED because the tracked-byte recheck also refused the
alteration; the added untracked-during-replay probe catches the disabled status
check. Both initial and final logs are retained. Missing-module RED is a
collection error, not behavioral RED. No independent gate or ChatGPT review yet.

## PARTIAL scope and limits

- No hosted publication, remote verification, account ownership or private-data
  review. Local output paths require attachment/upload to become delivery.
- Bundle includes ancestor history. Old secrets/private data may be present even
  if HEAD is safe. This artifact must not be published without content review.
- Trusted checkouts and trusted release storage only. An attacker controlling
  bundle and manifest can forge a mutually consistent artifact; no signatures.
- Git subprocess timeout is 30 seconds per operation. Output allocations are
  bounded after disk capture, but temporary disk has no quota. Blob reads cap at
  8 MB; bundle cap is 512 MB, file count 50,000. No total tree/history byte budget.
- Before/after checks are not a hostile concurrent-writer race defense. Symlink
  ancestors of roots/output directories and filesystem replacement races are not
  contained. os.rename assumes trusted parent storage and one output writer.
- Filesystem mode replay uses Git tree modes, not complete filesystem metadata.
  LFS/filter-backed working bytes may differ from committed blobs and are refused.
- Empty, unborn, partial/shallow or missing-object histories may fail bundle
  creation/replay rather than be advertised as complete repository archives.
- Runtime package or HTTP routes do not call this helper automatically. This
  fulfills a concrete local artifact generation step, not literal group closure.
- No full repository regression, independent audit, visual/UI output or world-
  leading comparison was performed. Tests inspect byte/object behavior only.
