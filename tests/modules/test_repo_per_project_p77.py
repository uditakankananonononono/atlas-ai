"""P77|L65 "A separate repository": standalone structure check over fixture file trees (real temp dirs)."""
import hashlib
import json
import os
import pathlib

import pytest

from app.modules.instinct_doc import repo_per_project_p77 as rp

URL = "https://example.test/{}"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def make_repo(root, name, files=None, git=True, head=b"ref: refs/heads/main\n", remote=None,
              readme=True, manifest="auto", pid=None):
    d = pathlib.Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    if git:
        (d / ".git").mkdir()
        (d / ".git" / "HEAD").write_bytes(head)
        cfg = "[core]\n\trepositoryformatversion = 0\n"
        if remote:
            cfg += f'[remote "origin"]\n\turl = {remote}\n'
        (d / ".git" / "config").write_text(cfg)
    if readme:
        (d / "README.md").write_text(f"# {name}\n")
    for rel, data in (files or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(data)
    if manifest == "auto":
        manifest = {"project_id": pid or name,
                    "files": [{"path": p, "sha256": sha(b)} for p, b in (files or {}).items()]}
    if manifest is not None:
        (d / "manifest.json").write_text(manifest if isinstance(manifest, str) else json.dumps(manifest))
    return d


def proj(root, name, files=None, url=None, repo=None, **extra):
    files = files if files is not None else {"src/main.py": b"print(1)\n"}
    make_repo(root, name, files, **(repo or {}))
    return {"project_id": name, "directory": name, "repository": url or URL.format(name), **extra}


def codes(report, i=0):
    return {f["code"] for f in report["projects"][i]["findings"]}


def test_module_does_not_depend_on_other_integrations():
    src = pathlib.Path(rp.__file__).read_text()
    for banned in ("project_deliverable_contract", "P77_AT_CONTRACT_PATH", "check_deliverables", "app.core"):
        assert banned not in src


def test_two_separate_consistent_repos(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha"), proj(tmp_path, "beta", {"x.py": b"x\n"})])
    assert [p["status"] for p in r["projects"]] == ["STRUCTURE_CONSISTENT"] * 2
    assert r["counts"]["consistent"] == 2 and r["counts"]["failed"] == 0 and r["counts"]["total_projects"] == 2
    assert r["projects"][0]["manifest_files_matched"] == 1


def test_report_makes_no_overclaim(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")])
    assert r["doc_line_fulfilled"] is False
    assert r["separate_repository_proven"] == "UNVERIFIED"
    assert r["scope"] == "P77|L65 only"
    assert "fixture" in r["boundary"].lower()


def test_missing_git_dir(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"git": False})])
    assert "NO_OWN_GIT_DIR" in codes(r) and r["projects"][0]["status"] == "STRUCTURE_FAILED"


def test_parent_git_does_not_count(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    assert "NO_OWN_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"git": False})]))


def test_git_as_symlink_rejected(tmp_path):
    p = proj(tmp_path, "alpha", repo={"git": False})
    real = tmp_path / "elsewhere_git"
    real.mkdir()
    (real / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (tmp_path / "alpha" / ".git").symlink_to(real)
    assert "NO_OWN_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_git_as_file_rejected(tmp_path):
    p = proj(tmp_path, "alpha", repo={"git": False})
    (tmp_path / "alpha" / ".git").write_text("gitdir: ../shared\n")
    assert "NO_OWN_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [p]))


@pytest.mark.parametrize("head", [b"", b"garbage\n", b"ref: \n", b"abc\n"])
def test_bad_head_rejected(tmp_path, head):
    assert "GIT_HEAD_INVALID" in codes(rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"head": head})]))


@pytest.mark.parametrize("head", [b"ref: refs/heads/main\n", b"0123456789abcdef0123456789abcdef01234567\n"])
def test_valid_head_forms(tmp_path, head):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"head": head})])
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_git_head_as_directory_is_invalid_not_a_crash(tmp_path):
    p = proj(tmp_path, "alpha")
    os.remove(tmp_path / "alpha" / ".git" / "HEAD")
    (tmp_path / "alpha" / ".git" / "HEAD").mkdir()
    assert "GIT_HEAD_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_readme_required_nonempty(tmp_path):
    p = proj(tmp_path, "alpha", repo={"readme": False})
    assert "REQUIRED_FILE_MISSING" in codes(rp.check_repo_per_project(tmp_path, [p]))
    (tmp_path / "alpha" / "README.md").write_text("")
    assert "REQUIRED_FILE_MISSING" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_custom_required_files(tmp_path):
    p = proj(tmp_path, "alpha", required_files=["README.md", "LICENSE"])
    assert "REQUIRED_FILE_MISSING" in codes(rp.check_repo_per_project(tmp_path, [p]))
    (tmp_path / "alpha" / "LICENSE").write_text("x")
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_required_file_path_escape_rejected(tmp_path):
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", required_files=["../README.md"])])


def test_manifest_missing_invalid_json_or_wrong_shape(tmp_path):
    for i, m in enumerate([None, "{not json", "[]", json.dumps({"project_id": "m0"}), json.dumps({"project_id": "m1", "files": "x"}),
                           json.dumps({"project_id": "m2", "files": [{"path": "a"}]})]):
        name = f"m{i}"
        make_repo(tmp_path, name, {"a": b"a"}, manifest=m)
        r = rp.check_repo_per_project(tmp_path, [{"project_id": name, "directory": name, "repository": URL.format(name)}])
        assert "MANIFEST_MISSING_OR_INVALID" in codes(r), (i, m)


def test_manifest_project_id_must_match_entry(tmp_path):
    make_repo(tmp_path, "alpha", {"a.py": b"a"}, pid="someone-else")
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha", "repository": URL.format("a")}])
    assert "MANIFEST_PROJECT_MISMATCH" in codes(r)


def test_manifest_must_list_files(tmp_path):
    p = proj(tmp_path, "alpha", {})
    assert "NO_FILES_LISTED" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_manifest_hash_mismatch_and_missing_file(tmp_path):
    p = proj(tmp_path, "alpha", {"a.py": b"a", "b.py": b"b"})
    (tmp_path / "alpha" / "a.py").write_bytes(b"changed")
    os.remove(tmp_path / "alpha" / "b.py")
    r = rp.check_repo_per_project(tmp_path, [p])
    details = {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"}
    assert details == {"a.py:HASH_MISMATCH", "b.py:MISSING"}


def test_manifest_empty_file_and_directory_entry_not_matched(tmp_path):
    p = proj(tmp_path, "alpha", {"e.txt": b"", "sub/f": b"f"})
    (tmp_path / "alpha" / "sub" / "f").unlink()
    (tmp_path / "alpha" / "sub" / "f").mkdir()
    r = rp.check_repo_per_project(tmp_path, [p])
    details = {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"}
    assert details == {"e.txt:EMPTY_FILE", "sub/f:NOT_REGULAR_FILE"}


def test_manifest_symlink_file_not_matched(tmp_path):
    p = proj(tmp_path, "alpha", {"a.py": b"a"})
    (tmp_path / "outside.txt").write_bytes(b"a")
    (tmp_path / "alpha" / "a.py").unlink()
    (tmp_path / "alpha" / "a.py").symlink_to(tmp_path / "outside.txt")
    r = rp.check_repo_per_project(tmp_path, [p])
    details = {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"}
    assert details == {"a.py:UNSAFE_SYMLINK"}


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../x", "a//b", "", "./a", "a\\b"])
def test_manifest_path_escape_rejected(tmp_path, bad):
    make_repo(tmp_path, "alpha", {"a": b"a"}, manifest={"project_id": "alpha", "files": [{"path": bad, "sha256": sha(b"a")}]})
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha", "repository": URL.format("a")}])
    assert "MANIFEST_MISSING_OR_INVALID" in codes(r)


def test_manifest_bad_sha_rejected(tmp_path):
    make_repo(tmp_path, "alpha", {"a": b"a"}, manifest={"project_id": "alpha", "files": [{"path": "a", "sha256": "ABC"}]})
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha", "repository": URL.format("a")}])
    assert "MANIFEST_MISSING_OR_INVALID" in codes(r)


def test_manifest_duplicate_paths_rejected(tmp_path):
    e = {"path": "a", "sha256": sha(b"a")}
    make_repo(tmp_path, "alpha", {"a": b"a"}, manifest={"project_id": "alpha", "files": [e, e]})
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha", "repository": URL.format("a")}])
    assert "MANIFEST_MISSING_OR_INVALID" in codes(r)


def test_manifest_file_inside_git_dir_flagged(tmp_path):
    p = proj(tmp_path, "alpha", {".git/HEAD": b"ref: refs/heads/main\n"})
    assert "MANIFEST_FILE_INSIDE_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_custom_manifest_name(tmp_path):
    p = proj(tmp_path, "alpha", manifest="files.json")
    assert "MANIFEST_MISSING_OR_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))
    (tmp_path / "alpha" / "manifest.json").rename(tmp_path / "alpha" / "files.json")
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_manifest_too_large_rejected(tmp_path):
    p = proj(tmp_path, "alpha")
    (tmp_path / "alpha" / "manifest.json").write_text(" " * (2 * 1024 * 1024))
    assert "MANIFEST_MISSING_OR_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_missing_project_dir(tmp_path):
    p = {"project_id": "ghost", "directory": "ghost", "repository": URL.format("ghost")}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_project_dir_symlink_rejected(tmp_path):
    proj(tmp_path, "real")
    (tmp_path / "alpha").symlink_to(tmp_path / "real")
    p = {"project_id": "alpha", "directory": "alpha", "repository": URL.format("alpha")}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_symlinked_intermediate_component_rejected(tmp_path):
    real = tmp_path / "real_parent"
    real.mkdir()
    make_repo(real, "inner", {"x.py": b"x\n"}, pid="inner")
    (tmp_path / "linked").symlink_to(real)
    p = {"project_id": "inner", "directory": "linked/inner", "repository": URL.format("inner")}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


@pytest.mark.parametrize("d", ["..", "../x", "/abs", "a/../b", ".", "", "a//b", "a\\b"])
def test_directory_must_be_contained_relative(tmp_path, d):
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": d, "repository": URL.format("a")}])


def test_nested_project_dirs_flagged_on_both(tmp_path):
    outer = proj(tmp_path, "outer")
    make_repo(tmp_path / "outer", "inner", {"i.py": b"i\n"}, pid="inner")
    inner = {"project_id": "inner", "directory": "outer/inner", "repository": URL.format("inner")}
    r = rp.check_repo_per_project(tmp_path, [outer, inner])
    assert "NESTED_PROJECT_DIRS" in codes(r, 0) and "NESTED_PROJECT_DIRS" in codes(r, 1)


def test_duplicate_directory_or_project_id_rejected(tmp_path):
    a = proj(tmp_path, "alpha")
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [a, a])
    b = proj(tmp_path, "beta")
    b["project_id"] = "alpha"
    with pytest.raises(rp.RepoStructureError, match="duplicate project_id"):
        rp.check_repo_per_project(tmp_path, [a, b])
    c = dict(a, project_id="other")
    with pytest.raises(rp.RepoStructureError, match="duplicate directory"):
        rp.check_repo_per_project(tmp_path, [a, c])


def test_shared_declared_repository_url(tmp_path):
    a = proj(tmp_path, "alpha", url="https://example.test/shared")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://example.test/shared")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_REPOSITORY_URL" in codes(r, 0) and "SHARED_REPOSITORY_URL" in codes(r, 1)


def test_url_comparison_ignores_trailing_slash_and_dot_git(tmp_path):
    a = proj(tmp_path, "alpha", url="https://Example.test/shared.git")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://example.test/shared/")
    assert "SHARED_REPOSITORY_URL" in codes(rp.check_repo_per_project(tmp_path, [a, b]), 0)


@pytest.mark.parametrize("bad", ["http://example.test/x", "ftp://x/y", "https://user:pw@example.test/x", "https://example.test/x?q=1", "not a url", 5])
def test_declared_repository_url_must_be_plain_https(tmp_path, bad):
    p = proj(tmp_path, "alpha", url="https://example.test/ok")
    p["repository"] = bad
    assert "REPOSITORY_URL_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_repository_url_is_optional(tmp_path):
    p = proj(tmp_path, "alpha")
    del p["repository"]
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_remote_in_git_config_must_match_declared(tmp_path):
    ok = proj(tmp_path, "alpha", repo={"remote": URL.format("alpha")})
    bad = proj(tmp_path, "beta", {"x.py": b"x\n"}, repo={"remote": "https://example.test/other"})
    r = rp.check_repo_per_project(tmp_path, [ok, bad])
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT" and r["projects"][0]["remote_recorded"] is True
    assert "REMOTE_MISMATCH" in codes(r, 1)


def test_no_remote_recorded_is_reported_not_failed(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")])
    assert r["projects"][0]["remote_recorded"] is False and r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_hardlink_shared_between_projects(tmp_path):
    a = proj(tmp_path, "alpha")
    b = proj(tmp_path, "beta", {"src/main.py": b"print(1)\n"})
    os.remove(tmp_path / "beta" / "src" / "main.py")
    os.link(tmp_path / "alpha" / "src" / "main.py", tmp_path / "beta" / "src" / "main.py")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_INODE" in codes(r, 0) and "SHARED_INODE" in codes(r, 1)


def test_hardlinked_git_head_between_projects(tmp_path):
    a = proj(tmp_path, "alpha")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"})
    os.remove(tmp_path / "beta" / ".git" / "HEAD")
    os.link(tmp_path / "alpha" / ".git" / "HEAD", tmp_path / "beta" / ".git" / "HEAD")
    assert "SHARED_INODE" in codes(rp.check_repo_per_project(tmp_path, [a, b]), 0)


def test_hardlinked_readme_and_manifest_between_projects(tmp_path):
    a = proj(tmp_path, "alpha", {})
    b = proj(tmp_path, "beta", {})
    os.remove(tmp_path / "beta" / "README.md")
    os.link(tmp_path / "alpha" / "README.md", tmp_path / "beta" / "README.md")
    assert "SHARED_INODE" in codes(rp.check_repo_per_project(tmp_path, [a, b]), 1)


def test_same_content_different_inode_is_not_shared(tmp_path):
    a = proj(tmp_path, "alpha", {"same.py": b"same\n"})
    b = proj(tmp_path, "beta", {"same.py": b"same\n"})
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert all(p["status"] == "STRUCTURE_CONSISTENT" for p in r["projects"])


def test_input_shape_errors(tmp_path):
    for bad in (None, {}, [{}], [{"directory": "a"}], [{"project_id": "a"}], [{"project_id": "a", "directory": 3}],
                [{"project_id": "", "directory": "a"}], [{"project_id": "A B", "directory": "a"}],
                [{"project_id": "a", "directory": "a", "manifest": "../m.json"}],
                [{"project_id": "a", "directory": "a", "required_files": "README.md"}]):
        with pytest.raises(rp.RepoStructureError):
            rp.check_repo_per_project(tmp_path, bad)


def test_root_must_be_real_directory(tmp_path):
    f = tmp_path / "f"
    f.write_text("x")
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(f, [])
    link = tmp_path / "lnk"
    link.symlink_to(tmp_path)
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(link, [])


def test_counts_name_what_they_count_and_sum(tmp_path):
    good = proj(tmp_path, "alpha")
    bad = proj(tmp_path, "beta", {"x.py": b"x\n"}, repo={"git": False})
    c = rp.check_repo_per_project(tmp_path, [good, bad])["counts"]
    assert c["counts_what"] == "project entries supplied to check_repo_per_project"
    assert c["consistent"] + c["failed"] == c["total_projects"] == 2


def test_check_does_not_write_into_root(tmp_path):
    p = proj(tmp_path, "alpha")
    snap = lambda: sorted(str(x.relative_to(tmp_path)) + str(x.stat().st_mtime_ns) for x in tmp_path.rglob("*"))
    before = snap()
    rp.check_repo_per_project(tmp_path, [p])
    assert before == snap()


def test_markdown_render_lists_every_project_and_codes(tmp_path):
    good = proj(tmp_path, "alpha")
    bad = proj(tmp_path, "beta", {"x.py": b"x\n"}, repo={"git": False})
    md = rp.render_markdown(rp.check_repo_per_project(tmp_path, [good, bad]))
    assert "alpha" in md and "beta" in md and "NO_OWN_GIT_DIR" in md and "STRUCTURE_CONSISTENT" in md


def test_markdown_ends_with_non_fulfilment_line(tmp_path):
    md = rp.render_markdown(rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")]))
    assert md.rstrip().splitlines()[-1] == "This table does not show the line P77|L65 is fulfilled."


def test_valid_manifest_over_one_mib_is_rejected_and_one_under_is_accepted(tmp_path):
    p = proj(tmp_path, "alpha")
    body = (tmp_path / "alpha" / "manifest.json").read_text()
    (tmp_path / "alpha" / "manifest.json").write_text(body + " " * (1024 * 1024 + 10))
    assert "MANIFEST_MISSING_OR_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))
    (tmp_path / "alpha" / "manifest.json").write_text(body + " " * (1024 * 1024 - len(body) - 1))
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


# --- third commit: tests only, pins the peer's surviving mutants and special-file probes ---
def _one(tmp_path, name="alpha", files=None, **kw):
    p = proj(tmp_path, name, files, **kw)
    return p, tmp_path / name


def _cfg(d, text):
    (d / ".git" / "config").write_text(text)


def test_oversized_git_config_is_ignored_not_a_crash(tmp_path):
    p, d = _one(tmp_path)
    _cfg(d, '[remote "origin"]\n\turl = https://example.test/other\n' + "#" + "x" * 70000 + "\n")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert r["projects"][0]["remote_recorded"] is False
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_git_config_at_exact_read_limit_is_still_read(tmp_path):
    p, d = _one(tmp_path)
    head = '[remote "origin"]\n\turl = https://example.test/other\n'
    _cfg(d, head + "#" * (65536 - len(head)))
    assert (d / ".git" / "config").stat().st_size == 65536
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REMOTE_MISMATCH" in codes(r)


def test_manifest_file_count_cap(tmp_path):
    for n, ok in ((10000, True), (10001, False)):
        name = f"cap{n}"
        make_repo(tmp_path, name, {}, manifest={"project_id": name,
                  "files": [{"path": f"f{i}", "sha256": "0" * 64} for i in range(n)]})
        r = rp.check_repo_per_project(tmp_path, [{"project_id": name, "directory": name}])
        details = [f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_MISSING_OR_INVALID"]
        assert bool(details) is (not ok), (n, details)
        if not ok:
            assert "too many" in details[0]


def test_file_size_cap_reports_too_large_and_boundary_matches(tmp_path):
    limit = rp.FILE_LIMIT
    big = tmp_path / "big.bin"
    with open(big, "wb") as f:
        f.truncate(limit + 1)
    make_repo(tmp_path, "alpha", {}, manifest={"project_id": "alpha", "files": [{"path": "big.bin", "sha256": "0" * 64}]})
    os.rename(big, tmp_path / "alpha" / "big.bin")
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha"}])
    assert {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"} == {"big.bin:TOO_LARGE"}
    data = b"\0" * limit
    (tmp_path / "alpha" / "big.bin").write_bytes(data)
    (tmp_path / "alpha" / "manifest.json").write_text(json.dumps(
        {"project_id": "alpha", "files": [{"path": "big.bin", "sha256": sha(data)}]}))
    r = rp.check_repo_per_project(tmp_path, [{"project_id": "alpha", "directory": "alpha"}])
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT" and r["projects"][0]["manifest_files_matched"] == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode 000 files")
def test_unreadable_file_reports_unreadable_not_a_crash(tmp_path):
    p, d = _one(tmp_path, files={"a.py": b"a"})
    os.chmod(d / "a.py", 0)
    try:
        r = rp.check_repo_per_project(tmp_path, [p])
    finally:
        os.chmod(d / "a.py", 0o644)
    assert {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"} == {"a.py:UNREADABLE"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode 000 files")
def test_unreadable_manifest_and_head_are_findings_not_crashes(tmp_path):
    p, d = _one(tmp_path)
    os.chmod(d / "manifest.json", 0)
    os.chmod(d / ".git" / "HEAD", 0)
    try:
        r = rp.check_repo_per_project(tmp_path, [p])
    finally:
        os.chmod(d / "manifest.json", 0o644)
        os.chmod(d / ".git" / "HEAD", 0o644)
    assert {"MANIFEST_MISSING_OR_INVALID", "GIT_HEAD_INVALID"} <= codes(r)


@pytest.mark.parametrize("bad", [("README.md",), {"README.md": 1}, None, 5, "README.md"])
def test_required_files_must_be_a_list(tmp_path, bad):
    p, _ = _one(tmp_path)
    p["required_files"] = bad
    with pytest.raises(rp.RepoStructureError, match="required_files must be a list"):
        rp.check_repo_per_project(tmp_path, [p])


@pytest.mark.parametrize("bad", ["https://[::1", "https://[invalid/x"])
def test_unparseable_declared_url_is_a_finding_not_an_exception(tmp_path, bad):
    p, _ = _one(tmp_path)
    p["repository"] = bad
    assert "REPOSITORY_URL_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_remote_only_read_from_origin_section_and_url_key(tmp_path):
    p, d = _one(tmp_path, url="https://example.test/alpha")
    cases = [
        '[remote "upstream"]\n\turl = https://example.test/other\n',
        '[remote "origin"]\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n',
        '[core]\n\turl = https://example.test/other\n',
        '[remote "origin"]\n\turlfoo = https://example.test/other\n',
        '[remote "origin"]\n\tpushurl = https://example.test/other\n',
    ]
    for text in cases:
        _cfg(d, text)
        r = rp.check_repo_per_project(tmp_path, [p])
        assert r["projects"][0]["remote_recorded"] is False, text
        assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT", text


def test_remote_origin_url_found_after_other_sections(tmp_path):
    p, d = _one(tmp_path, url="https://example.test/alpha")
    _cfg(d, '[core]\n\tbare = false\n[remote "upstream"]\n\turl = https://example.test/zzz\n'
            '[remote "origin"]\n\tfetch = +x\n\turl = https://example.test/alpha\n')
    r = rp.check_repo_per_project(tmp_path, [p])
    assert r["projects"][0]["remote_recorded"] is True and r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_distinct_hosts_with_same_path_are_not_merged(tmp_path):
    a = proj(tmp_path, "alpha", url="https://one.example/team/repo")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://two.example/team/repo")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert all(p["status"] == "STRUCTURE_CONSISTENT" for p in r["projects"])


def test_remote_with_different_host_same_path_is_a_mismatch(tmp_path):
    p, d = _one(tmp_path, url="https://one.example/team/repo")
    _cfg(d, '[remote "origin"]\n\turl = https://two.example/team/repo\n')
    assert "REMOTE_MISMATCH" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_same_host_different_case_is_one_repository(tmp_path):
    a = proj(tmp_path, "alpha", url="https://One.Example/team/repo")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://one.example/team/repo")
    assert "SHARED_REPOSITORY_URL" in codes(rp.check_repo_per_project(tmp_path, [a, b]))


def test_missing_head_and_missing_config_are_findings_not_crashes(tmp_path):
    p, d = _one(tmp_path)
    os.remove(d / ".git" / "HEAD")
    os.remove(d / ".git" / "config")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "GIT_HEAD_INVALID" in codes(r) and r["projects"][0]["remote_recorded"] is False
    assert "NO_OWN_GIT_DIR" not in codes(r)


def test_missing_config_alone_is_not_a_finding(tmp_path):
    p, d = _one(tmp_path)
    os.remove(d / ".git" / "config")
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_fifo_head_config_and_manifest_do_not_hang_and_are_rejected(tmp_path):
    p, d = _one(tmp_path)
    for rel in (".git/HEAD", ".git/config", "manifest.json"):
        os.remove(d / rel)
        os.mkfifo(d / rel)
    r = rp.check_repo_per_project(tmp_path, [p])
    assert {"GIT_HEAD_INVALID", "MANIFEST_MISSING_OR_INVALID"} <= codes(r)
    assert r["projects"][0]["remote_recorded"] is False


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_fifo_readme_and_listed_file_rejected(tmp_path):
    p, d = _one(tmp_path, files={"a.py": b"a"})
    os.remove(d / "README.md")
    os.mkfifo(d / "README.md")
    os.remove(d / "a.py")
    os.mkfifo(d / "a.py")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REQUIRED_FILE_MISSING" in codes(r)
    assert {f["detail"] for f in r["projects"][0]["findings"] if f["code"] == "MANIFEST_FILE_NOT_MATCHED"} == {"a.py:NOT_REGULAR_FILE"}


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_hardlinked_fifo_head_is_not_counted_as_a_shared_regular_file(tmp_path):
    a, da = _one(tmp_path, "alpha")
    b, db = _one(tmp_path, "beta", {"x.py": b"x\n"})
    os.remove(da / ".git" / "HEAD")
    os.remove(db / ".git" / "HEAD")
    os.mkfifo(da / ".git" / "HEAD")
    os.link(da / ".git" / "HEAD", db / ".git" / "HEAD")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "GIT_HEAD_INVALID" in codes(r, 0) and "SHARED_INODE" not in codes(r, 0)


def test_git_dir_with_head_directory_and_config_directory(tmp_path):
    p, d = _one(tmp_path)
    for rel in (".git/HEAD", ".git/config"):
        os.remove(d / rel)
        (d / rel).mkdir()
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "GIT_HEAD_INVALID" in codes(r) and r["projects"][0]["remote_recorded"] is False


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_hardlinked_fifo_config_is_not_counted_as_a_shared_regular_file(tmp_path):
    a, da = _one(tmp_path, "alpha")
    b, db = _one(tmp_path, "beta", {"x.py": b"x\n"})
    os.remove(da / ".git" / "config")
    os.remove(db / ".git" / "config")
    os.mkfifo(da / ".git" / "config")
    os.link(da / ".git" / "config", db / ".git" / "config")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_INODE" not in codes(r, 0) and "SHARED_INODE" not in codes(r, 1)
    assert r["projects"][0]["remote_recorded"] is False


# --- fourth commit: strict declared URL host and port (finding REPOSITORY_URL_INVALID, no exception) ---
_URL_MSG = "declared repository must be a plain credential-free https URL"


@pytest.mark.parametrize("bad", [
    "https://exa mple.test:99999999/x",
    "https://exa mple.test/x",
    "https://example.test:99999999/x",
    "https://example.test:65536/x",
    "https://example.test:abc/x",
    "https://example.test:-1/x",
    "https://example.test:1 2/x",
    "https://example. test/x",
    "https://example.test\t/x",
    "https://exa\tmple.test/x",
    "https://example.test:80a/x",
])
def test_declared_url_with_space_host_or_bad_port_is_a_finding_not_an_exception(tmp_path, bad):
    p = proj(tmp_path, "alpha", url=bad)
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" in codes(r)
    f = [f for f in r["projects"][0]["findings"] if f["code"] == "REPOSITORY_URL_INVALID"]
    assert len(f) == 1 and f[0]["detail"] == _URL_MSG
    assert r["projects"][0]["status"] == "STRUCTURE_FAILED"


@pytest.mark.parametrize("good", [
    "https://example.test/x",
    "https://example.test:443/x",
    "https://example.test:0/x",
    "https://example.test:65535/x",
    "https://example.test:8080/org/repo.git",
    "https://example.test:/x",
])
def test_declared_url_with_valid_port_still_passes(tmp_path, good):
    p = proj(tmp_path, "alpha", url=good)
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" not in codes(r)
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_invalid_declared_url_does_not_raise_repo_structure_error(tmp_path):
    p = proj(tmp_path, "alpha", url="https://exa mple.test:99999999/x")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert r["projects"][0]["remote_recorded"] in (True, False)


def test_bad_port_url_is_not_compared_against_remote(tmp_path):
    p, d = _one(tmp_path, url="https://example.test:99999999/x")
    _cfg(d, '[remote "origin"]\n\turl = https://other.test/x\n')
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" in codes(r) and "REMOTE_MISMATCH" not in codes(r)


def test_remote_config_url_is_still_only_compared_not_validated(tmp_path):
    p, d = _one(tmp_path, url="https://example.test/x")
    _cfg(d, '[remote "origin"]\n\turl = https://exa mple.test:99999999/x\n')
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" not in codes(r)
    assert "REMOTE_MISMATCH" in codes(r)
    assert r["projects"][0]["remote_recorded"] is True


def test_two_projects_invalid_urls_are_not_reported_as_shared(tmp_path):
    a = proj(tmp_path, "alpha", url="https://exa mple.test:99999999/x")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://exa mple.test:99999999/x")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_REPOSITORY_URL" not in codes(r, 0) and "SHARED_REPOSITORY_URL" not in codes(r, 1)


def test_whitespace_rule_is_limited_to_the_authority_not_the_path(tmp_path):
    p = proj(tmp_path, "alpha", url="https://example.test/org/my repo")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" not in codes(r)


def test_surrounding_whitespace_around_a_valid_declared_url_is_tolerated(tmp_path):
    p = proj(tmp_path, "alpha", url="  https://example.test:8443/x \n")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" not in codes(r)
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_trailing_whitespace_after_a_bare_authority_is_tolerated(tmp_path):
    p = proj(tmp_path, "alpha", url="https://example.test:8443 ")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "REPOSITORY_URL_INVALID" not in codes(r)
