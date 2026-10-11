"""Tests for ledger row 690 (Code Review) engine. Stdlib + pytest only."""
import importlib.util
import pathlib

import pytest

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "backend/app/modules/m20_general_cognitive_worker/code_review690.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("code_review690", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = _load()


def mkdiff(path, added, removed=(), start=1):
    body = [f"-{r}" for r in removed] + [f"+{a}" for a in added]
    return (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        f"@@ -{start},{len(removed)} +{start},{len(added)} @@\n" + "\n".join(body) + "\n"
    )


CLEAN = mkdiff("src/a.py", ["def f(x):", "    return x + 1"]) + mkdiff(
    "tests/test_a.py", ["def test_f():", "    assert True"]
)


def rules(report):
    return {f["rule"] for f in report["findings"]}


def test_parse_tracks_line_numbers_and_counts():
    files = cr.parse_unified_diff(mkdiff("a.py", ["x", "y"], ["old"], start=10))
    assert files[0]["path"] == "a.py"
    assert files[0]["added"] == [(10, "x"), (11, "y")]
    assert files[0]["removed"] == 1


def test_parse_rejects_malformed():
    with pytest.raises(cr.CodeReviewError):
        cr.parse_unified_diff("not a diff")
    with pytest.raises(cr.CodeReviewError):
        cr.parse_unified_diff("--- a/x\n+++ b/x\n@@ bad @@\n+x\n")
    # hunk header claims 3 added lines but only 1 present
    with pytest.raises(cr.CodeReviewError):
        cr.parse_unified_diff("--- a/x\n+++ b/x\n@@ -1,0 +1,3 @@\n+x\n")


def test_clean_diff_has_no_findings():
    r = cr.review(CLEAN, ["correctness"], author="alice")
    assert r["findings"] == []
    assert r["decision"] == "no_issues_found"
    assert r["human_review_required"] is True


def test_secret_is_blocking_and_value_not_echoed():
    d = mkdiff("src/c.py", ['password = "hunter2hunter2"'])
    r = cr.review(d, [], author="a")
    f = [x for x in r["findings"] if x["rule"] == "hardcoded-secret"][0]
    assert f["severity"] == "blocking" and f["line"] == 1 and f["path"] == "src/c.py"
    assert "hunter2" not in repr(r)
    assert r["decision"] == "request_changes"


def test_each_rule_fires_on_its_trigger():
    cases = {
        "bare-except": "except:",
        "debug-leftover": "    print(x)",
        "todo-marker": "# TODO fix",
        "trailing-whitespace": "x = 1   ",
        "long-line": "x = '" + "a" * 130 + "'",
        "conflict-marker": "<<<<<<< HEAD",
        "dynamic-exec": "    eval(user)",
    }
    for rule, line in cases.items():
        r = cr.review(mkdiff("tests/t.py", [line]), [], author="a")
        assert rule in rules(r), rule


def test_rules_only_look_at_added_lines():
    d = mkdiff("tests/t.py", ["ok = 1"], removed=["print(1)", "# TODO x"])
    assert cr.review(d, [], author="a")["findings"] == []


def test_source_without_tests_flagged_and_tests_change_clears_it():
    only_src = mkdiff("src/a.py", ["x = 1"])
    assert "missing-tests" in rules(cr.review(only_src, [], author="a"))
    assert "missing-tests" not in rules(cr.review(CLEAN, [], author="a"))
    docs_only = mkdiff("README.md", ["hi"])
    assert "missing-tests" not in rules(cr.review(docs_only, [], author="a"))


def test_oversized_change_flagged_with_threshold():
    d = mkdiff("tests/t.py", [f"v{i} = {i}" for i in range(30)])
    assert "oversized-change" in rules(cr.review(d, [], author="a", max_added_lines=20))
    assert "oversized-change" not in rules(cr.review(d, [], author="a", max_added_lines=30))


def test_checklist_results_and_unknown_items_need_human():
    d = mkdiff("src/a.py", ["print(1)"])
    r = cr.review(d, ["no debug code", "correctness", "tests"], author="a")
    res = {c["item"]: c["status"] for c in r["checklist"]}
    assert res["no debug code"] == "fail"
    assert res["tests"] == "fail"
    assert res["correctness"] == "needs_human"


def test_checklist_pass_when_rule_clear():
    r = cr.review(CLEAN, ["no debug code", "tests"], author="a")
    assert {c["status"] for c in r["checklist"]} == {"pass"}


def test_self_approval_forbidden():
    with pytest.raises(cr.SelfApprovalError):
        cr.review(CLEAN, [], author="alice", reviewer="Alice ", requested_decision="approve")


def test_approval_requires_reviewer_and_no_blockers():
    with pytest.raises(cr.CodeReviewError):
        cr.review(CLEAN, [], author="a", requested_decision="approve")
    bad = mkdiff("src/c.py", ["api_key = 'abcdefgh12345'"])
    r = cr.review(bad, [], author="a", reviewer="b", requested_decision="approve")
    assert r["decision"] == "request_changes" and r["approval"] is None
    assert r["unresolved_blockers"]


def test_valid_approval_recorded_but_not_merge():
    r = cr.review(CLEAN, [], author="a", reviewer="b", requested_decision="approve")
    assert r["decision"] == "approved_by_reviewer"
    assert r["approval"] == {"reviewer": "b", "author": "a"}
    assert "No merge" in r["boundary"]


def test_invalid_inputs():
    with pytest.raises(cr.CodeReviewError):
        cr.review(CLEAN, [], author="")
    with pytest.raises(cr.CodeReviewError):
        cr.review(CLEAN, "correctness", author="a")
    with pytest.raises(cr.CodeReviewError):
        cr.review(CLEAN, [], author="a", reviewer="b", requested_decision="merge")


def test_deterministic_and_input_hash():
    a = cr.review(CLEAN, ["x"], author="a")
    b = cr.review(CLEAN, ["x"], author="a")
    assert a == b and len(a["input_sha256"]) == 64
    assert cr.review(CLEAN + "\n", ["x"], author="a")["input_sha256"] != a["input_sha256"]


def test_secret_needs_min_length_literal():
    assert "hardcoded-secret" not in rules(cr.review(mkdiff("tests/t.py", ['token = "short"']), [], author="a"))
    assert "hardcoded-secret" in rules(cr.review(mkdiff("tests/t.py", ['token = "12345678"']), [], author="a"))


def test_long_line_boundary_is_exclusive():
    ok = "x" * 120
    assert "long-line" not in rules(cr.review(mkdiff("tests/t.py", [ok]), [], author="a"))
    assert "long-line" in rules(cr.review(mkdiff("tests/t.py", [ok + "y"]), [], author="a"))


def test_bare_except_regex_is_specific():
    for line in ["exceptional = 1", "except ValueError:", "# except", "x = 'except'"]:
        assert "bare-except" not in rules(cr.review(mkdiff("tests/t.py", [line]), [], author="a")), line


def test_warning_only_gives_comments_only_decision():
    r = cr.review(mkdiff("tests/t.py", ["# TODO later"]), [], author="a")
    assert r["decision"] == "comments_only" and r["unresolved_blockers"] == []
