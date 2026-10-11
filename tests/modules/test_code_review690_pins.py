"""Boundary pins for the code review engine (tests only; core unchanged)."""
import importlib.util
import pathlib
import sys

import pytest

MODULE_PATH = (pathlib.Path(__file__).resolve().parents[2]
               / "backend/app/modules/m20_general_cognitive_worker/code_review690.py")
_spec = importlib.util.spec_from_file_location("code_review690_pins", MODULE_PATH)
cr = importlib.util.module_from_spec(_spec)
sys.modules["code_review690_pins"] = cr
_spec.loader.exec_module(cr)


def hdr(path):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"


def rules(report):
    return {f["rule"] for f in report["findings"]}


# ---- parser input validation
@pytest.mark.parametrize("bad", [None, 123, b"@@ -1 +1 @@\n+x\n", ["@@"], "no hunk marker here", ""])
def test_parse_rejects_non_text_or_hunkless_with_contract_error(bad):
    with pytest.raises(cr.CodeReviewError):
        cr.parse_unified_diff(bad)


def test_diff_without_file_sections_raises():
    with pytest.raises(cr.CodeReviewError):
        cr.parse_unified_diff("@@ -1 +1 @@\n+x\n")      # hunk before any file header


# ---- hunk header default and explicit counts
def test_omitted_counts_default_to_one():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -5 +5 @@\n-old\n+new\n")[0]
    assert f["added"] == [(5, "new")] and f["removed"] == 1


def test_explicit_counts_are_used_not_start_numbers():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -7,2 +9,3 @@\n-a\n-b\n+x\n+y\n+z\n")[0]
    assert f["added"] == [(9, "x"), (10, "y"), (11, "z")] and f["removed"] == 2
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -7,2 +9,1 @@\n-a\n-b\n+x\n")[0]
    assert f["added"] == [(9, "x")] and f["removed"] == 2


def test_explicit_zero_counts_are_zero_not_default():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -0,0 +1,2 @@\n+a\n+b\n")[0]
    assert f["added"] == [(1, "a"), (2, "b")] and f["removed"] == 0
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -1,2 +0,0 @@\n-a\n-b\n")[0]
    assert f["added"] == [] and f["removed"] == 2


def test_single_count_mismatch_each_side_raises():
    for body in ("@@ -1,2 +1 @@\n-a\n+x\n", "@@ -1 +1,2 @@\n-a\n+x\n", "@@ -1,0 +1,0 @@\n+x\n", "@@ -1,0 +1,0 @@\n-x\n"):
        with pytest.raises(cr.CodeReviewError):
            cr.parse_unified_diff(hdr("a.py") + body)


# ---- lines that look like headers inside an incomplete hunk are content
def test_dash_and_plus_header_lookalikes_inside_hunk_are_content():
    d = hdr("a.py") + "@@ -1 +1 @@\n--- removed-looking\n+++ added-looking\n"
    f = cr.parse_unified_diff(d)[0]
    assert f["removed"] == 1 and f["added"] == [(1, "++ added-looking")]


def test_each_header_kind_after_complete_hunk_starts_new_file():
    base = hdr("a.py") + "@@ -1 +1 @@\n-o\n+n\n"
    two = base + hdr("b.py") + "@@ -1 +1 @@\n-o2\n+n2\n"
    f = cr.parse_unified_diff(two)
    assert [x["path"] for x in f] == ["a.py", "b.py"] and f[1]["added"] == [(1, "n2")]
    no_diff_line = base + "--- a/c.py\n+++ b/c.py\n@@ -1 +1 @@\n-o3\n+n3\n"
    assert [x["path"] for x in cr.parse_unified_diff(no_diff_line)] == ["a.py", "c.py"]
    plus_only = base + "+++ b/d.py\n@@ -1 +1 @@\n-o4\n+n4\n"
    assert [x["path"] for x in cr.parse_unified_diff(plus_only)] == ["a.py", "d.py"]
    dash_only = base + "--- a/e.py\n"
    f = cr.parse_unified_diff(dash_only)
    assert [x["path"] for x in f] == ["a.py"] and f[0]["removed"] == 1 and f[0]["added"] == [(1, "n")]
    diff_only = base + "diff --git a/f b/f\n"
    f = cr.parse_unified_diff(diff_only)
    assert [x["path"] for x in f] == ["a.py"] and f[0]["added"] == [(1, "n")]


def test_stray_lines_between_file_header_and_hunk_are_ignored():
    d = "--- a/x.py\n+++ b/x.py\n+stray added-looking line\n-stray removed-looking\n@@ -1 +1 @@\n-o\n+n\n"
    f = cr.parse_unified_diff(d)[0]
    assert f["added"] == [(1, "n")] and f["removed"] == 1


def test_no_newline_marker_line_ignored():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -1 +1 @@\n-o\n\\ No newline at end of file\n+n\n")[0]
    assert f["added"] == [(1, "n")] and f["removed"] == 1


def test_path_without_b_prefix_kept_and_prefix_stripped():
    assert cr.parse_unified_diff("--- a/x\n+++ b/dir/x.py\n@@ -1 +1 @@\n+n\n-o\n")[0]["path"] == "dir/x.py"
    assert cr.parse_unified_diff("--- x\n+++ dir/x.py\n@@ -1 +1 @@\n+n\n-o\n")[0]["path"] == "dir/x.py"


# ---- review() signature and defaults
def test_signature_keyword_only_after_checklist():
    with pytest.raises(TypeError):
        cr.review("@@", [], "alice")
    d = hdr("tests/t.py") + "@@ -1,0 +1 @@\n+x = 1\n"
    assert cr.review(diff=d, review_checklist=[], author="a")["decision"] == "no_issues_found"


def test_default_oversize_threshold_is_exactly_400():
    def big(n):
        return hdr("tests/t.py") + f"@@ -0,0 +1,{n} @@\n" + "".join(f"+v{i} = {i}\n" for i in range(n))
    assert "oversized-change" not in rules(cr.review(big(400), [], author="a"))
    assert "oversized-change" in rules(cr.review(big(401), [], author="a"))


def test_default_long_line_threshold_is_exactly_120():
    d = lambda n: hdr("tests/t.py") + f"@@ -0,0 +1 @@\n+{'x' * n}\n"
    assert "long-line" not in rules(cr.review(d(120), [], author="a"))
    assert "long-line" in rules(cr.review(d(121), [], author="a"))


# ---- constants and honesty flags
def test_self_approval_forbidden_flag_true_on_every_path():
    clean = hdr("tests/t.py") + "@@ -0,0 +1 @@\n+x = 1\n"
    bad = hdr("src/c.py") + '@@ -0,0 +1 @@\n+password = "hunter2hunter2"\n'
    for kw in ({}, {"reviewer": "b", "requested_decision": "approve"}, {"reviewer": "b", "requested_decision": "request_changes"}):
        assert cr.review(clean, [], author="a", **kw)["self_approval_forbidden"] is True
    assert cr.review(bad, [], author="a", reviewer="b", requested_decision="approve")["self_approval_forbidden"] is True


def test_heuristic_rules_list_exact_and_message_map_keys():
    r = cr.review(hdr("tests/t.py") + "@@ -0,0 +1 @@\n+x = 1\n", [], author="a")
    expected = sorted(["hardcoded-secret", "conflict-marker", "dynamic-exec", "bare-except", "debug-leftover",
                       "todo-marker", "trailing-whitespace"]) + ["missing-tests", "oversized-change", "long-line"]
    assert r["heuristic_rules"] == expected
    assert cr._MESSAGES["bare-except"] == "Bare except swallows all errors"
    assert cr._MESSAGES["hardcoded-secret"] == "Possible hard-coded credential literal"
    assert set(cr._MESSAGES) == set(expected[:7])


# ---- round 2 pins (from fresh survivors of an independent operator set)
def test_headers_without_any_hunk_marker_rejected():
    with pytest.raises(cr.CodeReviewError, match="unified diff"):
        cr.parse_unified_diff("--- a/x\n+++ b/x\n")


def test_incomplete_deletions_keep_lookalike_header_as_content():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -1,2 +1 @@\n+n\n--- b\n-c\n")[0]
    assert f["removed"] == 2 and f["added"] == [(1, "n")]


def test_diff_line_after_complete_hunk_ends_the_hunk_even_without_dash_headers():
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -1 +1 @@\n-o\n+n\ndiff --git a/b b/b\nnew file mode 100644\n+stray\n")[0]
    assert f["added"] == [(1, "n")] and f["removed"] == 1


def test_hunk_before_file_header_message_and_with_later_valid_file():
    with pytest.raises(cr.CodeReviewError, match="hunk before file header"):
        cr.parse_unified_diff("@@ -1 +1 @@\n+x\n-o\n--- a/y\n+++ b/y\n@@ -1 +1 @@\n+n\n-o\n")


def test_new_hunk_closes_previous_incomplete_hunk():
    with pytest.raises(cr.CodeReviewError, match="line counts"):
        cr.parse_unified_diff(hdr("a.py") + "@@ -1,2 +1 @@\n-a\n+x\n@@ -9 +9 @@\n-q\n+r\n")


def test_marker_text_but_no_file_sections_message():
    with pytest.raises(cr.CodeReviewError, match="no file sections"):
        cr.parse_unified_diff("hello @@ world")


@pytest.mark.parametrize("bad", [None, 5, "", "   "])
def test_author_must_be_nonblank_text_with_contract_error(bad):
    with pytest.raises(cr.CodeReviewError) as e:
        cr.review(hdr("a.py") + "@@ -1 +1 @@\n+n\n-o\n", [], author=bad)
    assert type(e.value) is cr.CodeReviewError and "author" in str(e.value)


def test_checklist_items_must_all_be_text_and_tuple_is_accepted():
    d = hdr("tests/t.py") + "@@ -1 +1 @@\n+n\n-o\n"
    with pytest.raises(cr.CodeReviewError, match="list of strings"):
        cr.review(d, ["ok", 1], author="a")
    assert cr.review(d, ("correctness",), author="a")["checklist"][0]["status"] == "needs_human"


@pytest.mark.parametrize("who", ["", "   ", None])
def test_blank_reviewer_is_refused_as_missing_not_as_self_approval(who):
    d = hdr("tests/t.py") + "@@ -1 +1 @@\n+n\n-o\n"
    with pytest.raises(cr.CodeReviewError, match="requires a reviewer") as e:
        cr.review(d, [], author="a", reviewer=who, requested_decision="approve")
    assert type(e.value) is cr.CodeReviewError


def test_deletion_only_source_change_needs_no_tests():
    d = hdr("src/a.py") + "@@ -1 +0,0 @@\n-old\n"
    assert "missing-tests" not in rules(cr.review(d, [], author="a"))


def test_requested_request_changes_without_blockers_is_request_changes():
    d = hdr("tests/t.py") + "@@ -1 +1 @@\n+n\n-o\n"
    r = cr.review(d, [], author="a", reviewer="b", requested_decision="request_changes")
    assert r["decision"] == "request_changes" and r["approval"] is None and r["unresolved_blockers"] == []


# ---- equivalence locks (L49 / L74 survivors adjudicated equivalent; these pin the
# behavior they touch - they document, they do not claim to kill an equivalent mutant)
def test_lock_l49_path_slice_behavior():
    # L49 p = raw[4:].strip(); reachable only under raw.startswith("+++ "), where
    # raw[3:] == " " + raw[4:] and strip makes the two identical - proven equivalent.
    assert cr.parse_unified_diff("--- a/x\n+++ b/dir/x.py\n@@ -1 +1 @@\n+n\n-o\n")[0]["path"] == "dir/x.py"
    assert cr.parse_unified_diff("--- x\n+++ dir/x.py\n@@ -1 +1 @@\n+n\n-o\n")[0]["path"] == "dir/x.py"
    assert cr.parse_unified_diff("--- x\n+++  odd.py\n@@ -1 +1 @@\n+n\n-o\n")[0]["path"] == "odd.py"


def test_lock_l74_empty_files_rejection():
    # L74: any(True for _ in files) == bool(files), so the or/and mutant is identical;
    # locks the guard semantics: marker text with no file sections raises, a valid
    # single-file diff yields exactly one entry.
    with pytest.raises(cr.CodeReviewError, match="no file sections"):
        cr.parse_unified_diff("hello @@ world")
    f = cr.parse_unified_diff(hdr("a.py") + "@@ -1 +1 @@\n-o\n+n\n")
    assert len(f) == 1 and f[0]["path"] == "a.py"
