"""Row 699 Git Flow: manages branches by running real git against a repository.

Stdlib only. Calls the `git` executable; nothing is simulated. Branch model:
main, develop, feature/*, release/<semver>, hotfix/<semver>.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

MAIN = "main"
DEVELOP = "develop"
KINDS = ("feature", "release", "hotfix")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_PREFIX = "v"
MARKER_NAME = "gitflow699-throwaway"

# (source kind, target branch kind) pairs git flow permits.
_MERGES = {
    ("feature", "develop"),
    ("release", "main"), ("release", "develop"),
    ("hotfix", "main"), ("hotfix", "develop"), ("hotfix", "release"),
}


class GitFlowError(Exception):
    pass


def clean_git_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("AWS_") and not k.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "gitflow", "GIT_AUTHOR_EMAIL": "gitflow@example.invalid",
        "GIT_COMMITTER_NAME": "gitflow", "GIT_COMMITTER_EMAIL": "gitflow@example.invalid",
        "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def merge_allowed(source_kind: str, target_kind: str) -> bool:
    return (source_kind, target_kind) in _MERGES


def classify_branch(name: str):
    if name == MAIN:
        return ("main", None)
    if name == DEVELOP:
        return ("develop", None)
    for k in KINDS:
        p = k + "/"
        if name.startswith(p) and len(name) > len(p):
            return (k, name[len(p):])
    return ("other", None)


_BAD_NAME = re.compile(r"[\s~^:?*\[\\]|\.\.|@\{|//")


def _valid_slug(name: str) -> bool:
    return bool(name) and "/" not in name and not _BAD_NAME.search(name) and not name.startswith(("-", ".")) \
        and not name.endswith((".", ".lock"))


def _semver_tuple(v: str):
    m = SEMVER.match(v)
    return tuple(int(x) for x in m.groups()) if m else None


class GitFlow:
    def __init__(self, path):
        # Guard: only throwaway repositories strictly inside the temp directory.
        p = Path(path).resolve()
        root = Path(tempfile.gettempdir()).resolve()
        if root not in p.parents:
            raise GitFlowError(f"refusing {p}: GitFlow only operates on repositories inside the temporary directory {root}")
        self.path = p  # resolved once; every operation uses this, never the caller's path

    # -- git plumbing -------------------------------------------------
    def _git(self, *args, check=True):
        r = subprocess.run(["git", "-C", str(self.path), *args], capture_output=True, text=True,
                           env=clean_git_env())
        if check and r.returncode != 0:
            raise GitFlowError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
        return r

    def _out(self, *args):
        return self._git(*args).stdout.strip()

    def _branches(self):
        out = self._out("for-each-ref", "--format=%(refname:short)", "refs/heads")
        return out.split() if out else []

    def _current(self):
        return self._out("branch", "--show-current")

    def _tags(self):
        out = self._out("tag", "--list", f"{TAG_PREFIX}*")
        return out.split() if out else []

    def _require_clean(self):
        if self._out("status", "--porcelain"):
            raise GitFlowError("working tree is not clean")

    def _is_ancestor(self, a, b):
        return self._git("merge-base", "--is-ancestor", a, b, check=False).returncode == 0

    def _open(self, kind):
        return [b for b in self._branches() if classify_branch(b)[0] == kind]

    def _highest_tag(self, ref=None):
        args = ["tag", "--list", f"{TAG_PREFIX}*"]
        if ref:
            args += ["--merged", ref]
        out = self._out(*args)
        vals = [t for t in out.split() if _semver_tuple(t[len(TAG_PREFIX):])]
        return max(vals, key=lambda t: _semver_tuple(t[len(TAG_PREFIX):]), default=None)

    # -- operations ---------------------------------------------------
    def _marker(self):
        return self.path / ".git" / MARKER_NAME

    def _require_owned(self):
        if not self._marker().is_file():
            raise GitFlowError(f"{self.path} was not created by this module (no throwaway marker); refusing")
        if self._out("remote"):
            raise GitFlowError("repository has a remote configured; throwaway repositories have none; refusing")

    def init(self):
        if self._marker().is_file():
            self._require_owned()
        else:
            if self.path.exists() and (not self.path.is_dir() or any(self.path.iterdir())):
                raise GitFlowError(f"{self.path} is not empty and was not created by this module; refusing")
            self.path.mkdir(parents=True, exist_ok=True)
            self._git("init", "-q", "-b", MAIN)
            self._marker().write_text(secrets.token_hex(16) + "\n")
        brs = self._branches()
        if MAIN not in brs:
            if brs:
                raise GitFlowError("repository has branches but no 'main'")
            self._git("commit", "-q", "--allow-empty", "-m", "initial commit")
        if DEVELOP not in self._branches():
            self._git("branch", DEVELOP, MAIN)
        if self._current() == MAIN:
            self._git("checkout", "-q", DEVELOP)

    def _check_name(self, kind, name):
        if kind not in KINDS:
            raise GitFlowError(f"unknown kind: {kind}")
        if kind == "feature":
            if not _valid_slug(name):
                raise GitFlowError(f"invalid feature name: {name!r}")
        elif not SEMVER.match(name or ""):
            raise GitFlowError(f"{kind} name must be MAJOR.MINOR.PATCH semver: {name!r}")

    def start(self, kind, name):
        self._require_owned()
        self._check_name(kind, name)
        branch = f"{kind}/{name}"
        self._require_clean()
        if branch in self._branches():
            raise GitFlowError(f"{branch} already exists")
        if DEVELOP not in self._branches() or MAIN not in self._branches():
            raise GitFlowError("repository is not initialised for git flow")
        if kind in ("release", "hotfix"):
            if f"{TAG_PREFIX}{name}" in self._tags():
                raise GitFlowError(f"tag {TAG_PREFIX}{name} already exists")
            top = self._highest_tag()
            if top and _semver_tuple(name) <= _semver_tuple(top[len(TAG_PREFIX):]):
                raise GitFlowError(f"{kind} version {name} must be greater than latest tag {top}")
        if kind == "release":
            if self._open("release"):
                raise GitFlowError("a release branch is already open: " + ", ".join(self._open("release")))
        base = DEVELOP if kind in ("feature", "release") else MAIN
        self._git("checkout", "-q", "-b", branch, base)
        return branch

    def _merge(self, source, target, message):
        self._git("checkout", "-q", target)
        r = self._git("merge", "--no-ff", "-m", message, source, check=False)
        if r.returncode != 0:
            self._git("merge", "--abort", check=False)
            raise GitFlowError(f"merge of {source} into {target} conflicted and was aborted")

    def finish(self, kind, name):
        self._require_owned()
        self._check_name(kind, name)
        branch = f"{kind}/{name}"
        if branch not in self._branches():
            raise GitFlowError(f"{branch} does not exist")
        self._require_clean()
        if kind == "feature":
            self._merge(branch, DEVELOP, f"Merge {branch} into {DEVELOP}")
            self._git("branch", "-d", branch)
            return {"merged_into": [DEVELOP], "tag": None}
        tag = f"{TAG_PREFIX}{name}"
        if tag in self._tags():
            raise GitFlowError(f"tag {tag} already exists")
        targets = [MAIN]
        self._merge(branch, MAIN, f"Merge {branch} into {MAIN}")
        self._git("tag", "-a", tag, "-m", f"{kind} {name}")
        other_release = [b for b in self._open("release") if b != branch]
        back = other_release[0] if kind == "hotfix" and other_release else DEVELOP
        self._merge(tag, back, f"Merge {tag} back into {back}")
        targets.append(back)
        self._git("branch", "-d", branch)
        return {"merged_into": targets, "tag": tag}

    def status(self):
        self._require_owned()
        cur = self._current()
        out = []
        for b in self._branches():
            kind, name = classify_branch(b)
            base = {"feature": DEVELOP, "release": DEVELOP, "hotfix": MAIN}.get(kind)
            row = {"name": b, "kind": kind, "current": b == cur, "base": base,
                   "ahead_of_base": None, "merged": None}
            if base and base in self._branches():
                row["ahead_of_base"] = int(self._out("rev-list", "--count", f"{base}..{b}"))
                row["merged"] = self._is_ancestor(b, base)
            out.append(row)
        return out

    def audit(self):
        self._require_owned()
        findings = []
        for b in self._branches():
            if classify_branch(b)[0] == "other":
                findings.append({"name": b, "problem": "nonconforming_branch_name"})
        brs = self._branches()
        if MAIN in brs and DEVELOP in brs and not self._is_ancestor(MAIN, DEVELOP) \
                and not self._open("release") and not self._open("hotfix"):
            findings.append({"name": MAIN, "problem": "main_ahead_of_develop_without_release"})
        return findings
