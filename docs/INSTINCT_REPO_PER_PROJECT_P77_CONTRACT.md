# [P77|L65] "1. A separate repository." Structure check: contract

Doc text (data): `[P76|L64] For every project, task, module, tool, or research project, produce:` then `[P77|L65] 1. A separate repository.`
This covers deliverable 1 only. Deliverables 2 to 15 are not covered. It does not claim the line is fulfilled.

Module: `backend/app/modules/instinct_doc/repo_per_project_p77.py`. Tests: `tests/modules/test_repo_per_project_p77.py`. No `__init__.py` is added in `instinct_doc/` (it is a namespace directory).

## What it does
`check_repo_per_project(root, projects)` reads a local directory tree. Each project entry is `{"directory": "<relative dir>", "spec": <AT spec>, "required_files": [optional]}`. For each project it reports STRUCTURE_CONSISTENT or STRUCTURE_FAILED with finding codes:
- DIR_MISSING_OR_UNSAFE (missing, not a directory, or any symlink on the path), NESTED_PROJECT_DIRS (one project directory inside another; both flagged).
- NO_OWN_GIT_DIR (a real `.git` directory must sit directly in the project directory; a parent's `.git`, a symlink or a `.git` file does not count), GIT_HEAD_INVALID (`.git/HEAD` must be a regular file holding `ref: refs/heads/<name>` or a 40-hex id).
- REQUIRED_FILE_MISSING (default `README.md`, non-empty regular file).
- REMOTE_MISMATCH (only when `.git/config` has an `origin` url that differs from the AT spec's declared repository; no remote recorded is reported as `remote_recorded: false`, not a failure), SHARED_REPOSITORY_URL (two projects declare the same URL after trailing slash and `.git` normalization).
- SHARED_INODE (a file, `.git/HEAD`, `.git/config`, README or artifact is the same inode as one in another project).
- AT_SPEC_INVALID, NO_ARTIFACTS_DECLARED, ARTIFACT_NOT_MATCHED, ARTIFACT_INSIDE_GIT_DIR.
Malformed input (bad paths, duplicate directories or project ids, bad root) raises `RepoStructureError`.

## How it uses the AT integration
Each spec is validated and its artifacts measured by `app.core.project_deliverable_contract.check_deliverables`, with the project's own directory as root, so artifacts must exist inside that project's repository tree. The AT report is returned unchanged under `at_report`. This module does not edit or copy that file.

## Not on this base
The AT integration (peer commit 7b7944db, supplied as a bundle) is not in main 1776396f. The tests import `app.core.project_deliverable_contract` and, if it is absent, load it from the file named by `P77_AT_CONTRACT_PATH`. Without either, the tests fail by design. The module raises `RepoStructureError` if that module cannot be imported. Results below were produced against a checkout of 7b7944db.

## Gaps and limits, stated plainly
- A passing result does not show that a repository exists, is hosted, is the project's real source of truth, or is separate from any repository outside the supplied tree. `separate_repository_proven` is always `UNVERIFIED` and `doc_line_fulfilled` is always `False`.
- The `.git` check is structural (directory plus HEAD form). It does not run git or verify objects or history.
- Whether something counts as a "project" is the caller's declaration.
- No repository is created, no network access, no writes into the checked tree.
- Linux only. Not a hostile-filesystem sandbox: paths are checked with lstat step by step, and a concurrent change between checks is not detected.
- Not run: the repo conftest, mounted auth/tenant tests, the repo-wide suite, platforms other than Linux.
- Mutation survivors judged equivalent (not proven by a test): `.lower()` on the URL host (urlsplit already lowercases it), root symlink check (lstat already reports a symlink as non-directory), absolute-path prefix check (a leading `/` is also caught by the empty-component check).
