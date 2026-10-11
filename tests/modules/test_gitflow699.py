"""Row 699 Git Flow: tests drive real git repositories in temp dirs."""
import importlib.util
import pathlib
import subprocess

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/gitflow699.py"


def _load():
    spec = importlib.util.spec_from_file_location("gitflow699", _SRC)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["gitflow699"] = mod
    spec.loader.exec_module(mod)
    return mod


gf = _load()


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True,
                          env=gf.clean_git_env()).stdout.strip()


def commit(repo, name, text="x"):
    (pathlib.Path(repo) / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"add {name}")


@pytest.fixture
def flow(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    f = gf.GitFlow(repo)
    f.init()
    return f


def branches(repo):
    return set(git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())


def test_init_creates_main_and_develop(flow):
    assert branches(flow.path) == {"main", "develop"}
    assert git(flow.path, "rev-parse", "main") == git(flow.path, "rev-parse", "develop")


def test_init_is_idempotent(flow):
    flow.init()
    assert branches(flow.path) == {"main", "develop"}


def test_classify_branch():
    c = gf.classify_branch
    assert c("main") == ("main", None)
    assert c("develop") == ("develop", None)
    assert c("feature/login") == ("feature", "login")
    assert c("release/1.2.0") == ("release", "1.2.0")
    assert c("hotfix/1.2.1") == ("hotfix", "1.2.1")
    assert c("random") == ("other", None)
    assert c("feature/") == ("other", None)


@pytest.mark.parametrize("bad", ["", "a b", "x..y", "-x", "a/b", "x.lock", "a~b", "a:b", ".x", "x.", "a@{b"])
def test_feature_name_rejected(flow, bad):
    with pytest.raises(gf.GitFlowError):
        flow.start("feature", bad)


@pytest.mark.parametrize("bad", ["1.2", "v1.2.3", "1.2.3-rc1", "01.2.3", "a.b.c", ""])
def test_release_name_must_be_semver(flow, bad):
    with pytest.raises(gf.GitFlowError):
        flow.start("release", bad)


def test_feature_start_branches_from_develop(flow):
    commit(flow.path, "d.txt")  # on develop? ensure checked out develop
    flow.start("feature", "login")
    assert "feature/login" in branches(flow.path)
    assert git(flow.path, "branch", "--show-current") == "feature/login"
    assert git(flow.path, "rev-parse", "feature/login") == git(flow.path, "rev-parse", "develop")


def test_feature_duplicate_rejected(flow):
    flow.start("feature", "a")
    git(flow.path, "checkout", "-q", "develop")
    with pytest.raises(gf.GitFlowError):
        flow.start("feature", "a")


def test_feature_finish_merges_noff_into_develop_and_deletes(flow):
    flow.start("feature", "login")
    commit(flow.path, "login.py")
    flow.finish("feature", "login")
    assert "feature/login" not in branches(flow.path)
    assert git(flow.path, "branch", "--show-current") == "develop"
    parents = git(flow.path, "rev-list", "--parents", "-n1", "develop").split()
    assert len(parents) == 3  # merge commit, --no-ff
    assert (flow.path / "login.py").exists()
    git(flow.path, "checkout", "-q", "main")
    assert not (flow.path / "login.py").exists()  # main untouched


def test_finish_unknown_branch(flow):
    with pytest.raises(gf.GitFlowError):
        flow.finish("feature", "nope")


def test_feature_finish_conflict_aborts_and_keeps_branch(flow):
    commit(flow.path, "f.txt", "base")
    flow.start("feature", "a")
    commit(flow.path, "f.txt", "from-feature")
    git(flow.path, "checkout", "-q", "develop")
    commit(flow.path, "f.txt", "from-develop")
    before = git(flow.path, "rev-parse", "develop")
    with pytest.raises(gf.GitFlowError):
        flow.finish("feature", "a")
    assert "feature/a" in branches(flow.path)
    assert git(flow.path, "rev-parse", "develop") == before
    assert git(flow.path, "status", "--porcelain") == ""
    assert not (flow.path / ".git" / "MERGE_HEAD").exists()


def test_dirty_worktree_blocks_finish(flow):
    commit(flow.path, "other.txt", "clean")
    flow.start("feature", "a")
    commit(flow.path, "a.py")
    (flow.path / "other.txt").write_text("dirty")
    dev = git(flow.path, "rev-parse", "develop")
    with pytest.raises(gf.GitFlowError, match="not clean"):
        flow.finish("feature", "a")
    assert git(flow.path, "rev-parse", "develop") == dev


def test_dirty_worktree_blocks_start(flow):
    commit(flow.path, "other.txt", "clean")
    (flow.path / "other.txt").write_text("dirty")
    with pytest.raises(gf.GitFlowError, match="not clean"):
        flow.start("feature", "a")


def test_release_lifecycle_tags_main_and_backmerges(flow):
    flow.start("feature", "x")
    commit(flow.path, "x.py")
    flow.finish("feature", "x")
    flow.start("release", "1.0.0")
    assert git(flow.path, "branch", "--show-current") == "release/1.0.0"
    commit(flow.path, "VERSION", "1.0.0")
    flow.finish("release", "1.0.0")
    assert "release/1.0.0" not in branches(flow.path)
    assert git(flow.path, "cat-file", "-t", "v1.0.0") == "tag"  # annotated
    assert git(flow.path, "rev-parse", "v1.0.0^{commit}") == git(flow.path, "rev-parse", "main")
    # develop contains everything main has
    git(flow.path, "merge-base", "--is-ancestor", "main", "develop")
    git(flow.path, "checkout", "-q", "main")
    assert (flow.path / "VERSION").exists() and (flow.path / "x.py").exists()


def test_only_one_release_open(flow):
    flow.start("release", "1.0.0")
    git(flow.path, "checkout", "-q", "develop")
    with pytest.raises(gf.GitFlowError):
        flow.start("release", "1.1.0")


def test_release_must_exceed_latest_tag(flow):
    flow.start("release", "1.0.0")
    flow.finish("release", "1.0.0")
    for v in ("1.0.0", "0.9.0"):
        with pytest.raises(gf.GitFlowError):
            flow.start("release", v)
    flow.start("release", "1.1.0")


def test_hotfix_branches_from_main_and_finishes_to_both(flow):
    flow.start("release", "1.0.0")
    flow.finish("release", "1.0.0")
    flow.start("feature", "wip")
    commit(flow.path, "wip.py")
    git(flow.path, "checkout", "-q", "develop")
    git(flow.path, "checkout", "-q", "develop")
    commit(flow.path, "dev_only.py")
    flow.start("hotfix", "1.0.1")
    assert git(flow.path, "rev-parse", "hotfix/1.0.1") == git(flow.path, "rev-parse", "main")
    assert git(flow.path, "rev-parse", "hotfix/1.0.1") != git(flow.path, "rev-parse", "develop")
    commit(flow.path, "fix.py")
    flow.finish("hotfix", "1.0.1")
    assert "hotfix/1.0.1" not in branches(flow.path)
    assert git(flow.path, "rev-parse", "v1.0.1^{commit}") == git(flow.path, "rev-parse", "main")
    git(flow.path, "merge-base", "--is-ancestor", "main", "develop")
    git(flow.path, "checkout", "-q", "develop")
    assert (flow.path / "fix.py").exists()


def test_hotfix_with_open_release_merges_into_release_not_develop(flow):
    flow.start("release", "1.0.0")
    flow.finish("release", "1.0.0")
    flow.start("release", "1.1.0")
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    commit(flow.path, "fix.py")
    dev_before = git(flow.path, "rev-parse", "develop")
    flow.finish("hotfix", "1.0.1")
    assert git(flow.path, "rev-parse", "develop") == dev_before
    git(flow.path, "merge-base", "--is-ancestor", "main", "release/1.1.0")


def test_hotfix_must_exceed_latest_tag(flow):
    flow.start("release", "1.2.0")
    flow.finish("release", "1.2.0")
    with pytest.raises(gf.GitFlowError):
        flow.start("hotfix", "1.1.9")


def test_finish_refuses_tag_collision_without_changing_branches(flow):
    flow.start("release", "1.0.0")
    commit(flow.path, "r.txt")
    git(flow.path, "tag", "v1.0.0")
    main_before = git(flow.path, "rev-parse", "main")
    with pytest.raises(gf.GitFlowError):
        flow.finish("release", "1.0.0")
    assert git(flow.path, "rev-parse", "main") == main_before
    assert "release/1.0.0" in branches(flow.path)


def test_merge_rules_table():
    ok = gf.merge_allowed
    assert ok("feature", "develop") and not ok("feature", "main")
    assert ok("release", "main") and ok("release", "develop")
    assert ok("hotfix", "main") and ok("hotfix", "develop") and ok("hotfix", "release")
    assert not ok("develop", "main") and not ok("main", "develop")
    assert not ok("feature", "release")


def test_status_reports_kinds_and_state(flow):
    flow.start("feature", "a")
    commit(flow.path, "a.py")
    git(flow.path, "checkout", "-q", "develop")
    s = {b["name"]: b for b in flow.status()}
    assert s["feature/a"]["kind"] == "feature" and s["feature/a"]["ahead_of_base"] == 1
    assert s["feature/a"]["merged"] is False
    assert s["main"]["kind"] == "main"
    assert s["develop"]["current"] is True


def test_audit_flags_nonconforming_branches(flow):
    git(flow.path, "branch", "wip-stuff")
    git(flow.path, "branch", "feature/ok")
    bad = flow.audit()
    assert [b["name"] for b in bad] == ["wip-stuff"]


def test_direct_commit_on_main_detected(flow):
    git(flow.path, "checkout", "-q", "main")
    commit(flow.path, "oops.py")
    findings = flow.audit()
    assert any(f["name"] == "main" and f["problem"] == "main_ahead_of_develop_without_release" for f in findings)


def test_clean_env_strips_aws(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("GIT_DIR", "/nope")
    e = gf.clean_git_env()
    assert not any(k.startswith("AWS_") for k in e) and "GIT_DIR" not in e
