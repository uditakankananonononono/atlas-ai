"""Row698 scoped trunk-based-development DAG analysis tests."""
import copy
import itertools
import json
import random

import pytest

from app.modules.m20_general_cognitive_worker import trunk_graph698 as mod
from app.modules.m20_general_cognitive_worker.trunk_graph698 import analyze_trunk

REF = "2026-10-11T12:00:00+05:30"  # == 06:30:00Z


def S(i):
    return f"{i:040x}"


def T(hours_before_ref):
    """UTC timestamp `hours_before_ref` hours before REF (06:30Z)."""
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 10, 11, 6, 30, tzinfo=timezone.utc)
    return (base - timedelta(hours=hours_before_ref)).strftime("%Y-%m-%dT%H:%M:%SZ")


def C(i, parents, h):
    return {"sha": S(i), "parents": [S(p) for p in parents], "committed_at": T(h)}


def base():
    # c1 <- c2 <- c3(main). feature: c2 <- c4 <- c5.
    return {
        "source_ref": "audit/repo-snapshot-1",
        "trunk": "main",
        "reference_time": REF,
        "max_branch_age_hours": 24,
        "required_checks": ["ci", "lint"],
        "commits": [C(1, [], 100), C(2, [1], 90), C(3, [2], 30), C(4, [2], 20), C(5, [4], 10)],
        "branches": [{"name": "main", "tip": S(3)}, {"name": "feat", "tip": S(5)}],
        "checks": [
            {"name": "ci", "sha": S(5), "conclusion": "success"},
            {"name": "lint", "sha": S(5), "conclusion": "success"},
            {"name": "ci", "sha": S(3), "conclusion": "success"},
        ],
    }


def msg(d):
    with pytest.raises(ValueError) as e:
        analyze_trunk(d)
    return str(e.value)


def br(r, name):
    return next(b for b in r["branches"] if b["name"] == name)


# ---------- known answers ----------
def test_diverged_branch_known_answer():
    r = analyze_trunk(base())
    f = br(r, "feat")
    assert (f["ahead"], f["behind"]) == (2, 1)
    assert f["merge_bases"] == [S(2)]
    assert f["state"] == "diverged"
    assert f["unmerged_commits"] == sorted([S(4), S(5)])
    assert f["oldest_unmerged_commit_at"] == T(20)
    assert f["age_seconds"] == 20 * 3600 and f["stale"] is False
    assert f["merge_commits_in_unmerged"] == []
    m = br(r, "main")
    assert (m["ahead"], m["behind"], m["state"]) == (0, 0, "trunk")
    assert r["trunk"]["tip"] == S(3)


def test_fast_forwardable_and_merged_states():
    d = base(); d["commits"][4:] = [C(5, [2], 10)]  # feat tip c5 directly on c2? keep c4 unreferenced
    d["commits"] = [c for c in d["commits"] if c["sha"] != S(4)]
    r = analyze_trunk(d)
    assert (br(r, "feat")["ahead"], br(r, "feat")["behind"]) == (1, 1)
    d = base(); d["branches"][1]["tip"] = S(2)  # feat is ancestor of main
    f = br(analyze_trunk(d), "feat")
    assert (f["ahead"], f["behind"], f["state"]) == (0, 1, "merged")
    assert f["age_seconds"] == 0 and f["oldest_unmerged_commit_at"] is None and f["stale"] is False
    d = base(); d["commits"].append(C(6, [3], 5)); d["branches"][0]["tip"] = S(6)
    d["commits"].append(C(7, [6], 2)); d["branches"][1]["tip"] = S(7)  # feat strictly ahead of main
    r = analyze_trunk(d)
    f = br(r, "feat")
    assert (f["ahead"], f["behind"], f["state"]) == (1, 0, "ahead")


def test_merge_vs_linear_history():
    d = base()
    d["commits"].append(C(6, [3, 5], 5))   # merge commit on trunk
    d["branches"][0]["tip"] = S(6)
    r = analyze_trunk(d)
    f = br(r, "feat")
    assert f["ahead"] == 0 and f["state"] == "merged"
    assert f["behind"] == 2  # c3 and c6
    # branch containing a merge commit reports it
    d = base()
    d["commits"] += [C(6, [5, 3], 5)]
    d["branches"][1]["tip"] = S(6)
    f = br(analyze_trunk(d), "feat")
    assert f["merge_commits_in_unmerged"] == [S(6)]
    assert f["ahead"] == 3 and f["behind"] == 0 and f["state"] == "ahead"
    assert f["merge_bases"] == [S(3)]


def test_criss_cross_has_two_merge_bases():
    d = base()
    d["commits"] = [C(1, [], 100), C(2, [1], 90), C(3, [1], 80), C(4, [2, 3], 30), C(5, [2, 3], 20)]
    d["branches"] = [{"name": "main", "tip": S(4)}, {"name": "feat", "tip": S(5)}]
    d["checks"] = []
    f = br(analyze_trunk(d), "feat")
    assert f["merge_bases"] == [S(2), S(3)]
    assert (f["ahead"], f["behind"]) == (1, 1)


def test_unrelated_branch_and_unreachable_commits():
    d = base()
    d["commits"] += [C(8, [], 50), C(9, [8], 40), C(10, [1], 7)]
    d["branches"].append({"name": "orphan", "tip": S(9)})
    r = analyze_trunk(d)
    o = br(r, "orphan")
    assert o["state"] == "unrelated" and o["merge_bases"] == []
    assert o["ahead"] == 2
    assert o["oldest_unmerged_commit_at"] == T(50) and o["age_seconds"] == 50 * 3600 and o["stale"] is True
    assert r["unreachable_commits"] == [S(10)]
    assert r["trunk"]["commit_count"] == 3


# ---------- checks ----------
def test_check_on_ancestor_does_not_cover_tip():
    r = analyze_trunk(base())
    f = br(r, "feat")
    assert f["required_checks"] == {"ci": {"status": "passed", "stale_ancestor_shas": []},
                                    "lint": {"status": "passed", "stale_ancestor_shas": []}}
    assert f["required_checks_covered"] is True
    m = br(r, "main")  # ci passed on c3 exactly, lint missing for c3
    assert m["required_checks"]["ci"]["status"] == "passed"
    assert m["required_checks"]["lint"]["status"] == "missing"
    assert m["required_checks_covered"] is False
    d = base()
    d["checks"] = [{"name": "ci", "sha": S(4), "conclusion": "success"}, {"name": "lint", "sha": S(5), "conclusion": "success"}]
    f = br(analyze_trunk(d), "feat")
    assert f["required_checks"]["ci"] == {"status": "missing", "stale_ancestor_shas": [S(4)]}
    assert f["required_checks_covered"] is False
    # success on a descendant (or sibling) never covers either
    d["checks"] = [{"name": "ci", "sha": S(5), "conclusion": "success"}]
    m = br(analyze_trunk(d), "main")
    assert m["required_checks"]["ci"] == {"status": "missing", "stale_ancestor_shas": []}


@pytest.mark.parametrize("concl,status", [("success", "passed"), ("failure", "failed"), ("cancelled", "failed"),
                                          ("timed_out", "failed"), ("skipped", "not_success"), ("neutral", "not_success"),
                                          ("pending", "pending")])
def test_conclusion_mapping(concl, status):
    d = base(); d["checks"][0]["conclusion"] = concl
    f = br(analyze_trunk(d), "feat")
    assert f["required_checks"]["ci"]["status"] == status
    assert f["required_checks_covered"] is (status == "passed")


def test_unknown_conclusion_and_non_required_checks():
    d = base(); d["checks"][0]["conclusion"] = "green"
    assert msg(d) == "check ci@" + S(5) + " has unsupported conclusion 'green'"
    d = base(); d["checks"].append({"name": "extra", "sha": S(5), "conclusion": "failure"})
    f = br(analyze_trunk(d), "feat")
    assert f["required_checks_covered"] is True and "extra" not in f["required_checks"]


def test_failed_check_on_tip_with_older_success_is_failed():
    d = base()
    d["checks"] = [{"name": "ci", "sha": S(5), "conclusion": "failure"}, {"name": "ci", "sha": S(4), "conclusion": "success"},
                   {"name": "lint", "sha": S(5), "conclusion": "success"}]
    f = br(analyze_trunk(d), "feat")
    assert f["required_checks"]["ci"] == {"status": "failed", "stale_ancestor_shas": [S(4)]}
    assert f["required_checks_covered"] is False


def test_duplicate_check_records():
    d = base(); d["checks"].append(dict(d["checks"][0]))
    assert msg(d) == f"duplicate check record ci@{S(5)}"
    d = base(); d["checks"].append({**d["checks"][0], "conclusion": "failure"})
    assert msg(d) == f"conflicting duplicate check record ci@{S(5)}"
    d = base(); d["checks"][0]["sha"] = S(99)
    assert msg(d) == f"unknown sha {S(99)} in check ci"


def test_required_checks_validation():
    d = base(); d["required_checks"] = []
    assert msg(d) == "required_checks must be a non-empty list"
    d = base(); d["required_checks"] = ["ci", "ci"]
    assert msg(d) == "required_checks has duplicate name 'ci'"
    d = base(); d["required_checks"] = ["bad\nname"]
    assert msg(d) == "invalid check name 'bad\\nname'"


# ---------- threshold ----------
def test_threshold_equal_over_under():
    for age, thr, stale in ((20, 20, False), (20, 19.999, True), (20, 20.001, False)):
        d = base(); d["max_branch_age_hours"] = thr
        assert br(analyze_trunk(d), "feat")["stale"] is stale
    d = base(); d["commits"][3]["committed_at"] = T(24); d["commits"][4]["committed_at"] = T(10)
    assert br(analyze_trunk(d), "feat")["stale"] is False  # exactly 24h
    d["commits"][3]["committed_at"] = (lambda s: s)("2026-10-10T06:29:59Z")  # 24h + 1s
    r = analyze_trunk(d)
    assert br(r, "feat")["stale"] is True and br(r, "feat")["age_seconds"] == 24 * 3600 + 1
    assert r["stale_branches"] == ["feat"]


def test_threshold_validation():
    for v in (0, -1, True, "24", float("nan"), float("inf"), 8761, None):
        d = base(); d["max_branch_age_hours"] = v
        assert msg(d) == "max_branch_age_hours must be a finite number in (0, 8760]"


# ---------- timestamps ----------
def test_timezone_normalization():
    d = base(); d["reference_time"] = "2026-10-11T06:30:00Z"
    a = analyze_trunk(d)
    d["reference_time"] = "2026-10-11T12:00:00+05:30"
    b = analyze_trunk(d)
    d["reference_time"] = "2026-10-11T01:30:00-05:00"
    c = analyze_trunk(d)
    assert a == b == c
    assert a["reference_time"] == "2026-10-11T06:30:00Z"
    d = base(); d["commits"][3]["committed_at"] = "2026-10-11T07:30:00+05:30"  # 02:00Z -> 4.5h old
    d["commits"][4]["committed_at"] = T(1)
    f = br(analyze_trunk(d), "feat")
    assert f["oldest_unmerged_commit_at"] == "2026-10-11T02:00:00Z" and f["age_seconds"] == int(4.5 * 3600)
    d = base(); d["commits"][3]["committed_at"] = "2026-10-11T02:00:00.250Z"; d["commits"][4]["committed_at"] = T(1)
    assert br(analyze_trunk(d), "feat")["oldest_unmerged_commit_at"] == "2026-10-11T02:00:00.250000Z"


@pytest.mark.parametrize("bad", ["2026-10-11T06:30:00", "2026-10-11", "2026-10-11 06:30:00Z", "yesterday",
                                 "2026-10-11T06:30:00+0530", "2026-13-01T00:00:00Z", "2026-10-11T06:30:60Z",
                                 "", None, 5, "2026-10-11T24:00:00Z", "2026-10-11T06:30:00+24:00"])
def test_ambiguous_or_malformed_timestamps_refuse(bad):
    d = base(); d["reference_time"] = bad
    assert msg(d) == "timestamp reference_time must be ISO-8601 with explicit UTC offset"
    d = base(); d["commits"][0]["committed_at"] = bad
    assert msg(d) == f"timestamp commit {S(1)} committed_at must be ISO-8601 with explicit UTC offset"


def test_clock_consistency_refusals():
    d = base(); d["commits"][4]["committed_at"] = "2026-10-11T06:30:01Z"
    assert msg(d) == f"commit {S(5)} is after reference_time"
    d = base(); d["commits"][3]["committed_at"] = T(95)  # c4 older than parent c2 (90h)
    assert msg(d) == f"commit {S(4)} is older than its parent {S(2)} (ambiguous clock)"
    d = base(); d["commits"][4]["committed_at"] = T(20)  # equal to parent time is allowed
    analyze_trunk(d)
    d = base(); d["checks"][0]["completed_at"] = "2026-10-11T06:30:01Z"
    assert msg(d) == f"check ci@{S(5)} completed_at is after reference_time"
    d = base(); d["checks"][0]["completed_at"] = T(15)  # before commit c5 (10h ago)
    assert msg(d) == f"check ci@{S(5)} completed_at precedes its commit"
    d = base(); d["checks"][0]["completed_at"] = "2026-10-11T06:00:00"
    assert msg(d) == f"timestamp check ci@{S(5)} completed_at must be ISO-8601 with explicit UTC offset"


# ---------- graph errors ----------
def test_cycles_unknown_parents_duplicates():
    d = base(); d["commits"][0]["parents"] = [S(1)]
    assert msg(d) == "cycle detected in commit graph"
    d = base(); d["commits"][0]["parents"] = [S(5)]
    assert msg(d) == "cycle detected in commit graph"
    d = base(); d["commits"][1]["parents"] = [S(3)]; d["commits"][2]["parents"] = [S(2)]
    assert msg(d) == "cycle detected in commit graph"
    d = base(); d["commits"][1]["parents"] = [S(77)]
    assert msg(d) == f"unknown parent {S(77)} of commit {S(2)}"
    d = base(); d["commits"][1]["parents"] = [S(1), S(1)]
    assert msg(d) == f"duplicate parent {S(1)} in commit {S(2)}"
    d = base(); d["commits"].append(dict(d["commits"][1]))
    assert msg(d) == f"duplicate commit {S(2)}"
    d = base(); d["commits"].append({**d["commits"][1], "parents": []})
    assert msg(d) == f"conflicting duplicate commit {S(2)}"
    d = base(); d["branches"].append({"name": "feat", "tip": S(4)})
    assert msg(d) == "duplicate branch feat"
    d = base(); d["trunk"] = "master"
    assert msg(d) == "trunk branch master not in branches"
    d = base(); d["branches"][1]["tip"] = S(88)
    assert msg(d) == f"unknown tip {S(88)} for branch feat"
    d = base(); d["commits"][0]["sha"] = "ABC"
    assert msg(d) == "invalid sha 'ABC'"
    d = base(); d["commits"][0]["sha"] = S(1).upper().replace("0", "A")
    assert "invalid sha" in msg(d)


def test_unknown_keys_and_protection_claims_refused():
    d = base(); d["protected"] = True
    assert msg(d) == "unknown key 'protected' in request"
    d = base(); d["branches"][0]["protected"] = True
    assert msg(d) == "unknown key 'protected' in branch main"
    d = base(); d["commits"][0]["signed"] = True
    assert msg(d) == f"unknown key 'signed' in commit {S(1)}"
    d = base(); d["checks"][0]["required"] = True
    assert msg(d) == f"unknown key 'required' in check ci@{S(5)}"
    r = analyze_trunk(base())
    assert r["branch_protection_verified"] is False and r["main_mutated"] is False
    assert any("branch protection" in x for x in r["limits"])


def test_non_dict_and_missing_fields():
    for bad in (None, [], "x", 3):
        assert msg(bad) == "request must be an object"
    d = base(); del d["source_ref"]
    assert msg(d) == "source_ref must be a non-blank string"
    d = base(); d["commits"] = []
    assert msg(d) == "commits must be a non-empty list"
    d = base(); d["branches"] = "x"
    assert msg(d) == "branches must be a non-empty list"
    d = base(); d["checks"] = None
    assert msg(d) == "checks must be a list"
    d = base(); d["commits"][0]["parents"] = "x"
    assert msg(d) == f"parents of commit {S(1)} must be a list"
    d = base(); d["commits"][0] = "x"
    assert msg(d) == "commit 0 must be an object"
    d = base(); d["branches"][0]["name"] = "bad name"
    assert msg(d) == "invalid branch name 'bad name'"


# ---------- bounds N / N+1 ----------
def _chain(n):
    return [C(i + 1, [i] if i else [], 100 - 0.0 * i) for i in range(n)]


def test_commit_count_bound():
    n = mod.MAX_COMMITS
    d = base()
    d["commits"] = [{"sha": S(i + 1), "parents": [S(i)] if i else [], "committed_at": T(100)} for i in range(n)]
    d["branches"] = [{"name": "main", "tip": S(n)}]
    d["checks"] = []
    r = analyze_trunk(d)
    assert r["trunk"]["commit_count"] == n
    d["commits"].append({"sha": S(n + 1), "parents": [S(n)], "committed_at": T(100)})
    assert msg(d) == f"commits exceed {n}"


def test_other_count_bounds():
    n = mod.MAX_BRANCHES
    d = base(); d["branches"] = [{"name": f"b{i}", "tip": S(3)} for i in range(n - 1)] + [{"name": "main", "tip": S(3)}]
    analyze_trunk(d)
    d["branches"].append({"name": "extra", "tip": S(3)})
    assert msg(d) == f"branches exceed {n}"
    n = mod.MAX_CHECKS
    d = base(); d["required_checks"] = ["ci"]
    d["checks"] = [{"name": f"c{i}", "sha": S(5), "conclusion": "success"} for i in range(n)]
    analyze_trunk(d)
    d["checks"].append({"name": "cX", "sha": S(5), "conclusion": "success"})
    assert msg(d) == f"checks exceed {n}"
    n = mod.MAX_REQUIRED
    d = base(); d["required_checks"] = [f"r{i}" for i in range(n)]; d["checks"] = []
    analyze_trunk(d)
    d["required_checks"].append("rX")
    assert msg(d) == f"required_checks exceed {n}"
    n = mod.MAX_PARENTS
    d = base(); d["commits"] = [C(i, [], 100) for i in range(1, n + 2)] + [C(50, list(range(1, n + 1)), 10)]
    d["branches"] = [{"name": "main", "tip": S(50)}]; d["checks"] = []
    analyze_trunk(d)
    d["commits"][-1]["parents"].append(S(n + 1))
    assert msg(d) == f"commit {S(50)} parents exceed {n}"
    n = mod.MAX_NAME
    d = base(); d["branches"][1]["name"] = "a" * n
    analyze_trunk(d)
    d["branches"][1]["name"] = "a" * (n + 1)
    assert msg(d) == f"invalid branch name '{'a' * (n + 1)}'"


# ---------- determinism / hygiene ----------
def test_order_invariance_and_determinism():
    d = base(); d["commits"].append(C(6, [3, 5], 5))
    r = analyze_trunk(d)
    rnd = random.Random(7)
    for _ in range(10):
        e = copy.deepcopy(d)
        rnd.shuffle(e["commits"]); rnd.shuffle(e["branches"]); rnd.shuffle(e["checks"]); rnd.shuffle(e["required_checks"])
        assert analyze_trunk(e) == r
    assert json.dumps(r, sort_keys=True) == json.dumps(analyze_trunk(d), sort_keys=True)
    tr = r["source_trace"]
    assert tr == sorted(tr, key=lambda t: (t["kind"], t["id"]))
    assert {t["kind"] for t in tr} == {"commit", "branch", "check"}
    assert all(t["source_ref"] == "audit/repo-snapshot-1" for t in tr)


def test_record_source_ref_override_and_input_not_mutated():
    d = base(); d["branches"][1]["source_ref"] = "gh/branch-feat"
    snap = copy.deepcopy(d)
    r = analyze_trunk(d)
    assert d == snap
    assert {"kind": "branch", "id": "feat", "source_ref": "gh/branch-feat"} in r["source_trace"]
    r["branches"][0]["name"] = "x"
    assert d["branches"][0]["name"] == "main"


def test_sensitive_to_observed_graph():
    d = base(); d["commits"][3]["parents"] = [S(3)]  # feature now branches from c3
    f = br(analyze_trunk(d), "feat")
    assert (f["ahead"], f["behind"], f["merge_bases"], f["state"]) == (2, 0, [S(3)], "ahead")


# ---------- exhaustive finite DAG oracle ----------
def _oracle(parents, a, b):
    """Independent naive implementation using explicit DFS ancestor sets."""
    def anc(x):
        seen, st = set(), [x]
        while st:
            y = st.pop()
            if y in seen:
                continue
            seen.add(y); st.extend(parents[y])
        return seen
    A, B = anc(a), anc(b)
    common = A & B
    bases = sorted(c for c in common if not any(c != d and c in anc(d) for d in common))
    return len(A - B), len(B - A), bases


def test_exhaustive_dag_oracle_up_to_5_nodes():
    cases = 0
    for n in range(1, 6):
        subsets = [[list(c) for k in range(i + 1) for c in itertools.combinations(range(i), k)] for i in range(n)]
        for parents in itertools.product(*subsets):
            par = {i: list(p) for i, p in enumerate(parents)}
            commits = [{"sha": S(i + 1), "parents": [S(p + 1) for p in par[i]], "committed_at": T(100 - i)} for i in range(n)]
            commits.reverse()
            for trunk_tip in range(n):
                for tip in range(n):
                    d = {"source_ref": "x", "trunk": "main", "reference_time": REF, "max_branch_age_hours": 1000,
                         "required_checks": ["ci"], "commits": commits,
                         "branches": [{"name": "main", "tip": S(trunk_tip + 1)}, {"name": "b", "tip": S(tip + 1)}],
                         "checks": []}
                    r = analyze_trunk(d)
                    b = br(r, "b")
                    ahead_n, behind_n, bases = _oracle(par, tip, trunk_tip)
                    assert (b["ahead"], b["behind"]) == (ahead_n, behind_n), (par, trunk_tip, tip)
                    assert b["merge_bases"] == [S(x + 1) for x in bases], (par, trunk_tip, tip)
                    state = ("merged" if ahead_n == 0 else "unrelated" if not bases
                             else "diverged" if behind_n else "ahead")
                    assert b["state"] == state, (par, trunk_tip, tip, b["state"])
                    cases += 1
    assert cases > 20000


# ================================================================ R2 audit pins (tests only; runtime unchanged)
def test_source_ref_length_guard_top_commit_branch_check_200_ok_201_refused():
    ok, bad = "r" * 200, "r" * 201
    d = base(); d["source_ref"] = ok
    analyze_trunk(d)
    d["source_ref"] = bad
    assert msg(d) == "source_ref exceeds 200 characters"
    d = base(); d["commits"][0]["source_ref"] = ok
    analyze_trunk(d)
    d["commits"][0]["source_ref"] = bad
    assert msg(d) == f"commit {S(1)} source_ref exceeds 200 characters"
    d = base(); d["branches"][1]["source_ref"] = ok
    analyze_trunk(d)
    d["branches"][1]["source_ref"] = bad
    assert msg(d) == "branch feat source_ref exceeds 200 characters"
    d = base(); d["checks"][0]["source_ref"] = ok
    analyze_trunk(d)
    d["checks"][0]["source_ref"] = bad
    assert msg(d) == f"check ci@{S(5)} source_ref exceeds 200 characters"
    d = base(); d["source_ref"] = "x" * 199 + "é"  # 200 characters, 201 bytes: the limit counts characters
    analyze_trunk(d)


@pytest.mark.parametrize("trunk", [5, None, "", "a" * 101, "bad name", "ma!n", ["main"], True])
def test_invalid_trunk_name_has_its_own_diagnostic(trunk):
    d = base(); d["trunk"] = trunk
    assert msg(d) == f"invalid trunk name {trunk!r}"


def test_trunk_name_100_chars_ok_and_unknown_valid_trunk_is_a_different_error():
    d = base(); d["trunk"] = "t" * 100; d["branches"][0]["name"] = "t" * 100
    assert analyze_trunk(d)["trunk"]["name"] == "t" * 100
    d = base(); d["trunk"] = "release/1.x_y-z"
    assert msg(d) == "trunk branch release/1.x_y-z not in branches"


def test_required_checks_cap_exact_with_message():
    n = mod.MAX_REQUIRED
    d = base(); d["required_checks"] = [f"r{i}" for i in range(n)]; d["checks"] = []
    assert len(analyze_trunk(d)["trunk"]["required_checks"]) == n
    d["required_checks"].append("rX")
    assert msg(d) == f"required_checks exceed {n}"
    d["required_checks"] = [f"r{i}" for i in range(n)] + [5]
    assert msg(d) == f"required_checks exceed {n}"  # the cap is checked before element validation


def test_malformed_branch_and_check_objects_have_specific_diagnostics():
    for bad in (None, "main", 5, ["main"]):
        d = base(); d["branches"].append(bad)
        assert msg(d) == "branch must be an object"
        d = base(); d["checks"].append(bad)
        assert msg(d) == "check must be an object"
        d = base(); d["commits"].append(bad)
        assert msg(d).startswith("commit ") and msg(d).endswith("must be an object")


@pytest.mark.parametrize("name", [None, 5, "", "a" * 101, "bad\nname", "bad;name", ["ci"]])
def test_invalid_check_record_name_diagnostic(name):
    d = base(); d["checks"][0]["name"] = name
    assert msg(d) == f"invalid check name {name!r}"


def test_check_name_100_chars_ok_and_spaces_allowed_in_checks_not_branches():
    d = base(); d["checks"][0]["name"] = "c" * 100
    analyze_trunk(d)
    d = base(); d["checks"][0]["name"] = "ci job"
    analyze_trunk(d)
    d = base(); d["branches"][1]["name"] = "feat x"
    assert msg(d) == "invalid branch name 'feat x'"


@pytest.mark.parametrize("tz", ["+00:60", "+05:60", "+10:99", "-00:60", "-23:75", "+24:00", "-24:00", "+23:60", "+99:00"])
def test_timezone_offset_components_out_of_range_refused(tz):
    d = base(); d["reference_time"] = "2026-10-11T12:00:00" + tz
    assert msg(d) == "timestamp reference_time must be ISO-8601 with explicit UTC offset"
    d = base(); d["commits"][0]["committed_at"] = "2026-07-01T00:00:00" + tz
    assert msg(d) == f"timestamp commit {S(1)} committed_at must be ISO-8601 with explicit UTC offset"


@pytest.mark.parametrize("ref,utc", [("2026-10-12T12:00:00+23:59", "2026-10-11T12:01:00Z"), ("2026-10-11T12:00:00-23:59", "2026-10-12T11:59:00Z"),
                                     ("2026-10-11T12:00:00+00:59", "2026-10-11T11:01:00Z"), ("2026-10-11T12:00:00-00:00", "2026-10-11T12:00:00Z"),
                                     ("2026-10-11T20:00:00+14:00", "2026-10-11T06:00:00Z")])
def test_timezone_offset_component_edges_accepted(ref, utc):
    d = base(); d["reference_time"] = ref
    assert analyze_trunk(d)["reference_time"] == utc


def age_case(ts):
    """feature branch whose only unique commit is stamped `ts`; reference time is 06:30:00Z."""
    d = base()
    d["commits"] = [C(1, [], 100), C(2, [1], 90), C(3, [2], 30), {"sha": S(4), "parents": [S(2)], "committed_at": ts}]
    d["branches"] = [{"name": "main", "tip": S(3)}, {"name": "feat", "tip": S(4)}]
    d["checks"] = []
    d["max_branch_age_hours"] = 8760
    return br(analyze_trunk(d), "feat")


@pytest.mark.parametrize("ts,age", [("2026-10-11T06:30:00Z", 0), ("2026-10-11T06:29:59Z", 1), ("2026-10-11T05:30:00Z", 3600),
                                    ("2026-10-09T03:29:55Z", 2 * 86400 + 3 * 3600 + 5)])
def test_whole_second_ages_are_integers(ts, age):
    got = age_case(ts)["age_seconds"]
    assert got == age and type(got) is int


@pytest.mark.parametrize("ts,age", [("2026-10-11T06:29:59.750000Z", 0.25), ("2026-10-11T06:29:59.999999Z", 0.000001),
                                    ("2026-10-11T06:29:58.999999Z", 1.000001), ("2026-10-11T06:29:59.5Z", 0.5),
                                    ("2026-10-09T03:29:55.5Z", 2 * 86400 + 3 * 3600 + 4.5), ("2026-10-11T06:29:59.000001Z", 0.999999),
                                    ("2026-10-10T06:29:59.000001Z", 86400.999999)])
def test_fractional_ages_keep_microsecond_precision_as_float(ts, age):
    got = age_case(ts)["age_seconds"]
    assert type(got) is float and got == age


def test_fractional_age_beyond_a_second_is_not_truncated_or_rounded():
    got = age_case("2026-10-11T06:00:00.123456Z")["age_seconds"]
    assert got == 1799.876544 and got != 1799 and got != 1800


def test_trunk_summary_comes_from_the_trunk_branch_not_another_branch():
    d = base()  # main: ci passed, lint missing; feat: ci and lint passed
    r = analyze_trunk(d)
    assert r["trunk"]["required_checks_covered"] is False
    assert r["trunk"]["required_checks"] == br(r, "main")["required_checks"]
    assert r["trunk"]["required_checks"]["ci"]["status"] == "passed" and r["trunk"]["required_checks"]["lint"]["status"] == "missing"
    assert r["trunk"]["required_checks"] != br(r, "feat")["required_checks"]
    assert r["trunk"]["tip"] == S(3) and r["trunk"]["commit_count"] == 3
    d = base(); d["checks"] += [{"name": "lint", "sha": S(3), "conclusion": "success"}, {"name": "ci", "sha": S(5), "conclusion": "failure"}]
    d["checks"] = [c for c in d["checks"] if not (c["name"] == "ci" and c["sha"] == S(5) and c["conclusion"] == "success")]
    r = analyze_trunk(d)
    assert r["trunk"]["required_checks_covered"] is True and br(r, "feat")["required_checks_covered"] is False
    # trunk name sorting after other branches and before them
    for tname in ("aaa-trunk", "zzz-trunk"):
        d = base(); d["trunk"] = tname; d["branches"][0]["name"] = tname
        r = analyze_trunk(d)
        assert r["trunk"]["name"] == tname and r["trunk"]["required_checks"] == br(r, tname)["required_checks"]
        assert r["trunk"]["tip"] == S(3) and br(r, tname)["state"] == "trunk"


@pytest.mark.parametrize('field',['sha','parent','tip','branch','trunk','required_check','check_name','check_sha','reference_time','committed_at','completed_at'])
def test_trailing_newline_rejected_at_field(field):
 d=base()
 if field=='sha':d['commits'][0]['sha']+='\n';prefix='invalid sha '
 elif field=='parent':d['commits'][1]['parents'][0]+='\n';prefix='invalid sha '
 elif field=='tip':d['branches'][1]['tip']+='\n';prefix='invalid sha '
 elif field=='branch':d['branches'][1]['name']+='\n';prefix='invalid branch name '
 elif field=='trunk':d['trunk']+='\n';prefix='invalid trunk name '
 elif field=='required_check':d['required_checks'][0]+='\n';prefix='invalid check name '
 elif field=='check_name':d['checks'][0]['name']+='\n';prefix='invalid check name '
 elif field=='check_sha':d['checks'][0]['sha']+='\n';prefix='invalid sha '
 elif field=='reference_time':d['reference_time']+='\n';prefix='timestamp reference_time '
 elif field=='committed_at':d['commits'][0]['committed_at']+='\n';prefix='timestamp commit '+S(1)+' committed_at '
 else:d['checks'][0]['completed_at']=T(1)+'\n';prefix='timestamp check ci@'+S(5)+' completed_at '
 assert msg(d).startswith(prefix)


@pytest.mark.parametrize('field',['reference_time','committed_at','completed_at'])
@pytest.mark.parametrize('zero',['\u0660','\uff10'])
def test_timestamp_ascii_digits_only(field,zero):
 d=base();value=T(1).replace('0',zero)
 if field=='reference_time':d[field]=value;prefix='timestamp reference_time '
 elif field=='committed_at':d['commits'][0][field]=value;prefix='timestamp commit '+S(1)+' committed_at '
 else:d['checks'][0][field]=value;prefix='timestamp check ci@'+S(5)+' completed_at '
 assert msg(d).startswith(prefix)


def test_stale_ancestor_records_include_any_conclusion():
 d=base();d['checks'].append({'name':'ci','sha':S(2),'conclusion':'failure'})
 result=analyze_trunk(d)
 assert S(2) in br(result,'feat')['required_checks']['ci']['stale_ancestor_shas']


# ---------- boundary and exact-output pins
class TestBoundaryPins:
    def test_caps_commits_2000_accepted_2001_refused(self):
        d = {"source_ref": "s", "trunk": "main", "reference_time": REF,
             "max_branch_age_hours": 24, "required_checks": ["ci"],
             "commits": [{"sha": S(i), "parents": [S(i - 1)] if i > 1 else [], "committed_at": T(100)}
                         for i in range(1, 2001)],
             "branches": [{"name": "main", "tip": S(2000)}], "checks": []}
        assert analyze_trunk(d)["trunk"]["commit_count"] == 2000
        d["commits"] = d["commits"] + [{"sha": S(2001), "parents": [S(2000)], "committed_at": T(100)}]
        assert msg(d) == "commits exceed 2000"

    def test_caps_branches_64_accepted_65_refused(self):
        d = base()
        d["branches"] = [{"name": "main", "tip": S(3)}] + [{"name": f"b{i:02d}", "tip": S(3)} for i in range(63)]
        assert len(analyze_trunk(d)["branches"]) == 64
        d["branches"].append({"name": "b63", "tip": S(3)})
        assert msg(d) == "branches exceed 64"

    def test_caps_checks_512_accepted_513_refused(self):
        d = base()
        d["checks"] = [{"name": f"c{i:03d}", "sha": S(5), "conclusion": "success"} for i in range(512)]
        r = analyze_trunk(d)
        assert len([t for t in r["source_trace"] if t["kind"] == "check"]) == 512
        d["checks"].append({"name": "c512", "sha": S(5), "conclusion": "success"})
        assert msg(d) == "checks exceed 512"

    def test_caps_required_16_accepted_17_refused(self):
        d = base(); d["required_checks"] = [f"r{i:02d}" for i in range(16)]
        assert len(analyze_trunk(d)["trunk"]["required_checks"]) == 16
        d["required_checks"] = [f"r{i:02d}" for i in range(17)]
        assert msg(d) == "required_checks exceed 16"

    def test_caps_parents_8_accepted_9_refused(self):
        kids = [C(i, [], 100 - i) for i in range(1, 9)]
        d = {"source_ref": "s", "trunk": "main", "reference_time": REF,
             "max_branch_age_hours": 24, "required_checks": ["ci"],
             "commits": kids + [C(9, list(range(1, 9)), 10)],
             "branches": [{"name": "main", "tip": S(9)}], "checks": []}
        assert analyze_trunk(d)["trunk"]["tip"] == S(9)
        d["commits"] = kids + [C(8, [], 50)] * 0 + [C(8, [], 50), C(9, list(range(1, 9)) + [8], 10)] \
            if False else kids + [C(9, list(range(1, 10)), 10)]
        assert msg(d) == f"commit {S(9)} parents exceed 8"

    def test_limits_block_is_the_exact_five_strings(self):
        assert analyze_trunk(base())["limits"] == [
            "Analyzes only the supplied commit, branch and check records; nothing is read from git or GitHub, so record accuracy is the caller's claim.",
            "Does not verify, enable or change GitHub branch protection or any protected-branch rule; branch_protection_verified is always false and trunk is never mutated.",
            "Branch age is reference_time minus the oldest commit unique to the branch (not branch creation time); commit timestamps are caller-supplied author/committer claims.",
            "Check coverage is exact-SHA only: a pass on an ancestor, descendant or sibling never covers a tip. Check provenance and runner trust are not verified.",
            "Not a merge-readiness or release decision; human review is still required.",
        ]

    def test_branch_age_threshold_zero_refused_positive_accepted(self):
        for ok in (1, 0.5):
            d = base(); d["max_branch_age_hours"] = ok
            assert analyze_trunk(d)["branches"]
        d = base(); d["max_branch_age_hours"] = 0
        assert msg(d) == "max_branch_age_hours must be a finite number in (0, 8760]"

    def test_stale_boundary_at_exactly_one_hour(self):
        d = base(); d["max_branch_age_hours"] = 1
        # feat has exactly one unmerged commit; age is measured from it
        d["commits"] = d["commits"][:3] + [{"sha": S(9), "parents": [S(2)], "committed_at": "2026-10-11T05:30:00Z"}]
        d["branches"] = [{"name": "main", "tip": S(3)}, {"name": "feat", "tip": S(9)}]
        d["checks"] = [c for c in d["checks"] if c["sha"] == S(3)]
        assert br(analyze_trunk(d), "feat")["stale"] is False        # exactly 3600s old: not stale
        d["commits"][3]["committed_at"] = "2026-10-11T05:29:59.999999Z"
        r = analyze_trunk(d)
        assert br(r, "feat")["stale"] is True and r["stale_branches"] == ["feat"]   # 1us more: stale

    def test_duplicate_required_check_message_names_the_duplicated_name(self):
        d = base(); d["required_checks"] = ["a", "b", "b"]
        assert msg(d) == "required_checks has duplicate name 'b'"

    def test_duplicate_parent_message_names_the_duplicated_parent(self):
        d = {"source_ref": "s", "trunk": "main", "reference_time": REF,
             "max_branch_age_hours": 24, "required_checks": ["ci"],
             "commits": [C(1, [], 100), C(2, [], 90), C(3, [1, 2, 2], 30)],
             "branches": [{"name": "main", "tip": S(3)}], "checks": []}
        assert msg(d) == f"duplicate parent {S(2)} in commit {S(3)}"

    def test_check_completed_at_equal_to_reference_time_accepted(self):
        d = base()
        d["checks"][0]["completed_at"] = "2026-10-11T06:30:00Z"   # == REF (06:30:00Z)
        assert analyze_trunk(d)["branches"]
        d["checks"][0]["completed_at"] = "2026-10-11T06:30:00.000001Z"
        assert msg(d) == f"check ci@{S(5)} completed_at is after reference_time"

    def test_check_completed_at_equal_to_commit_time_accepted(self):
        d = base()
        d["checks"][0]["completed_at"] = T(10)                    # == c5 committed_at
        assert analyze_trunk(d)["branches"]
        from datetime import datetime, timedelta, timezone
        earlier = (datetime(2026, 10, 10, 20, 30, tzinfo=timezone.utc) - timedelta(microseconds=1))
        d["checks"][0]["completed_at"] = earlier.strftime("%Y-%m-%dT%H:%M:%S") + ".999999Z"
        assert msg(d) == f"check ci@{S(5)} completed_at precedes its commit"

    def test_check_trace_id_is_name_at_sha(self):
        r = analyze_trunk(base())
        assert {"kind": "check", "id": f"ci@{S(5)}", "source_ref": "audit/repo-snapshot-1"} in r["source_trace"]

    def test_branch_dict_exact_shape(self):
        f = br(analyze_trunk(base()), "feat")
        assert f == {
            "name": "feat", "tip": S(5), "state": "diverged", "ahead": 2, "behind": 1,
            "merge_bases": [S(2)], "unmerged_commits": [S(4), S(5)],
            "merge_commits_in_unmerged": [], "oldest_unmerged_commit_at": T(20),
            "age_seconds": 72000, "stale": False,
            "required_checks": {"ci": {"status": "passed", "stale_ancestor_shas": []},
                                "lint": {"status": "passed", "stale_ancestor_shas": []}},
            "required_checks_covered": True,
        }

    def test_unreachable_commit_with_smallest_sha_is_reported(self):
        d = base(); d["commits"].append(C(0, [], 50))
        assert analyze_trunk(d)["unreachable_commits"] == [S(0)]
