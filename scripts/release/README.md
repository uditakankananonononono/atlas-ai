# Local mailbox packaging

`package_mailbox.py` runs an explicit list of repository test files on a clean
checkout at the release head, emits a git-am mailbox, applies it on a detached
base worktree, verifies the resulting tree and both commit identities, and
writes an external SHA256 receipt. It never pushes or changes remote state.

```sh
python scripts/release/package_mailbox.py --base BASE --head HEAD --selector tests/release/test_package_mailbox.py --output OUT
```

Output must be new. A failed or timed-out selector keeps its actual log and
labels its result FAIL or UNTESTED-TIMEOUT; it never becomes a passing claim.
The command uses --noconftest and restores the development-only auth fixture
values for these local tests. Public notes use portable Python commands;
external receipts retain the exact executable used.

UNTESTED: hostile repositories/test files, external effects, historical mutant
batteries, whole-repository regressions. This helper is for trusted local
checkouts, not a sandbox. The test-process timeout does not claim descendant
process isolation. Receipts bind mailbox bytes, test-log bytes and base/result
trees; they are external so no file needs to contain its own content hash.
