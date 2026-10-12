# Local mailbox packaging

`package_mailbox.py` runs an explicit list of repository test files on a clean
checkout at the release head, emits a git-am mailbox, applies it on a detached
base worktree, verifies the resulting tree and source author/committer identities, and
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

Post-test HEAD and nonignored status must remain unchanged. An all-skipped run
is FAIL, even with exit 0; JUnit counts require at least one non-skipped test.
Selectors resolve within the repository. Interpreter argv is an absolute path,
with version and executable SHA256 recorded before execution and hash rechecked
afterward. The effective environment is a recorded allowlist, not the parent
environment: PATH/HOME/locale/TMPDIR plus the named test overrides. Other values,
including pytest plugin options and credentials, are removed. Plugin auto-loading
is disabled. Receipts are local/private by default; paths must be normalized with
explicit disclosure before public delivery.

Applied committer metadata is forced by git-am configuration and is not independent
provenance. The original source author and committer are checked separately.
Ignored files and transient changes restored before the check remain outside the
checkout observation. A timeout still does not isolate descendants: a survivor
can append to selector.log after its recorded hash. The hash covers observed
bytes, not a promise of a permanently frozen log. Trusted checkout only, not a
sandbox; local hooks and test code can have effects.
