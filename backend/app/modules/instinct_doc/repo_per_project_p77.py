"""[P77|L65] "1. A separate repository." Fixture file-tree structure check, one deliverable only.

Consumes the project-deliverable (AT) integration: each project's AT spec is validated and its
artifacts measured by app.core.project_deliverable_contract.check_deliverables, rooted at that
project's own directory. This module adds the repository-structure checks that module does not do.
It reads a local directory tree. It never creates a repository, never runs git and never touches a network.
Linux only (inherits that from the AT integration). Not a hostile-filesystem sandbox.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

SCOPE = "P77|L65 only"
BOUNDARY = ("Fixture file-tree structure check over caller-declared projects. It does not show that a "
            "repository exists, is hosted, is the project's real source of truth or is separate from "
            "any other repository outside the supplied tree. Artifact counts and hashes come from the "
            "AT integration and prove bytes only.")
HEAD_RE = re.compile(rb"^(ref: refs/heads/\S+|[0-9a-f]{40})\n?$")
DEFAULT_REQUIRED = ("README.md",)


class RepoStructureError(ValueError):
    pass


def _at():
    try:
        from app.core import project_deliverable_contract as m
    except ModuleNotFoundError as e:  # integration not on this base
        raise RepoStructureError("AT integration app.core.project_deliverable_contract is not available") from e
    return m


def _rel_parts(rel, what):
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel:
        raise RepoStructureError(f"{what} must be a contained relative path: {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise RepoStructureError(f"{what} must be a contained relative path: {rel!r}")
    return tuple(parts)


def _lstat(base: Path, parts):
    """lstat of base/parts, refusing any symlink component. Returns os.stat_result or None."""
    cur = base
    st = None
    for p in parts:
        cur = cur / p
        try:
            st = os.lstat(cur)
        except OSError:
            return None
        if stat.S_ISLNK(st.st_mode):
            return None
    return st


def _read_small(path: Path, limit=4096):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        return os.read(fd, limit)
    finally:
        os.close(fd)


def _norm_url(u):
    if not isinstance(u, str):
        return None
    s = urlsplit(u.strip())
    path = s.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{s.scheme.lower()}://{(s.hostname or '').lower()}{path.rstrip('/')}"


def _remote_url(config_bytes):
    if config_bytes is None:
        return None
    section = None
    for line in config_bytes.decode("utf-8", "replace").splitlines():
        t = line.strip()
        if t.startswith("["):
            section = t
        elif section == '[remote "origin"]' and t.startswith("url"):
            k, _, v = t.partition("=")
            if k.strip() == "url":
                return v.strip()
    return None


def _validate_input(root, projects):
    root = Path(root)
    try:
        st = os.lstat(root)
    except OSError as e:
        raise RepoStructureError("root must be an existing directory") from e
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise RepoStructureError("root must be a real (non-symlink) directory")
    if not isinstance(projects, list):
        raise RepoStructureError("projects must be a list")
    dirs, ids = set(), set()
    parsed = []
    for p in projects:
        if not isinstance(p, dict) or "directory" not in p or "spec" not in p or not isinstance(p["spec"], dict):
            raise RepoStructureError("each project needs 'directory' and 'spec' (an AT spec object)")
        parts = _rel_parts(p["directory"], "directory")
        req = p.get("required_files", list(DEFAULT_REQUIRED))
        if not isinstance(req, list):
            raise RepoStructureError("required_files must be a list")
        req_parts = [_rel_parts(r, "required file") for r in req]
        if parts in dirs:
            raise RepoStructureError(f"duplicate directory: {p['directory']}")
        dirs.add(parts)
        pid = p["spec"].get("project_id")
        if isinstance(pid, str):
            if pid in ids:
                raise RepoStructureError(f"duplicate project_id: {pid}")
            ids.add(pid)
        parsed.append((p, parts, req_parts))
    return root, parsed


def check_repo_per_project(root, projects):
    at = _at()
    root, parsed = _validate_input(root, projects)
    n = len(parsed)
    findings = [[] for _ in range(n)]
    reports = [None] * n
    remote_recorded = [False] * n
    inodes = {}  # (dev, ino) -> set of project indexes
    urls = {}

    def add(i, code, detail=""):
        findings[i].append({"code": code, "detail": detail})

    def track(i, st):
        inodes.setdefault((st.st_dev, st.st_ino), set()).add(i)

    for i, (p, parts, req_parts) in enumerate(parsed):
        for j, (_, other, _) in enumerate(parsed):
            if i != j and (other == parts[:len(other)] or parts == other[:len(parts)]):
                add(i, "NESTED_PROJECT_DIRS", "/".join(other))
        dst = _lstat(root, parts)
        if dst is None or not stat.S_ISDIR(dst.st_mode):
            add(i, "DIR_MISSING_OR_UNSAFE", p["directory"])
            continue
        pdir = root.joinpath(*parts)
        gst = _lstat(pdir, (".git",))
        if gst is None or not stat.S_ISDIR(gst.st_mode):
            add(i, "NO_OWN_GIT_DIR", "no real .git directory directly inside the project directory")
        else:
            hst = _lstat(pdir, (".git", "HEAD"))
            head = _read_small(pdir / ".git" / "HEAD") if hst is not None and stat.S_ISREG(hst.st_mode) else None
            if head is None or not HEAD_RE.match(head):
                add(i, "GIT_HEAD_INVALID", ".git/HEAD is not a regular file holding refs/heads/<name> or a 40-hex id")
            if hst is not None and stat.S_ISREG(hst.st_mode):
                track(i, hst)
            cst = _lstat(pdir, (".git", "config"))
            if cst is not None and stat.S_ISREG(cst.st_mode):
                track(i, cst)
                url = _remote_url(_read_small(pdir / ".git" / "config", 65536))
                if url is not None:
                    remote_recorded[i] = True
                    declared = _norm_url(p["spec"].get("repository"))
                    if _norm_url(url) != declared:
                        add(i, "REMOTE_MISMATCH", f".git/config origin url differs from declared repository")
        for rp_ in req_parts:
            rst = _lstat(pdir, rp_)
            if rst is None or not stat.S_ISREG(rst.st_mode) or rst.st_size == 0:
                add(i, "REQUIRED_FILE_MISSING", "/".join(rp_))
            else:
                track(i, rst)
        try:
            rep = at.check_deliverables(str(pdir), p["spec"])
        except at.ContractError as e:
            add(i, "AT_SPEC_INVALID", str(e))
            continue
        reports[i] = rep
        if not rep["artifacts"]:
            add(i, "NO_ARTIFACTS_DECLARED", "AT spec declares no artifacts, so nothing ties files to this repository")
        for a in rep["artifacts"]:
            if a["path"] == ".git" or a["path"].startswith(".git/"):
                add(i, "ARTIFACT_INSIDE_GIT_DIR", a["id"])
            if a["status"] != "FILE_HASH_MATCH":
                add(i, "ARTIFACT_NOT_MATCHED", f"{a['id']}:{a['status']}")
            else:
                ast = _lstat(pdir, tuple(a["path"].split("/")))
                if ast is not None:
                    track(i, ast)
        u = _norm_url(p["spec"].get("repository"))
        if u:
            urls.setdefault(u, set()).add(i)

    for group in inodes.values():
        if len(group) > 1:
            for i in group:
                add(i, "SHARED_INODE", "a file in this project is the same inode as a file in another project")
    for group in urls.values():
        if len(group) > 1:
            for i in group:
                add(i, "SHARED_REPOSITORY_URL", "declared repository URL equals another project's")

    out = []
    for i, (p, parts, _) in enumerate(parsed):
        out.append({"directory": p["directory"], "project_id": p["spec"].get("project_id"),
                    "status": "STRUCTURE_FAILED" if findings[i] else "STRUCTURE_CONSISTENT",
                    "findings": findings[i], "remote_recorded": remote_recorded[i], "at_report": reports[i]})
    ok = sum(1 for x in out if x["status"] == "STRUCTURE_CONSISTENT")
    return {"scope": SCOPE, "doc_line_fulfilled": False, "separate_repository_proven": "UNVERIFIED",
            "boundary": BOUNDARY,
            "counts": {"counts_what": "project entries supplied to check_repo_per_project",
                       "total_projects": n, "consistent": ok, "failed": n - ok},
            "projects": out}


def render_markdown(report):
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    lines = [report["boundary"], "", "| Project | Directory | Status | Findings |", "|---|---|---|---|"]
    for p in report["projects"]:
        f = "; ".join(x["code"] + (f" ({esc(x['detail'])})" if x["detail"] else "") for x in p["findings"]) or "none"
        lines.append(f"| {esc(p['project_id'])} | {esc(p['directory'])} | {p['status']} | {f} |")
    c = report["counts"]
    lines += ["", f"{c['counts_what']}: {c['total_projects']}; consistent={c['consistent']}, failed={c['failed']}.",
              "This table does not show the line P77|L65 is fulfilled."]
    return "\n".join(lines) + "\n"
