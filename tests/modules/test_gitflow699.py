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


# --- throwaway-repo guard (added in second commit) ---
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_guard_refuses_the_atlas_repo_itself():
    with pytest.raises(gf.GitFlowError, match="temporary"):
        gf.GitFlow(_REPO_ROOT)


def test_guard_refuses_non_temp_path_without_creating_it():
    target = pathlib.Path.home() / "gitflow699_must_not_exist"
    with pytest.raises(gf.GitFlowError, match="temporary"):
        gf.GitFlow(target)
    assert not target.exists()


def test_guard_refuses_symlink_from_temp_to_non_temp(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(_REPO_ROOT)
    with pytest.raises(gf.GitFlowError, match="temporary"):
        gf.GitFlow(link)


def test_guard_refuses_dotdot_escape(tmp_path):
    with pytest.raises(gf.GitFlowError, match="temporary"):
        gf.GitFlow(tmp_path.joinpath(*[".."] * 12) / "nonexistent_gitflow699")


def test_guard_refuses_temp_root_itself():
    import tempfile
    with pytest.raises(gf.GitFlowError, match="temporary"):
        gf.GitFlow(tempfile.gettempdir())


def test_guard_allows_path_inside_temp(tmp_path):
    assert gf.GitFlow(tmp_path / "ok").path.name == "ok"


# --- round 3: marker, no remotes, resolved path (added in third commit) ---
def _preexisting_clone(tmp_path, with_remote=True):
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q", "-b", "main")
    commit(src, "a.txt")
    dst = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(src), str(dst)], check=True, env=gf.clean_git_env())
    git(dst, "branch", "develop")
    return dst


def test_marker_lives_in_git_dir_and_tree_stays_clean(flow):
    assert (flow.path / ".git" / gf.MARKER_NAME).is_file()
    assert git(flow.path, "status", "--porcelain") == ""


def test_init_refuses_preexisting_clone_inside_temp(tmp_path):
    dst = _preexisting_clone(tmp_path)
    before = set(branches(dst))
    f = gf.GitFlow(dst)
    with pytest.raises(gf.GitFlowError, match="not created by this module"):
        f.init()
    assert set(branches(dst)) == before
    assert not (dst / ".git" / gf.MARKER_NAME).exists()


@pytest.mark.parametrize("op", ["start", "finish", "status", "audit"])
def test_ops_refuse_unmarked_repo(tmp_path, op):
    dst = _preexisting_clone(tmp_path)
    f = gf.GitFlow(dst)
    with pytest.raises(gf.GitFlowError, match="not created by this module"):
        if op in ("start", "finish"):
            getattr(f, op)("feature", "x")
        else:
            getattr(f, op)()
    assert "feature/x" not in branches(dst)


def test_init_refuses_clone_of_the_atlas_checkout_inside_temp(tmp_path):
    dst = tmp_path / "atlas_clone"
    subprocess.run(["git", "clone", "-q", "--no-checkout", "--local", str(_REPO_ROOT), str(dst)],
                   check=True, env=gf.clean_git_env())
    with pytest.raises(gf.GitFlowError, match="not created by this module"):
        gf.GitFlow(dst).init()


def test_init_refuses_nonempty_plain_directory(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "file.txt").write_text("x")
    with pytest.raises(gf.GitFlowError, match="not created by this module"):
        gf.GitFlow(d).init()
    assert not (d / ".git").exists()


def test_marked_repo_with_remote_is_refused(flow):
    git(flow.path, "remote", "add", "origin", "https://example.invalid/x.git")
    for call in (lambda: flow.start("feature", "x"), flow.status, flow.audit, flow.init):
        with pytest.raises(gf.GitFlowError, match="remote"):
            call()


def test_ops_use_resolved_path_not_later_symlink_target(tmp_path):
    real = tmp_path / "real"
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q", "-b", "main")
    commit(other, "o.txt")
    link = tmp_path / "link"
    link.symlink_to(real.parent / "real_placeholder_missing")
    real.mkdir()
    link.unlink()
    link.symlink_to(real)
    f = gf.GitFlow(link)
    f.init()
    link.unlink()
    link.symlink_to(other)  # retarget after construction
    f.start("feature", "x")
    assert "feature/x" in branches(real)
    assert branches(other) == {"main"}
    assert f.path == real.resolve()


# ---------------------------------------------------------------------------
# Repair pins (tests only): refusal messages, return values, git side effects.
# ---------------------------------------------------------------------------
import re as _re


def log_count(repo, ref):
    return int(git(repo, "rev-list", "--count", ref))


def tag_commit(repo, tag, ref="HEAD"):
    git(repo, "tag", tag, ref)


def parents(repo, ref):
    return git(repo, "rev-list", "--parents", "-n", "1", ref).split()[1:]


def subject(repo, ref):
    return git(repo, "log", "-1", "--format=%s", ref)


def test_git_failure_raises_with_command_and_git_message(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow._git("checkout", "-q", "no-such-branch")
    assert str(e.value).startswith("git checkout -q no-such-branch failed: ")
    assert "no-such-branch" in str(e.value)


def test_git_check_false_returns_result_without_raising(flow):
    r = flow._git("checkout", "-q", "no-such-branch", check=False)
    assert r.returncode != 0


def test_git_success_returns_completed_process(flow):
    r = flow._git("rev-parse", "main")
    assert r.returncode == 0 and len(r.stdout.strip()) == 40


def test_init_fresh_makes_one_initial_commit_and_marker(flow):
    assert log_count(flow.path, "main") == 1
    assert subject(flow.path, "main") == "initial commit"
    marker = flow.path / ".git" / gf.MARKER_NAME
    assert marker.is_file()
    assert _re.fullmatch(r"[0-9a-f]{32}\n", marker.read_text())
    assert git(flow.path, "branch", "--show-current") == "develop"


def test_init_does_not_add_commit_when_main_already_has_history(flow):
    commit(flow.path, "a.txt")
    flow.init()
    assert log_count(flow.path, "main") == 1
    assert log_count(flow.path, "develop") == 2


def test_init_recreates_missing_develop_from_main_and_leaves_main(flow):
    git(flow.path, "checkout", "-q", "main")
    git(flow.path, "branch", "-D", "develop")
    flow.init()
    assert git(flow.path, "rev-parse", "develop") == git(flow.path, "rev-parse", "main")
    assert git(flow.path, "branch", "--show-current") == "develop"


def test_init_moves_off_main_to_develop(flow):
    git(flow.path, "checkout", "-q", "main")
    flow.init()
    assert git(flow.path, "branch", "--show-current") == "develop"


def test_init_keeps_other_current_branch(flow):
    flow.start("feature", "keep")
    flow.init()
    assert git(flow.path, "branch", "--show-current") == "feature/keep"


def test_init_commits_in_owned_repo_with_no_commits_yet(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    f = gf.GitFlow(repo)
    f.init()
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-D", "develop")
    git(repo, "update-ref", "-d", "refs/heads/main")
    assert git(repo, "for-each-ref", "refs/heads") == ""
    f.init()
    assert log_count(repo, "main") == 1
    assert subject(repo, "main") == "initial commit"
    assert "develop" in branches(repo)


def test_init_refuses_branches_without_main(flow):
    git(flow.path, "checkout", "-q", "develop")
    git(flow.path, "branch", "-m", "main", "trunk")
    with pytest.raises(gf.GitFlowError) as e:
        flow.init()
    assert str(e.value) == "repository has branches but no 'main'"
    assert "main" not in branches(flow.path)


def test_init_refuses_nonempty_unmarked_directory(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "f").write_text("1")
    with pytest.raises(gf.GitFlowError) as e:
        gf.GitFlow(d).init()
    assert "is not empty and was not created by this module; refusing" in str(e.value)
    assert not (d / ".git").exists()


def test_init_refuses_a_file_path(tmp_path):
    p = tmp_path / "file"
    p.write_text("1")
    with pytest.raises(gf.GitFlowError, match="not empty and was not created"):
        gf.GitFlow(p).init()


def test_init_on_marked_repo_with_remote_is_refused(flow):
    git(flow.path, "remote", "add", "o", "https://example.invalid/x.git")
    with pytest.raises(gf.GitFlowError) as e:
        flow.init()
    assert "has a remote configured" in str(e.value)


@pytest.mark.parametrize("op", ["start", "finish", "status", "audit"])
def test_operations_refuse_unmarked_repository(tmp_path, op):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    f = gf.GitFlow(repo)
    args = {"start": ("feature", "a"), "finish": ("feature", "a"), "status": (), "audit": ()}[op]
    with pytest.raises(gf.GitFlowError) as e:
        getattr(f, op)(*args)
    assert "was not created by this module (no throwaway marker); refusing" in str(e.value)


@pytest.mark.parametrize("op", ["start", "finish", "status", "audit"])
def test_operations_refuse_repository_with_remote(flow, op):
    git(flow.path, "remote", "add", "o", "https://example.invalid/x.git")
    args = {"start": ("feature", "a"), "finish": ("feature", "a"), "status": (), "audit": ()}[op]
    with pytest.raises(gf.GitFlowError, match="remote configured"):
        getattr(flow, op)(*args)


def test_start_existing_branch_refused_with_message(flow):
    flow.start("feature", "a")
    git(flow.path, "checkout", "-q", "develop")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("feature", "a")
    assert str(e.value) == "feature/a already exists"


def test_start_requires_clean_tree(flow):
    commit(flow.path, "t.txt")
    (flow.path / "t.txt").write_text("changed")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("feature", "a")
    assert str(e.value) == "working tree is not clean"
    assert "feature/a" not in branches(flow.path)


def test_start_refuses_when_develop_missing(flow):
    git(flow.path, "checkout", "-q", "main")
    git(flow.path, "branch", "-D", "develop")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("feature", "a")
    assert str(e.value) == "repository is not initialised for git flow"
    assert "feature/a" not in branches(flow.path)


def test_start_refuses_when_main_missing(flow):
    git(flow.path, "branch", "-m", "main", "trunk")
    assert "develop" in branches(flow.path) and "main" not in branches(flow.path)
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("feature", "a")
    assert str(e.value) == "repository is not initialised for git flow"


def test_start_returns_branch_name_and_checks_it_out(flow):
    assert flow.start("feature", "a") == "feature/a"
    assert git(flow.path, "branch", "--show-current") == "feature/a"
    assert flow.start.__name__ == "start"


@pytest.mark.parametrize("kind", ["release", "hotfix"])
def test_start_refuses_existing_tag_equal_version(flow, kind):
    tag_commit(flow.path, "v1.0.0")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start(kind, "1.0.0")
    assert str(e.value) == "tag v1.0.0 already exists"
    assert f"{kind}/1.0.0" not in branches(flow.path)


@pytest.mark.parametrize("kind", ["release", "hotfix"])
def test_start_refuses_version_below_latest_tag(flow, kind):
    tag_commit(flow.path, "v1.2.0")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start(kind, "1.1.9")
    assert str(e.value) == f"{kind} version 1.1.9 must be greater than latest tag v1.2.0"
    assert f"{kind}/1.1.9" not in branches(flow.path)


@pytest.mark.parametrize("kind", ["release", "hotfix"])
def test_start_accepts_version_above_latest_tag_numerically(flow, kind):
    tag_commit(flow.path, "v1.9.0")
    tag_commit(flow.path, "v1.10.0")
    with pytest.raises(gf.GitFlowError, match="must be greater than latest tag v1.10.0"):
        flow.start(kind, "1.9.5")
    assert flow.start(kind, "1.10.1") == f"{kind}/1.10.1"


def test_start_ignores_non_semver_tags_for_ordering(flow):
    tag_commit(flow.path, "vfoo")
    tag_commit(flow.path, "v2.0.0")
    assert flow._highest_tag() == "v2.0.0"
    assert flow.start("release", "2.0.1") == "release/2.0.1"


def test_second_release_refused_while_one_open(flow):
    flow.start("release", "1.0.0")
    git(flow.path, "checkout", "-q", "develop")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("release", "1.1.0")
    assert str(e.value) == "a release branch is already open: release/1.0.0"
    assert "release/1.1.0" not in branches(flow.path)


def test_hotfix_and_feature_allowed_while_release_open(flow):
    flow.start("release", "1.0.0")
    git(flow.path, "checkout", "-q", "main")
    assert flow.start("hotfix", "1.0.1") == "hotfix/1.0.1"
    git(flow.path, "checkout", "-q", "develop")
    assert flow.start("feature", "z") == "feature/z"


def test_start_release_and_hotfix_bases(flow):
    commit(flow.path, "d.txt")  # develop ahead of main
    flow.start("release", "1.0.0")
    assert git(flow.path, "rev-parse", "release/1.0.0") == git(flow.path, "rev-parse", "develop")
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    assert git(flow.path, "rev-parse", "hotfix/1.0.1") == git(flow.path, "rev-parse", "main")
    assert git(flow.path, "rev-parse", "hotfix/1.0.1") != git(flow.path, "rev-parse", "develop")


def test_finish_missing_branch_refused(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("feature", "nope")
    assert str(e.value) == "feature/nope does not exist"


def test_finish_unknown_kind_refused(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("bugfix", "x")
    assert str(e.value) == "unknown kind: bugfix"


def test_finish_requires_clean_tree(flow):
    flow.start("feature", "a")
    commit(flow.path, "t.txt")
    (flow.path / "t.txt").write_text("dirty")
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("feature", "a")
    assert str(e.value) == "working tree is not clean"
    assert "feature/a" in branches(flow.path)


def test_finish_feature_returns_full_dict_and_cleans_up(flow):
    flow.start("feature", "a")
    commit(flow.path, "a.txt")
    res = flow.finish("feature", "a")
    assert res == {"merged_into": ["develop"], "tag": None}
    assert "feature/a" not in branches(flow.path)
    assert git(flow.path, "branch", "--show-current") == "develop"
    assert subject(flow.path, "develop") == "Merge feature/a into develop"
    assert len(parents(flow.path, "develop")) == 2
    assert (flow.path / "a.txt").exists()


def test_finish_release_returns_full_dict_tag_and_merges(flow):
    flow.start("release", "1.0.0")
    commit(flow.path, "r.txt")
    res = flow.finish("release", "1.0.0")
    assert res == {"merged_into": ["main", "develop"], "tag": "v1.0.0"}
    assert "release/1.0.0" not in branches(flow.path)
    assert git(flow.path, "cat-file", "-t", "v1.0.0") == "tag"
    assert git(flow.path, "tag", "-l", "--format=%(contents:subject)", "v1.0.0") == "release 1.0.0"
    assert subject(flow.path, "main") == "Merge release/1.0.0 into main"
    assert len(parents(flow.path, "main")) == 2
    assert subject(flow.path, "develop") == "Merge v1.0.0 back into develop"
    assert len(parents(flow.path, "develop")) == 2
    assert git(flow.path, "rev-parse", "v1.0.0^{commit}") == git(flow.path, "rev-parse", "main")
    assert git(flow.path, "branch", "--show-current") == "develop"


def test_finish_hotfix_returns_full_dict_back_to_develop(flow):
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    commit(flow.path, "h.txt")
    res = flow.finish("hotfix", "1.0.1")
    assert res == {"merged_into": ["main", "develop"], "tag": "v1.0.1"}
    assert "hotfix/1.0.1" not in branches(flow.path)
    assert git(flow.path, "tag", "-l", "--format=%(contents:subject)", "v1.0.1") == "hotfix 1.0.1"
    assert subject(flow.path, "develop") == "Merge v1.0.1 back into develop"


def test_finish_hotfix_goes_back_into_open_release_not_develop(flow):
    flow.start("release", "2.0.0")
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    commit(flow.path, "h.txt")
    dev_before = git(flow.path, "rev-parse", "develop")
    res = flow.finish("hotfix", "1.0.1")
    assert res == {"merged_into": ["main", "release/2.0.0"], "tag": "v1.0.1"}
    assert git(flow.path, "rev-parse", "develop") == dev_before
    assert subject(flow.path, "release/2.0.0") == "Merge v1.0.1 back into release/2.0.0"
    assert (git(flow.path, "show", "release/2.0.0:h.txt")) == "x"


def test_finish_release_ignores_itself_as_other_release(flow):
    flow.start("release", "1.0.0")
    res = flow.finish("release", "1.0.0")
    assert res["merged_into"] == ["main", "develop"]


def test_finish_refuses_when_tag_already_exists(flow):
    flow.start("release", "1.0.0")
    tag_commit(flow.path, "v1.0.0")
    main_before = git(flow.path, "rev-parse", "main")
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("release", "1.0.0")
    assert str(e.value) == "tag v1.0.0 already exists"
    assert "release/1.0.0" in branches(flow.path)
    assert git(flow.path, "rev-parse", "main") == main_before


def test_finish_conflict_is_aborted_with_message_and_clean_tree(flow):
    commit(flow.path, "c.txt", "base")
    flow.start("feature", "a")
    commit(flow.path, "c.txt", "from feature")
    git(flow.path, "checkout", "-q", "develop")
    commit(flow.path, "c.txt", "from develop")
    git(flow.path, "checkout", "-q", "feature/a")
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("feature", "a")
    assert str(e.value) == "merge of feature/a into develop conflicted and was aborted"
    assert git(flow.path, "status", "--porcelain") == ""
    assert "feature/a" in branches(flow.path)
    assert not (flow.path / ".git" / "MERGE_HEAD").exists()


def test_status_rows_for_every_kind_with_ahead_and_merged(flow):
    flow.start("feature", "a")
    commit(flow.path, "a.txt")
    commit(flow.path, "b.txt")
    git(flow.path, "checkout", "-q", "develop")
    git(flow.path, "branch", "stray")
    rows = {r["name"]: r for r in flow.status()}
    assert rows["main"] == {"name": "main", "kind": "main", "current": False, "base": None,
                            "ahead_of_base": None, "merged": None}
    assert rows["develop"]["current"] is True and rows["develop"]["base"] is None
    assert rows["stray"]["kind"] == "other" and rows["stray"]["base"] is None
    assert rows["stray"]["ahead_of_base"] is None and rows["stray"]["merged"] is None
    fa = rows["feature/a"]
    assert fa == {"name": "feature/a", "kind": "feature", "current": False, "base": "develop",
                  "ahead_of_base": 2, "merged": False}


def test_status_merged_and_zero_ahead_distinguished(flow):
    flow.start("feature", "m")
    git(flow.path, "checkout", "-q", "develop")
    row = next(r for r in flow.status() if r["name"] == "feature/m")
    assert row["ahead_of_base"] == 0 and row["merged"] is True
    flow.start("feature", "n")
    commit(flow.path, "n.txt")
    git(flow.path, "checkout", "-q", "develop")
    row = next(r for r in flow.status() if r["name"] == "feature/n")
    assert row["ahead_of_base"] == 1 and row["merged"] is False
    git(flow.path, "merge", "-q", "--no-ff", "-m", "m", "feature/n")
    row = next(r for r in flow.status() if r["name"] == "feature/n")
    assert row["ahead_of_base"] == 0 and row["merged"] is True


def test_status_hotfix_base_is_main_and_release_base_develop(flow):
    flow.start("release", "1.0.0")
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    commit(flow.path, "h.txt")
    rows = {r["name"]: r for r in flow.status()}
    assert rows["hotfix/1.0.1"]["base"] == "main" and rows["hotfix/1.0.1"]["ahead_of_base"] == 1
    assert rows["hotfix/1.0.1"]["merged"] is False and rows["hotfix/1.0.1"]["current"] is True
    assert rows["release/1.0.0"]["base"] == "develop" and rows["release/1.0.0"]["kind"] == "release"


def test_status_missing_base_branch_leaves_counts_none(flow):
    flow.start("feature", "a")
    commit(flow.path, "a.txt")
    git(flow.path, "branch", "-m", "develop", "dev2")
    row = next(r for r in flow.status() if r["name"] == "feature/a")
    assert row["base"] == "develop"
    assert row["ahead_of_base"] is None and row["merged"] is None


def test_highest_tag_merged_filter_distinguishes_unmerged_tags(flow):
    tag_commit(flow.path, "v1.0.0")
    flow.start("feature", "x")
    commit(flow.path, "x.txt")
    tag_commit(flow.path, "v2.0.0")
    git(flow.path, "checkout", "-q", "develop")
    assert flow._highest_tag() == "v2.0.0"
    assert flow._highest_tag("develop") == "v1.0.0"
    assert flow._highest_tag("feature/x") == "v2.0.0"
    assert flow._highest_tag("main") == "v1.0.0"


def test_highest_tag_none_when_no_tags(flow):
    assert flow._highest_tag() is None
    assert flow._highest_tag("develop") is None


def test_audit_reports_nonconforming_and_main_ahead(flow):
    assert flow.audit() == []
    git(flow.path, "branch", "weird")
    assert flow.audit() == [{"name": "weird", "problem": "nonconforming_branch_name"}]
    git(flow.path, "branch", "-D", "weird")
    git(flow.path, "checkout", "-q", "main")
    commit(flow.path, "m.txt")
    assert flow.audit() == [{"name": "main", "problem": "main_ahead_of_develop_without_release"}]
    git(flow.path, "branch", "release/9.9.9", "develop")
    assert flow.audit() == []


# --- constructs named in the audit: env dict, slug rules, nested init, unknown kind, audit strings ---
def test_clean_git_env_exact_git_settings(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("GIT_DIR", "/nowhere")
    monkeypatch.setenv("KEEP_ME", "1")
    env = gf.clean_git_env()
    assert "AWS_SECRET_ACCESS_KEY" not in env and "GIT_DIR" not in env
    assert env["KEEP_ME"] == "1"
    import os as _os
    assert env["GIT_CONFIG_GLOBAL"] == _os.devnull and env["GIT_CONFIG_SYSTEM"] == _os.devnull
    assert env["GIT_AUTHOR_NAME"] == "gitflow" and env["GIT_COMMITTER_NAME"] == "gitflow"
    assert env["GIT_AUTHOR_EMAIL"] == "gitflow@example.invalid"
    assert env["GIT_COMMITTER_EMAIL"] == "gitflow@example.invalid"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.parametrize("name,ok", [
    ("login", True), ("a-b_c", True), ("v1.2", True), ("a.b", True),
    ("-x", False), (".x", False), ("x.", False), ("x.lock", False), ("a/b", False), ("", False),
    ("a b", False), ("a~b", False), ("a^b", False), ("a:b", False), ("a?b", False), ("a*b", False),
    ("a[b", False), ("a\\b", False), ("a..b", False), ("a@{b", False), ("a//b", False),
    ("a@b", True), ("lock", True), ("x.locky", True),
])
def test_valid_slug_each_rule(name, ok):
    assert gf._valid_slug(name) is ok


def test_init_creates_missing_nested_directory(tmp_path):
    target = tmp_path / "a" / "b" / "r"
    f = gf.GitFlow(target)
    f.init()
    assert target.is_dir() and (target / ".git" / gf.MARKER_NAME).is_file()
    assert branches(target) == {"main", "develop"}


def test_init_uses_main_as_initial_branch_name(flow):
    roots = git(flow.path, "rev-list", "--max-parents=0", "main").split()
    assert len(roots) == 1
    assert git(flow.path, "rev-parse", "main") == roots[0]


def test_start_unknown_kind_message_and_no_branch(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("bugfix", "x")
    assert str(e.value) == "unknown kind: bugfix"
    assert "bugfix/x" not in branches(flow.path)


def test_semver_name_message_for_release(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("release", "1.0")
    assert str(e.value) == "release name must be MAJOR.MINOR.PATCH semver: '1.0'"


def test_feature_name_message(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("feature", "a b")
    assert str(e.value) == "invalid feature name: 'a b'"


def test_audit_finding_strings_exact(flow):
    git(flow.path, "branch", "odd")
    git(flow.path, "checkout", "-q", "main")
    commit(flow.path, "m.txt")
    out = flow.audit()
    assert {"name": "odd", "problem": "nonconforming_branch_name"} in out
    assert {"name": "main", "problem": "main_ahead_of_develop_without_release"} in out
    assert len(out) == 2
    git(flow.path, "branch", "hotfix/9.9.9", "main")
    assert flow.audit() == [{"name": "odd", "problem": "nonconforming_branch_name"}]


def test_marker_file_has_the_documented_literal_name(flow):
    assert gf.MARKER_NAME == "gitflow699-throwaway"
    assert (flow.path / ".git" / "gitflow699-throwaway").is_file()


def test_merge_refused_for_a_non_conflict_reason_still_reports_conflict_error(flow):
    git(flow.path, "checkout", "-q", "--orphan", "feature/orph")
    commit(flow.path, "o.txt")
    with pytest.raises(gf.GitFlowError) as e:
        flow.finish("feature", "orph")
    assert str(e.value) == "merge of feature/orph into develop conflicted and was aborted"
    assert "feature/orph" in branches(flow.path)
    assert git(flow.path, "status", "--porcelain") == ""


# --- required groups from the landing review (test-only) ---
def test_git_failure_message_has_command_prefix_and_real_git_stderr_for_newline_version(flow):
    # Observed with the installed git: a version with a trailing newline passes the SEMVER regex
    # (the "$" anchor matches before a final newline) and git then refuses the branch name.
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("release", "1.0.0\n")
    msg = str(e.value)
    assert msg.startswith("git checkout -q -b release/1.0.0\n develop failed: ")
    stderr_part = msg[len("git checkout -q -b release/1.0.0\n develop failed: "):]
    assert "is not a valid branch name" in stderr_part
    assert "release/1.0.0" in stderr_part
    assert "release/1.0.0\n" not in branches(flow.path)


def test_git_failure_message_includes_stderr_text_of_the_actual_failure(flow):
    with pytest.raises(gf.GitFlowError) as e:
        flow._git("checkout", "-q", "missing-branch-xyz")
    msg = str(e.value)
    assert msg.startswith("git checkout -q missing-branch-xyz failed: ")
    tail = msg.split("failed: ", 1)[1]
    assert tail.strip() != "" and "missing-branch-xyz" in tail


def test_newline_version_with_existing_tag_reports_version_not_greater(flow):
    tag_commit(flow.path, "v1.0.0")
    with pytest.raises(gf.GitFlowError) as e:
        flow.start("release", "1.0.0\n")
    assert str(e.value) == "release version 1.0.0\n must be greater than latest tag v1.0.0"


def test_audit_with_missing_develop_returns_empty_list(flow):
    git(flow.path, "checkout", "-q", "main")
    commit(flow.path, "m.txt")
    git(flow.path, "branch", "-D", "develop")
    assert "develop" not in branches(flow.path) and "main" in branches(flow.path)
    assert flow.audit() == []


def test_audit_with_missing_main_returns_empty_list(flow):
    commit(flow.path, "d.txt")
    git(flow.path, "branch", "-D", "main")
    assert "main" not in branches(flow.path) and "develop" in branches(flow.path)
    assert flow.audit() == []


def test_audit_with_missing_develop_still_reports_nonconforming_names(flow):
    git(flow.path, "checkout", "-q", "main")
    git(flow.path, "branch", "odd")
    git(flow.path, "branch", "-D", "develop")
    assert flow.audit() == [{"name": "odd", "problem": "nonconforming_branch_name"}]


def test_finish_hotfix_with_two_open_releases_merges_into_first_sorted_release(flow):
    git(flow.path, "branch", "release/2.0.0", "develop")
    git(flow.path, "branch", "release/1.5.0", "develop")
    git(flow.path, "checkout", "-q", "main")
    flow.start("hotfix", "1.0.1")
    commit(flow.path, "h.txt")
    res = flow.finish("hotfix", "1.0.1")
    assert res == {"merged_into": ["main", "release/1.5.0"], "tag": "v1.0.1"}
    assert git(flow.path, "show", "release/1.5.0:h.txt") == "x"
    assert subprocess.run(["git", "-C", str(flow.path), "cat-file", "-e", "release/2.0.0:h.txt"],
                          capture_output=True).returncode != 0
