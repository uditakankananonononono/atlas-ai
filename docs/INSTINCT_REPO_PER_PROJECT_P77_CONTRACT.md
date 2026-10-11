# [P77|L65] "1. A separate repository." Structure check: contract

Doc text (data): `[P76|L64] For every project, task, module, tool, or research project, produce:` then `[P77|L65] 1. A separate repository.`
This covers deliverable 1 only. Deliverables 2 to 15 are not covered. It does not claim the line is fulfilled.

Module: `backend/app/modules/instinct_doc/repo_per_project_p77.py`. Tests: `tests/modules/test_repo_per_project_p77.py`. No `__init__.py` is added in `instinct_doc/` (namespace directory).

## Correction note (2026-10-11, second commit)
The first commit (7610f585) called another module's checker (the project-deliverable "AT" integration, `check_deliverables`) and could load it from an environment path. That was a dependency deviation: that module is not audited or landed, and its behavior is not settled. This commit removes the import, the call and the environment fallback. The module is now standalone and uses its own manifest check. Comparison with the AT integration is deferred until it is repaired, audited and landed. The first commit stays in the history unchanged.

## What it does
`check_repo_per_project(root, projects)` reads a local directory tree. Each entry: `{"project_id": "<[a-z0-9_-]+>", "directory": "<relative dir>", "repository": "<optional declared https URL>", "required_files": [optional, default README.md], "manifest": "<optional, default manifest.json>"}`. For each project it reports STRUCTURE_CONSISTENT or STRUCTURE_FAILED with finding codes:
- DIR_MISSING_OR_UNSAFE (missing, not a directory, or a symlink anywhere on the path), NESTED_PROJECT_DIRS (one project directory inside another; both flagged).
- NO_OWN_GIT_DIR (a real `.git` directory must sit directly in the project directory; a parent's `.git`, a symlink or a `.git` file does not count), GIT_HEAD_INVALID (`.git/HEAD` must be a regular file holding `ref: refs/heads/<name>` or a 40-hex id).
- REQUIRED_FILE_MISSING (non-empty regular files, default `README.md`).
- MANIFEST_MISSING_OR_INVALID, MANIFEST_PROJECT_MISMATCH, NO_FILES_LISTED, MANIFEST_FILE_NOT_MATCHED, MANIFEST_FILE_INSIDE_GIT_DIR. The manifest is a JSON object `{"project_id": ..., "files": [{"path": <relative>, "sha256": <64 lowercase hex>}]}` (at most 1 MiB, 10000 files). Every listed file must be a contained, non-empty regular file inside the project directory (no symlink on its path, at most 10 MB) whose sha256 matches. Per-file status in the finding detail: MISSING, UNSAFE_SYMLINK, NOT_REGULAR_FILE, EMPTY_FILE, TOO_LARGE, UNREADABLE, HASH_MISMATCH.
- REPOSITORY_URL_INVALID (declared URL must be a plain https URL without credentials, query or fragment), SHARED_REPOSITORY_URL (two projects declare the same URL after trailing slash and `.git` normalization), REMOTE_MISMATCH (only when `.git/config` has an `origin` url that differs from the declared one; no remote recorded is reported as `remote_recorded: false`, not a failure).
- SHARED_INODE (a file, `.git/HEAD`, `.git/config`, README, manifest or listed file is the same inode as one in another project).
Malformed input (bad paths, duplicate directories or project ids, bad root, bad entry shape) raises `RepoStructureError`.

## Gaps and limits, stated plainly
- A passing result does not show that a repository exists, is hosted, is the project's real source of truth, or is separate from any repository outside the supplied tree. `separate_repository_proven` is always `UNVERIFIED` and `doc_line_fulfilled` is always `False`.
- The `.git` check is structural (directory plus HEAD form). It does not run git or verify objects or history.
- The manifest is written by the caller; a match shows listed bytes equal listed hashes, nothing about their meaning.
- Whether something counts as a "project" is the caller's declaration.
- No repository is created, no network access, no writes into the checked tree.
- Linux only. Not a hostile-filesystem sandbox: paths are checked with lstat step by step, and a concurrent change between checks is not detected.
- Not run: the repo conftest, mounted auth/tenant tests, the repo-wide suite, platforms other than Linux.
- Mutation survivors judged equivalent by the author (not proven by a test; the peer audits independently): `.lower()` on the URL host (urlsplit already lowercases it), root symlink check (lstat already reports a symlink as non-directory), absolute-path prefix check (a leading `/` is also caught by the empty-component check), HEAD-must-be-regular-file guard (the bounded reader already returns nothing for a directory).
