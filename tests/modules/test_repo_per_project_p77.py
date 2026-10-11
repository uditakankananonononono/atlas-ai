"""P77|L65 "A separate repository": structure check over fixture file trees (real temp dirs)."""
import hashlib
import importlib.util
import os
import pathlib
import sys

import pytest


def _load_at():
    try:
        import app.core.project_deliverable_contract as m  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    p = os.environ.get("P77_AT_CONTRACT_PATH")
    if not p:
        pytest.fail("AT integration (app.core.project_deliverable_contract) is not on this base; "
                    "set P77_AT_CONTRACT_PATH to its file", pytrace=False)
    spec = importlib.util.spec_from_file_location("app.core.project_deliverable_contract", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app.core.project_deliverable_contract"] = mod
    spec.loader.exec_module(mod)


_load_at()
from app.modules.instinct_doc import repo_per_project_p77 as rp  # noqa: E402

URL = "https://example.test/{}"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def make_repo(root, name, files=None, git=True, head=b"ref: refs/heads/main\n", remote=None, readme=True):
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
    return d


def spec(pid, files, url=None):
    return {"project_id": pid, "domain": "software", "source_lines": ["P77|L65"],
            "repository": url or URL.format(pid),
            "requested_targets": {"datasets": 0, "project_tools": 0, "program_tools": 0},
            "artifacts": [{"id": f"a{i}", "kind": "code", "path": p, "sha256": sha(b)}
                          for i, (p, b) in enumerate(files.items())], "benchmark": None}


def proj(root, name, files=None, **kw):
    files = files if files is not None else {"src/main.py": b"print(1)\n"}
    make_repo(root, name, files, **kw.pop("repo", {}))
    return {"directory": name, "spec": spec(name, files, **kw)}


def codes(report, i=0):
    return {f["code"] for f in report["projects"][i]["findings"]}


def test_two_separate_consistent_repos(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha"), proj(tmp_path, "beta", {"x.py": b"x\n"})])
    assert [p["status"] for p in r["projects"]] == ["STRUCTURE_CONSISTENT"] * 2
    assert r["counts"]["consistent"] == 2 and r["counts"]["failed"] == 0
    assert r["counts"]["total_projects"] == 2


def test_report_consumes_at_integration_output(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")])
    at = r["projects"][0]["at_report"]
    assert at["project_id"] == "alpha" and at["artifacts"][0]["status"] == "FILE_HASH_MATCH"
    assert at["repository_created"] == "UNVERIFIED"


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
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"git": False})])
    assert "NO_OWN_GIT_DIR" in codes(r)


def test_git_as_symlink_rejected(tmp_path):
    p = proj(tmp_path, "alpha", repo={"git": False})
    real = tmp_path / "elsewhere_git"
    real.mkdir()
    (real / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (tmp_path / "alpha" / ".git").symlink_to(real)
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "NO_OWN_GIT_DIR" in codes(r)


def test_git_as_file_rejected(tmp_path):
    p = proj(tmp_path, "alpha", repo={"git": False})
    (tmp_path / "alpha" / ".git").write_text("gitdir: ../shared\n")
    assert "NO_OWN_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [p]))


@pytest.mark.parametrize("head", [b"", b"garbage\n", b"ref: \n", b"abc\n"])
def test_bad_head_rejected(tmp_path, head):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"head": head})])
    assert "GIT_HEAD_INVALID" in codes(r)


@pytest.mark.parametrize("head", [b"ref: refs/heads/main\n", b"0123456789abcdef0123456789abcdef01234567\n"])
def test_valid_head_forms(tmp_path, head):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"head": head})])
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_readme_required_nonempty(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha", repo={"readme": False})])
    assert "REQUIRED_FILE_MISSING" in codes(r)
    (tmp_path / "alpha" / "README.md").write_text("")
    assert "REQUIRED_FILE_MISSING" in codes(rp.check_repo_per_project(tmp_path, [proj_again(tmp_path)]))


def proj_again(tmp_path):
    files = {"src/main.py": b"print(1)\n"}
    return {"directory": "alpha", "spec": spec("alpha", files)}


def test_custom_required_files(tmp_path):
    p = proj(tmp_path, "alpha")
    p["required_files"] = ["README.md", "LICENSE"]
    assert "REQUIRED_FILE_MISSING" in codes(rp.check_repo_per_project(tmp_path, [p]))
    (tmp_path / "alpha" / "LICENSE").write_text("x")
    assert rp.check_repo_per_project(tmp_path, [p])["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


def test_required_file_path_escape_rejected(tmp_path):
    p = proj(tmp_path, "alpha")
    p["required_files"] = ["../README.md"]
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [p])


def test_missing_project_dir(tmp_path):
    p = {"directory": "ghost", "spec": spec("ghost", {"a.py": b"a"})}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_project_dir_symlink_rejected(tmp_path):
    proj(tmp_path, "real")
    (tmp_path / "alpha").symlink_to(tmp_path / "real")
    p = {"directory": "alpha", "spec": spec("alpha", {"src/main.py": b"print(1)\n"})}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


@pytest.mark.parametrize("d", ["..", "../x", "/abs", "a/../b", ".", "", "a//b"])
def test_directory_must_be_contained_relative(tmp_path, d):
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [{"directory": d, "spec": spec("alpha", {})}])


def test_nested_project_dirs_flagged_on_both(tmp_path):
    outer = proj(tmp_path, "outer")
    inner_files = {"i.py": b"i\n"}
    make_repo(tmp_path / "outer", "inner", inner_files)
    inner = {"directory": "outer/inner", "spec": spec("inner", inner_files)}
    r = rp.check_repo_per_project(tmp_path, [outer, inner])
    assert "NESTED_PROJECT_DIRS" in codes(r, 0) and "NESTED_PROJECT_DIRS" in codes(r, 1)


def test_duplicate_directory_or_project_id_rejected(tmp_path):
    a = proj(tmp_path, "alpha")
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [a, a])
    b = proj(tmp_path, "beta")
    b["spec"]["project_id"] = "alpha"
    with pytest.raises(rp.RepoStructureError):
        rp.check_repo_per_project(tmp_path, [a, b])


def test_shared_declared_repository_url(tmp_path):
    a = proj(tmp_path, "alpha", url="https://example.test/shared")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://example.test/shared")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_REPOSITORY_URL" in codes(r, 0) and "SHARED_REPOSITORY_URL" in codes(r, 1)


def test_url_comparison_ignores_trailing_slash_and_dot_git_and_case_of_host(tmp_path):
    a = proj(tmp_path, "alpha", url="https://Example.test/shared.git")
    b = proj(tmp_path, "beta", {"x.py": b"x\n"}, url="https://example.test/shared/")
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_REPOSITORY_URL" in codes(r, 0)


def test_remote_in_git_config_must_match_declared(tmp_path):
    ok = proj(tmp_path, "alpha", repo={"remote": URL.format("alpha")})
    bad = proj(tmp_path, "beta", {"x.py": b"x\n"}, repo={"remote": "https://example.test/other"})
    r = rp.check_repo_per_project(tmp_path, [ok, bad])
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT" and r["projects"][0]["remote_recorded"] is True
    assert "REMOTE_MISMATCH" in codes(r, 1)


def test_no_remote_recorded_is_reported_not_failed(tmp_path):
    r = rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")])
    assert r["projects"][0]["remote_recorded"] is False
    assert r["projects"][0]["status"] == "STRUCTURE_CONSISTENT"


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
    r = rp.check_repo_per_project(tmp_path, [a, b])
    assert "SHARED_INODE" in codes(r, 0)


def test_artifact_hash_mismatch_fails_via_at(tmp_path):
    p = proj(tmp_path, "alpha")
    (tmp_path / "alpha" / "src" / "main.py").write_bytes(b"changed\n")
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "ARTIFACT_NOT_MATCHED" in codes(r)
    f = [x for x in r["projects"][0]["findings"] if x["code"] == "ARTIFACT_NOT_MATCHED"][0]
    assert "HASH_MISMATCH" in f["detail"]


def test_artifact_missing_fails(tmp_path):
    p = proj(tmp_path, "alpha")
    os.remove(tmp_path / "alpha" / "src" / "main.py")
    assert "ARTIFACT_NOT_MATCHED" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_no_artifacts_declared_fails(tmp_path):
    p = proj(tmp_path, "alpha", {})
    assert "NO_ARTIFACTS_DECLARED" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_artifact_inside_git_dir_flagged(tmp_path):
    files = {".git/HEAD": b"ref: refs/heads/main\n"}
    p = proj(tmp_path, "alpha", files)
    assert "ARTIFACT_INSIDE_GIT_DIR" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_invalid_at_spec_becomes_failed_finding(tmp_path):
    p = proj(tmp_path, "alpha")
    p["spec"]["domain"] = "science"
    r = rp.check_repo_per_project(tmp_path, [p])
    assert "AT_SPEC_INVALID" in codes(r) and r["projects"][0]["status"] == "STRUCTURE_FAILED"
    assert r["projects"][0]["at_report"] is None


def test_artifact_outside_project_rejected_by_at(tmp_path):
    p = proj(tmp_path, "alpha")
    p["spec"]["artifacts"][0]["path"] = "../beta/x.py"
    assert "AT_SPEC_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_input_shape_errors(tmp_path):
    for bad in (None, {}, [{}], [{"directory": "a"}], [{"spec": {}}], [{"directory": 3, "spec": {}}]):
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
    before = sorted(str(x.relative_to(tmp_path)) + str(x.stat().st_mtime_ns) for x in tmp_path.rglob("*"))
    rp.check_repo_per_project(tmp_path, [p])
    after = sorted(str(x.relative_to(tmp_path)) + str(x.stat().st_mtime_ns) for x in tmp_path.rglob("*"))
    assert before == after


def test_markdown_render_lists_every_project_and_codes(tmp_path):
    good = proj(tmp_path, "alpha")
    bad = proj(tmp_path, "beta", {"x.py": b"x\n"}, repo={"git": False})
    md = rp.render_markdown(rp.check_repo_per_project(tmp_path, [good, bad]))
    assert "alpha" in md and "beta" in md and "NO_OWN_GIT_DIR" in md and "STRUCTURE_CONSISTENT" in md
    assert "does not show" in md


# --- added after first mutation pass ---
def test_symlinked_intermediate_component_rejected(tmp_path):
    real = tmp_path / "real_parent"
    real.mkdir()
    make_repo(real, "inner", {"x.py": b"x\n"})
    (tmp_path / "linked").symlink_to(real)
    p = {"directory": "linked/inner", "spec": spec("inner", {"x.py": b"x\n"})}
    assert "DIR_MISSING_OR_UNSAFE" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_same_directory_with_different_ids_rejected(tmp_path):
    a = proj(tmp_path, "alpha")
    b = {"directory": "alpha", "spec": spec("other", {"src/main.py": b"print(1)\n"})}
    with pytest.raises(rp.RepoStructureError, match="duplicate directory"):
        rp.check_repo_per_project(tmp_path, [a, b])


def test_git_head_as_directory_is_invalid_not_a_crash(tmp_path):
    p = proj(tmp_path, "alpha")
    os.remove(tmp_path / "alpha" / ".git" / "HEAD")
    (tmp_path / "alpha" / ".git" / "HEAD").mkdir()
    assert "GIT_HEAD_INVALID" in codes(rp.check_repo_per_project(tmp_path, [p]))


def test_markdown_ends_with_non_fulfilment_line(tmp_path):
    md = rp.render_markdown(rp.check_repo_per_project(tmp_path, [proj(tmp_path, "alpha")]))
    assert md.rstrip().splitlines()[-1] == "This table does not show the line P77|L65 is fulfilled."
