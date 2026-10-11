# Row 699 Git Flow: contract

Source text (feature document row, Technical & Engineering): "Git Flow - Manages branches".
Repo row 699 points at `software_practice_685_709.py`, whose `git_flow` method only checks caller-supplied fields.
This package adds an engine that runs real `git` on a repository. Module: `gitflow699.py`. Standard library only; requires the `git` executable.

## Branch model
- `main`, `develop`, `feature/<slug>`, `release/<MAJOR.MINOR.PATCH>`, `hotfix/<MAJOR.MINOR.PATCH>`.
- Tags are annotated `v<version>`.

## API
- `GitFlow(path).init()` creates `main` (with an initial empty commit if the repo is new) and `develop`. Safe to repeat.
- `start(kind, name)` creates the branch. feature/release from `develop`, hotfix from `main`. Refuses: dirty tree, duplicate branch, bad name, a second open release, a release/hotfix version that is not greater than the highest `v` tag or whose tag exists.
- `finish(kind, name)`: feature merges `--no-ff` into `develop`. release/hotfix merge `--no-ff` into `main`, tag, merge the tag back into `develop` (a hotfix goes into the open release branch instead, if one exists), then delete the branch. A conflicting merge is aborted and the branch is kept.
- `status()` lists branches with kind, commits ahead of base, merged flag. `audit()` reports nonconforming names and `main` ahead of `develop` with no open release or hotfix.
- `classify_branch(name)`, `merge_allowed(source_kind, target_kind)`, `clean_git_env()` (drops `AWS_*` and `GIT_*` variables).

## Limits
- Local repositories only. No push, no remotes, no hosting-service rules.
- A release or hotfix finish that fails at a later step (for example the back-merge conflicts) can leave `main` merged and tagged. The error names the failing merge. This is not rolled back.
- A tag check against `main` ancestry is not done; "highest tag" means the highest semver `v` tag in the repository.
- Not wired into any router. Existing `git_flow` method is untouched.

## Qualification (added 2026-10-11, second commit; the first commit's text above is unchanged)
Operations are meant for throwaway/temporary repos only. Being inside the temp directory is NOT treated as proof of that. What the guard does (third commit, 2026-10-11, superseding the sentence from the second commit):
- `GitFlow(path)` resolves the path once (symlinks and `..`) and refuses anything not strictly inside the system temporary directory. All later operations use that resolved path, so retargeting a symlink afterwards does not redirect them.
- `init()` only creates a repository: the target must not exist or must be an empty directory. It writes a marker file inside `.git`. An existing non-empty directory, an existing clone (including a clone of the Atlas checkout placed in temp) or an existing unmarked repo is refused.
- `start`, `finish`, `status`, `audit` and a repeat `init` refuse any repository without that marker, and any repository that has a remote configured.

What it does NOT guarantee: it cannot tell a throwaway repo from a real one by itself. Anyone who can write into a repository's `.git` directory can add the marker to a real repo in temp, and a remote-less marked repo is accepted whatever its history. It does not detect the Atlas repo by name or content, it refuses it because it lacks the marker and is outside temp. It does not stop git operations you run yourself outside this class. Temp location alone is not a safety condition; the marker and no-remote checks are.

Material risks, stated verbatim:
- backmerge failure can leave main merged+TAGGED without transactional rollback
- highest-tag selection is repo-wide not main-ancestry
