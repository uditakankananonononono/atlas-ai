"""[P77|L65] "1. A separate repository." Standalone fixture file-tree structure check, one deliverable only.

Reads a local directory tree and checks each declared project directory for the structure of a repository
of its own: its own .git directory, a README, a manifest of files with sha256 that must match, no file
shared with another project, no path escaping the root. It does not depend on any other module of this
repository. It never creates a repository, never runs git and never touches a network. Linux only.
Not a hostile-filesystem sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

SCOPE = "P77|L65 only"
BOUNDARY = ("Fixture file-tree structure check over caller-declared projects. It does not show that a "
            "repository exists, is hosted, is the project's real source of truth or is separate from "
            "any other repository outside the supplied tree. Manifest matches prove bytes only.")
HEAD_RE = re.compile(rb"^(ref: refs/heads/\S+|[0-9a-f]{40})\n?$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_REQUIRED = ("README.md",)
DEFAULT_MANIFEST = "manifest.json"
MANIFEST_LIMIT = 1024 * 1024
FILE_LIMIT = 10_000_000
MAX_FILES = 10000


class RepoStructureError(ValueError):
    pass


def _rel_parts(rel, what):
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel:
        raise RepoStructureError(f"{what} must be a contained relative path: {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise RepoStructureError(f"{what} must be a contained relative path: {rel!r}")
    return tuple(parts)


def _classify(base: Path, parts):
    """lstat base/parts step by step. Returns (stat_result, None) or (None, 'MISSING'|'UNSAFE_SYMLINK')."""
    cur = base
    st = None
    for p in parts:
        cur = cur / p
        try:
            st = os.lstat(cur)
        except OSError:
            return None, "MISSING"
        if stat.S_ISLNK(st.st_mode):
            return None, "UNSAFE_SYMLINK"
    return st, None


def _lstat(base: Path, parts):
    return _classify(base, parts)[0]


def _read_bounded(path: Path, limit):
    """Read up to limit bytes without following symlinks. Returns bytes, or None if unreadable or longer."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        out = b""
        while len(out) <= limit:
            chunk = os.read(fd, 65536)
            if not chunk:
                return out
            out += chunk
        return None
    except OSError:
        return None
    finally:
        os.close(fd)


def _norm_url(u):
    s = urlsplit(u.strip())
    path = s.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{s.scheme.lower()}://{(s.hostname or '').lower()}{path.rstrip('/')}"


def _valid_url(u):
    if not isinstance(u, str) or not u.strip():
        return False
    try:
        raw = u.strip()
        s = urlsplit(raw)
        # Whitespace anywhere in the authority (urlsplit silently drops tabs and newlines) and an
        # unparseable port (non-numeric or outside 0..65535) make the declared URL invalid.
        authority = raw.partition("://")[2]
        for sep in "/?#":
            authority = authority.split(sep, 1)[0]
        if any(c.isspace() for c in authority):
            return False
        s.port  # raises ValueError for a non-numeric or out-of-range port
        return s.scheme == "https" and bool(s.hostname) and not s.username and not s.password \
            and not s.query and not s.fragment
    except ValueError:
        return False


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
    dirs, ids, parsed = set(), set(), []
    for p in projects:
        if not isinstance(p, dict) or "directory" not in p or "project_id" not in p:
            raise RepoStructureError("each project needs 'project_id' and 'directory'")
        if not isinstance(p["project_id"], str) or not ID_RE.match(p["project_id"]):
            raise RepoStructureError(f"invalid project_id: {p['project_id']!r}")
        parts = _rel_parts(p["directory"], "directory")
        req = p.get("required_files", list(DEFAULT_REQUIRED))
        if not isinstance(req, list):
            raise RepoStructureError("required_files must be a list")
        req_parts = [_rel_parts(r, "required file") for r in req]
        man_parts = _rel_parts(p.get("manifest", DEFAULT_MANIFEST), "manifest")
        if parts in dirs:
            raise RepoStructureError(f"duplicate directory: {p['directory']}")
        if p["project_id"] in ids:
            raise RepoStructureError(f"duplicate project_id: {p['project_id']}")
        dirs.add(parts)
        ids.add(p["project_id"])
        parsed.append((p, parts, req_parts, man_parts))
    return root, parsed


def _parse_manifest(raw):
    """Returns (project_id, [(parts, sha)], error)."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, None, "manifest is not valid JSON"
    if not isinstance(data, dict) or not isinstance(data.get("project_id"), str) or not isinstance(data.get("files"), list):
        return None, None, "manifest must be an object with string project_id and a files list"
    if len(data["files"]) > MAX_FILES:
        return None, None, "manifest lists too many files"
    out, seen = [], set()
    for e in data["files"]:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str) or not isinstance(e.get("sha256"), str):
            return None, None, "each manifest file needs string path and sha256"
        try:
            parts = _rel_parts(e["path"], "manifest path")
        except RepoStructureError:
            return None, None, f"manifest path is not a contained relative path: {e['path']!r}"
        if not SHA_RE.match(e["sha256"]):
            return None, None, f"manifest sha256 is not 64 lowercase hex: {e['path']!r}"
        if parts in seen:
            return None, None, f"manifest lists a path twice: {e['path']!r}"
        seen.add(parts)
        out.append((parts, e["sha256"]))
    return data["project_id"], out, None


def _measure(pdir: Path, parts, want):
    st, why = _classify(pdir, parts)
    if st is None:
        return why, None
    if not stat.S_ISREG(st.st_mode):
        return "NOT_REGULAR_FILE", None
    if st.st_size == 0:
        return "EMPTY_FILE", None
    if st.st_size > FILE_LIMIT:
        return "TOO_LARGE", None
    data = _read_bounded(pdir.joinpath(*parts), FILE_LIMIT)
    if data is None:
        return "UNREADABLE", None
    if hashlib.sha256(data).hexdigest() != want:
        return "HASH_MISMATCH", None
    return "MATCH", st


def check_repo_per_project(root, projects):
    root, parsed = _validate_input(root, projects)
    n = len(parsed)
    findings = [[] for _ in range(n)]
    matched = [0] * n
    remote_recorded = [False] * n
    inodes, urls = {}, {}

    def add(i, code, detail=""):
        findings[i].append({"code": code, "detail": detail})

    def track(i, st):
        inodes.setdefault((st.st_dev, st.st_ino), set()).add(i)

    for i, (p, parts, req_parts, man_parts) in enumerate(parsed):
        for j, (_, _, _, _) in enumerate(parsed):
            other = parsed[j][1]
            if i != j and (other == parts[:len(other)] or parts == other[:len(parts)]):
                add(i, "NESTED_PROJECT_DIRS", "/".join(other))
        dst = _lstat(root, parts)
        if dst is None or not stat.S_ISDIR(dst.st_mode):
            add(i, "DIR_MISSING_OR_UNSAFE", p["directory"])
            continue
        pdir = root.joinpath(*parts)
        declared = p.get("repository")
        declared_ok = declared is not None and _valid_url(declared)
        if declared is not None and not declared_ok:
            add(i, "REPOSITORY_URL_INVALID", "declared repository must be a plain credential-free https URL")
        gst = _lstat(pdir, (".git",))
        if gst is None or not stat.S_ISDIR(gst.st_mode):
            add(i, "NO_OWN_GIT_DIR", "no real .git directory directly inside the project directory")
        else:
            hst = _lstat(pdir, (".git", "HEAD"))
            head = _read_bounded(pdir / ".git" / "HEAD", 4096) if hst is not None and stat.S_ISREG(hst.st_mode) else None
            if head is None or not HEAD_RE.match(head):
                add(i, "GIT_HEAD_INVALID", ".git/HEAD is not a regular file holding refs/heads/<name> or a 40-hex id")
            if hst is not None and stat.S_ISREG(hst.st_mode):
                track(i, hst)
            cst = _lstat(pdir, (".git", "config"))
            if cst is not None and stat.S_ISREG(cst.st_mode):
                track(i, cst)
                url = _remote_url(_read_bounded(pdir / ".git" / "config", 65536))
                if url is not None:
                    remote_recorded[i] = True
                    if declared_ok and _norm_url(url) != _norm_url(declared):
                        add(i, "REMOTE_MISMATCH", ".git/config origin url differs from declared repository")
        for rp_ in req_parts:
            rst = _lstat(pdir, rp_)
            if rst is None or not stat.S_ISREG(rst.st_mode) or rst.st_size == 0:
                add(i, "REQUIRED_FILE_MISSING", "/".join(rp_))
            else:
                track(i, rst)
        mst = _lstat(pdir, man_parts)
        raw = _read_bounded(pdir.joinpath(*man_parts), MANIFEST_LIMIT) if mst is not None and stat.S_ISREG(mst.st_mode) else None
        if raw is None:
            add(i, "MANIFEST_MISSING_OR_INVALID", "manifest missing, unreadable, not a regular file or over 1 MiB")
        else:
            track(i, mst)
            mpid, entries, err = _parse_manifest(raw)
            if err:
                add(i, "MANIFEST_MISSING_OR_INVALID", err)
            else:
                if mpid != p["project_id"]:
                    add(i, "MANIFEST_PROJECT_MISMATCH", f"manifest says {mpid!r}")
                if not entries:
                    add(i, "NO_FILES_LISTED", "manifest lists no files, so nothing ties files to this repository")
                for parts_, want in entries:
                    rel = "/".join(parts_)
                    if parts_[0] == ".git":
                        add(i, "MANIFEST_FILE_INSIDE_GIT_DIR", rel)
                    status, fst = _measure(pdir, parts_, want)
                    if status == "MATCH":
                        matched[i] += 1
                        track(i, fst)
                    else:
                        add(i, "MANIFEST_FILE_NOT_MATCHED", f"{rel}:{status}")
        if declared_ok:
            urls.setdefault(_norm_url(declared), set()).add(i)

    for group in inodes.values():
        if len(group) > 1:
            for i in group:
                add(i, "SHARED_INODE", "a file in this project is the same inode as a file in another project")
    for group in urls.values():
        if len(group) > 1:
            for i in group:
                add(i, "SHARED_REPOSITORY_URL", "declared repository URL equals another project's")

    out = []
    for i, (p, _, _, _) in enumerate(parsed):
        out.append({"directory": p["directory"], "project_id": p["project_id"],
                    "status": "STRUCTURE_FAILED" if findings[i] else "STRUCTURE_CONSISTENT",
                    "findings": findings[i], "remote_recorded": remote_recorded[i],
                    "manifest_files_matched": matched[i]})
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
