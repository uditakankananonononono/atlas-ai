"""Tests for the Deliverable 5 (P81|L69) presence audit.

The audit consumes the result dict of the per-project deliverable checker. These
tests build such dicts by hand (stub data only); no external checker code is loaded.
All data is fictional. Run with: pytest --noconftest <this file>
"""
import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import sys

import pytest

_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "backend/app/modules/instinct_doc/deliverable5_audit_p81.py"
)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


A = _load(_PATH, "deliverable5_audit_p81_under_test")
KINDS = ("dataset", "tool", "code", "test", "verification_script", "formula", "real_life_data",
         "external_validation", "benchmark_output")
UNVERIFIED_FIELDS = ("repository_created", "dataset_use", "real_life_data", "tool_execution",
                     "test_execution", "external_validation", "benchmark_execution", "sota")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def art(aid, kind, path, status="FILE_HASH_MATCH", content=None):
    return {"id": aid, "kind": kind, "path": path, "sha256": sha(content if content is not None else path),
            "status": status}


def result(artifacts, project_id="proj-a", source_lines=("P81|L69",)):
    counts = {k: 0 for k in KINDS}
    for a in artifacts:
        if a["status"] == "FILE_HASH_MATCH":
            counts[a["kind"]] += 1
    r = {
        "project_id": project_id, "source_lines": list(source_lines),
        "declared_repository": "https://example.invalid/r", "requested_targets":
        {"datasets": 0, "project_tools": 0, "program_tools": 0},
        "artifacts": artifacts, "measured_artifact_count": sum(counts.values()),
        "measured_artifact_counts": counts, "benchmark_metadata": None,
        "doc_lines_fulfilled": False, "boundary": "x",
    }
    for f in UNVERIFIED_FIELDS:
        r[f] = "UNVERIFIED"
    return r


def full():
    return [
        art("c1", "code", "src/engine.py"),
        art("t1", "test", "tests/test_engine.py"),
        art("v1", "verification_script", "scripts/verify_engine.py"),
        art("f1", "formula", "docs/formulas.tex"),
    ]


# ---- category verdicts ---------------------------------------------------------
def test_all_four_present_and_corroborated():
    rep = A.audit_project(result(full()))
    cats = rep["categories"]
    assert {k: v["verdict"] for k, v in cats.items()} == {
        "code": "PRESENT_CORROBORATED", "test": "PRESENT_CORROBORATED",
        "verification_script": "PRESENT_CORROBORATED", "formula": "PRESENT_CORROBORATED"}
    assert rep["all_four_present"] is True and rep["all_four_corroborated"] is True
    assert cats["code"] == {"verdict": "PRESENT_CORROBORATED", "counted": 1, "corroborated": 1,
                            "artifact_ids": ["c1"], "notes": [], "meets_declared_minimum": None}


def test_missing_category_is_absent():
    rep = A.audit_project(result([a for a in full() if a["kind"] != "formula"]))
    assert rep["categories"]["formula"]["verdict"] == "ABSENT"
    assert rep["categories"]["formula"]["counted"] == 0
    assert rep["all_four_present"] is False and rep["all_four_corroborated"] is False


def test_empty_artifact_list_everything_absent():
    rep = A.audit_project(result([]))
    assert all(v["verdict"] == "ABSENT" for v in rep["categories"].values())
    assert rep["not_counted"] == []


@pytest.mark.parametrize("status", ["HASH_MISMATCH", "DUPLICATE_CONTENT", "EMPTY_FILE", "TOO_LARGE",
                                    "CHANGED_DURING_READ", "UNREADABLE_OR_UNSAFE", "NOT_REGULAR_FILE"])
def test_uncounted_statuses_do_not_count(status):
    arts = [a for a in full() if a["kind"] != "test"] + [art("t1", "test", "tests/test_engine.py", status=status)]
    rep = A.audit_project(result(arts))
    assert rep["categories"]["test"]["verdict"] == "ABSENT"
    assert rep["not_counted"] == [{"id": "t1", "kind": "test", "path": "tests/test_engine.py", "status": status}]


def test_only_first_counted_unit_of_duplicates_counts():
    arts = full() + [art("t2", "test", "tests/test_other.py", status="DUPLICATE_CONTENT")]
    rep = A.audit_project(result(arts))
    assert rep["categories"]["test"]["counted"] == 1
    assert [n["id"] for n in rep["not_counted"]] == ["t2"]


def test_other_kinds_are_reported_not_audited():
    arts = full() + [art("d1", "dataset", "data/a.csv"), art("d2", "dataset", "data/b.csv"),
                     art("b1", "benchmark_output", "out/b.json")]
    rep = A.audit_project(result(arts))
    assert rep["other_kinds_counted_not_audited"] == {"dataset": 2, "benchmark_output": 1}
    assert set(rep["categories"]) == {"code", "test", "verification_script", "formula"}


def test_counted_but_path_does_not_look_like_the_kind():
    arts = [art("c1", "code", "notes.txt"), art("t1", "test", "docs/readme.md"),
            art("v1", "verification_script", "src/engine.py"), art("f1", "formula", "src/engine.bin")]
    rep = A.audit_project(result(arts))
    for k, v in rep["categories"].items():
        assert v["verdict"] == "PRESENT_UNCORROBORATED" and v["counted"] == 1 and v["corroborated"] == 0, k
        assert any("path" in n for n in v["notes"]), k
    assert rep["all_four_present"] is True and rep["all_four_corroborated"] is False


@pytest.mark.parametrize("kind,path,ok", [
    ("code", "src/a.py", True), ("code", "lib/a.js", True), ("code", "a.ts", True), ("code", "a.go", True),
    ("code", "a.rs", True), ("code", "a.java", True), ("code", "a.c", True), ("code", "a.cpp", True),
    ("code", "a.rb", True), ("code", "a.sh", True), ("code", "a.md", False), ("code", "a.txt", False),
    ("code", "tests/test_a.py", False), ("code", "src/a_test.py", False), ("code", "a.spec.ts", False),
    ("code", "a.test.js", False),
    ("test", "tests/test_a.py", True), ("test", "test_a.py", True), ("test", "a_test.py", True),
    ("test", "a.test.js", True), ("test", "a.spec.ts", True), ("test", "tests/helper.py", True),
    ("test", "__tests__/a.js", True), ("test", "src/a.py", False), ("test", "tests/readme.md", False),
    ("verification_script", "scripts/verify_a.py", True), ("verification_script", "check_a.sh", True),
    ("verification_script", "validate_a.py", True), ("verification_script", "verification/run.py", True),
    ("verification_script", "verify/run.sh", True), ("verification_script", "verify_a.md", False),
    ("verification_script", "src/a.py", False),
    ("formula", "docs/f.tex", True), ("formula", "f.md", True), ("formula", "f.rst", True),
    ("formula", "f.txt", True), ("formula", "formulas.py", True), ("formula", "math_utils.py", True),
    ("formula", "equations.ipynb", True), ("formula", "src/a.py", False), ("formula", "f.bin", False),
])
def test_path_hints(kind, path, ok):
    rep = A.audit_project(result([art("x1", kind, path)]))
    cat = rep["categories"][kind]
    assert cat["counted"] == 1
    assert (cat["verdict"] == "PRESENT_CORROBORATED") is ok


# ---- content corroboration (bound to the measured hash) -------------------------
TEST_SRC = "def test_x():\n    assert 1 == 1\n"
FORMULA_SRC = "The loss is $L = \\frac{1}{n}\\sum_i (y_i - p_i)^2$.\n"


def test_content_with_markers_corroborates():
    arts = [art("t1", "test", "tests/test_a.py", content=TEST_SRC),
            art("f1", "formula", "docs/f.md", content=FORMULA_SRC)]
    rep = A.audit_project(result(arts), contents={"tests/test_a.py": TEST_SRC, "docs/f.md": FORMULA_SRC})
    assert rep["categories"]["test"]["verdict"] == "PRESENT_CORROBORATED"
    assert rep["categories"]["formula"]["verdict"] == "PRESENT_CORROBORATED"
    assert rep["contents_checked"] == ["docs/f.md", "tests/test_a.py"]


def test_bound_content_without_markers_downgrades():
    prose = "Nothing mathematical here, only prose.\n"
    arts = [art("f1", "formula", "docs/f.md", content=prose)]
    rep = A.audit_project(result(arts), contents={"docs/f.md": prose})
    c = rep["categories"]["formula"]
    assert c["verdict"] == "PRESENT_UNCORROBORATED" and c["counted"] == 1 and c["corroborated"] == 0
    assert any("no formula marker" in n for n in c["notes"])
    empty_t = "# only a comment\nx = 1\n"
    rep = A.audit_project(result([art("t1", "test", "tests/test_a.py", content=empty_t)]),
                          contents={"tests/test_a.py": empty_t})
    assert rep["categories"]["test"]["verdict"] == "PRESENT_UNCORROBORATED"
    assert any("no test marker" in n for n in rep["categories"]["test"]["notes"])


def test_content_not_matching_artifact_hash_is_ignored_and_noted():
    arts = [art("t1", "test", "tests/test_a.py", content=TEST_SRC)]
    rep = A.audit_project(result(arts), contents={"tests/test_a.py": "def test_y():\n    assert True\n"})
    assert rep["categories"]["test"]["verdict"] == "PRESENT_CORROBORATED"  # path hint only
    assert rep["contents_checked"] == []
    assert rep["contents_rejected"] == [{"path": "tests/test_a.py", "reason": "content does not match the artifact sha256"}]


def test_content_for_unknown_or_uncounted_path_is_rejected():
    arts = [art("t1", "test", "tests/test_a.py", status="HASH_MISMATCH", content=TEST_SRC)]
    rep = A.audit_project(result(arts), contents={"tests/test_a.py": TEST_SRC, "other.py": "x"})
    reasons = {r["path"]: r["reason"] for r in rep["contents_rejected"]}
    assert reasons == {"other.py": "path is not a declared artifact",
                       "tests/test_a.py": "artifact was not counted by the checker"}


def test_content_must_be_str_and_dict():
    with pytest.raises(A.AuditInputError):
        A.audit_project(result(full()), contents={"src/engine.py": b"bytes"})
    with pytest.raises(A.AuditInputError):
        A.audit_project(result(full()), contents=["x"])


@pytest.mark.parametrize("src,ok", [
    ("def test_a():\n    pass\n", True), ("assert x == 1\n", True), ("@Test\npublic void a() {}\n", True),
    ("expect(x).toBe(1)\n", True), ("it('works', () => {})\n", True), ("test('works', () => {})\n", True),
    ("describe('x', () => {})\n", True), ("x = 1\n", False), ("# assertion later\n", False),
    ("def tester():\n    pass\n", False),
])
def test_test_markers(src, ok):
    rep = A.audit_project(result([art("t1", "test", "tests/test_a.py", content=src)]),
                          contents={"tests/test_a.py": src})
    assert (rep["categories"]["test"]["verdict"] == "PRESENT_CORROBORATED") is ok


@pytest.mark.parametrize("src,ok", [
    ("$a + b = c$", True), ("\\frac{a}{b}", True), ("\\sum_i x_i", True), ("\\int_0^1 f", True),
    ("\\sqrt{2}", True), ("\\begin{equation} a=b \\end{equation}", True), ("\\[ a = b \\]", True),
    ("\\( a \\)", True), ("\\partial_t u", True), ("E \u2248 mc\u00b2 and \u2211 x", True),
    ("\u2207f", True), ("plain words only", False), ("price is 5 dollars and 6 cents", False),
    ("a = b", False),
])
def test_formula_markers(src, ok):
    rep = A.audit_project(result([art("f1", "formula", "f.md", content=src)]), contents={"f.md": src})
    assert (rep["categories"]["formula"]["verdict"] == "PRESENT_CORROBORATED") is ok


# ---- declared minimums ----------------------------------------------------------
def test_declared_minimums():
    arts = full() + [art("c2", "code", "src/more.py")]
    rep = A.audit_project(result(arts), minimum_counts={"code": 2, "test": 2, "formula": 1})
    c = rep["categories"]
    assert (c["code"]["meets_declared_minimum"], c["test"]["meets_declared_minimum"],
            c["formula"]["meets_declared_minimum"], c["verification_script"]["meets_declared_minimum"]) == (True, False, True, None)
    assert rep["minimum_counts_are_caller_declared"] is True
    assert rep["all_declared_minimums_met"] is False


def test_declared_minimums_use_counted_not_corroborated():
    arts = [art("c1", "code", "notes.txt")]
    rep = A.audit_project(result(arts), minimum_counts={"code": 1})
    assert rep["categories"]["code"]["meets_declared_minimum"] is True


def test_no_minimums_means_none():
    rep = A.audit_project(result(full()))
    assert rep["all_declared_minimums_met"] is None and rep["minimum_counts_are_caller_declared"] is False


@pytest.mark.parametrize("bad", [{"datasets": 1}, {"code": -1}, {"code": True}, {"code": 1.5}, {"code": "2"}, [1]])
def test_bad_minimums_rejected(bad):
    with pytest.raises(A.AuditInputError):
        A.audit_project(result(full()), minimum_counts=bad)


# ---- consuming the checker's result: validation ---------------------------------
def test_counts_must_match_artifacts():
    r = result(full())
    r["measured_artifact_counts"]["code"] = 5
    with pytest.raises(A.AuditInputError) as e:
        A.audit_project(r)
    assert "counts" in str(e.value)
    r = result(full())
    r["measured_artifact_count"] = 99
    with pytest.raises(A.AuditInputError):
        A.audit_project(r)


@pytest.mark.parametrize("field", UNVERIFIED_FIELDS)
def test_result_must_leave_every_claim_unverified(field):
    r = result(full())
    r[field] = "VERIFIED"
    with pytest.raises(A.AuditInputError) as e:
        A.audit_project(r)
    assert field in str(e.value)


def test_result_must_not_claim_doc_lines_fulfilled():
    r = result(full())
    r["doc_lines_fulfilled"] = True
    with pytest.raises(A.AuditInputError):
        A.audit_project(r)


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("project_id"), lambda r: r.pop("artifacts"), lambda r: r.pop("measured_artifact_counts"),
    lambda r: r.pop("measured_artifact_count"), lambda r: r.pop("source_lines"),
    lambda r: r.pop("doc_lines_fulfilled"), lambda r: r.pop("sota"),
    lambda r: r.update(project_id=""), lambda r: r.update(project_id=5), lambda r: r.update(artifacts="x"),
    lambda r: r.update(source_lines="P81|L69"), lambda r: r.update(source_lines=["bad"]),
    lambda r: r["artifacts"][0].update(kind="mystery"), lambda r: r["artifacts"][0].update(status="OK"),
    lambda r: r["artifacts"][0].pop("sha256"), lambda r: r["artifacts"][0].update(id=""),
    lambda r: r["artifacts"][0].update(path=""), lambda r: r["artifacts"][1].update(id=r["artifacts"][0]["id"]),
    lambda r: r["artifacts"][1].update(path=r["artifacts"][0]["path"]),
    lambda r: r["artifacts"].append("not a dict"),
    lambda r: r["measured_artifact_counts"].pop("code"),
    lambda r: r["measured_artifact_counts"].update(extra=1),
    lambda r: r["measured_artifact_counts"].update(code=True),
])
def test_malformed_results_rejected(mutate):
    r = result(full())
    mutate(r)
    with pytest.raises(A.AuditInputError):
        A.audit_project(r)


def test_non_dict_result_rejected():
    for bad in (None, [], "x", 1):
        with pytest.raises(A.AuditInputError):
            A.audit_project(bad)


def test_input_not_mutated_and_output_is_json():
    r = result(full())
    before = copy.deepcopy(r)
    rep = A.audit_project(r, contents={"src/engine.py": "x"}, minimum_counts={"code": 1})
    assert r == before
    json.dumps(rep)
    assert json.dumps(rep, sort_keys=True) == json.dumps(
        A.audit_project(copy.deepcopy(r), contents={"src/engine.py": "x"}, minimum_counts={"code": 1}), sort_keys=True)


# ---- honesty fields in the output -------------------------------------------------
def test_report_states_what_it_does_not_claim():
    rep = A.audit_project(result(full()))
    assert rep["deliverable"] == "5" and rep["source_line"] == "P81|L69"
    assert rep["doc_line_fulfilled"] is False
    assert rep["vastness_threshold"] is None
    assert rep["unverified"] == {"quality": "UNVERIFIED", "vastness": "UNVERIFIED",
                                 "execution": "UNVERIFIED", "correctness": "UNVERIFIED"}
    for phrase in ("presence", "not quality", "not vastness"):
        assert phrase in rep["boundary"]
    assert "heuristic" in rep["boundary"]


def test_cites_source_line_flag():
    assert A.audit_project(result(full()))["cites_p81_l69"] is True
    assert A.audit_project(result(full(), source_lines=("P1|L1", "P81|L69")))["cites_p81_l69"] is True
    assert A.audit_project(result(full(), source_lines=("P1|L1",)))["cites_p81_l69"] is False
    assert A.audit_project(result(full(), source_lines=("P810|L69",)))["cites_p81_l69"] is False


def test_passes_through_project_identity():
    rep = A.audit_project(result(full(), project_id="proj-z", source_lines=("P2|L2",)))
    assert rep["project_id"] == "proj-z" and rep["source_lines"] == ["P2|L2"]


# ---- many projects ---------------------------------------------------------------
def test_audit_projects_rollup():
    good = result(full(), project_id="a")
    partial = result([a for a in full() if a["kind"] != "verification_script"], project_id="b")
    bad_path = result([art("c1", "code", "x.txt"), art("t1", "test", "tests/test_a.py"),
                       art("v1", "verification_script", "verify_a.py"), art("f1", "formula", "f.tex")], project_id="c")
    out = A.audit_projects([good, partial, bad_path])
    assert [p["project_id"] for p in out["projects"]] == ["a", "b", "c"]
    assert out["rollup"] == {"projects": 3, "all_four_present": 2, "all_four_corroborated": 1,
                             "absent_by_category": {"code": 0, "test": 0, "verification_script": 1, "formula": 0}}
    assert out["doc_line_fulfilled"] is False


def test_audit_projects_rejects_bad_lists():
    with pytest.raises(A.AuditInputError):
        A.audit_projects([])
    with pytest.raises(A.AuditInputError):
        A.audit_projects("x")
    with pytest.raises(A.AuditInputError):
        A.audit_projects([result(full(), project_id="a"), result(full(), project_id="a")])


def test_audit_projects_contents_and_minimums_per_project():
    t = TEST_SRC
    r = result([art("t1", "test", "tests/test_a.py", content=t)], project_id="a")
    out = A.audit_projects([r], contents_by_project={"a": {"tests/test_a.py": t}}, minimum_counts={"test": 1})
    p = out["projects"][0]
    assert p["contents_checked"] == ["tests/test_a.py"]
    assert p["categories"]["test"]["meets_declared_minimum"] is True
    with pytest.raises(A.AuditInputError):
        A.audit_projects([r], contents_by_project={"zzz": {}})


# ---- structure ------------------------------------------------------------------
def test_module_imports_only_pure_stdlib():
    tree = ast.parse(_PATH.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "copy", "hashlib", "re", "typing"}, mods


def test_module_has_no_package_relative_imports():
    # Ownership-neutral: the module must work whether or not the directory has a package marker
    # (it is loaded by file path here). This test neither requires nor forbids that marker.
    tree = ast.parse(_PATH.read_text())
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]


def test_artifacts_empty_tuple_refused_with_exact_message():
    r = result([])
    r["artifacts"] = ()
    with pytest.raises(A.AuditInputError) as ei:
        A.audit_project(r)
    assert str(ei.value) == "artifacts must be a list"


def test_hidden_file_name_is_not_an_extension():
    assert A._split(".py") == ([], ".py", ".py", "")
    assert A._split("a/.py") == (["a"], ".py", ".py", "")
    assert A._split("a/b.py") == (["a"], "b.py", "b", ".py")
    cat = A.audit_project(result([art("x1", "code", ".py")]))["categories"]["code"]
    assert cat["verdict"] == "PRESENT_UNCORROBORATED"


# ---- declared schema of the consumed result (stub data only, no external code loaded) ----
# The audit consumes the result dict of a per-project deliverable checker. This test declares the
# fields the audit relies on, with hand-written stub data. A comparison against the real checker
# is deliberately NOT made here: that checker is not landed.
STUB_RESULT_FIELDS = ("project_id", "source_lines", "artifacts", "measured_artifact_counts",
                      "measured_artifact_count", "doc_lines_fulfilled") + UNVERIFIED_FIELDS
STUB_ARTIFACT_FIELDS = ("id", "kind", "path", "sha256", "status")


def test_declared_stub_schema_is_what_the_audit_needs():
    stub = result(full() + [art("f2", "formula", "docs/dup.md", status="DUPLICATE_CONTENT"),
                            art("d1", "dataset", "data/a.csv")])
    assert all(f in stub for f in STUB_RESULT_FIELDS)
    assert all(f in a for a in stub["artifacts"] for f in STUB_ARTIFACT_FIELDS)
    rep = A.audit_project(stub)
    assert rep["all_four_corroborated"] is True
    assert [n["status"] for n in rep["not_counted"]] == ["DUPLICATE_CONTENT"]
    assert rep["other_kinds_counted_not_audited"] == {"dataset": 1}
    for f in STUB_RESULT_FIELDS:
        broken = {k: v for k, v in stub.items() if k != f}
        with pytest.raises(A.AuditInputError):
            A.audit_project(broken)
    for f in STUB_ARTIFACT_FIELDS:
        broken = copy.deepcopy(stub)
        del broken["artifacts"][0][f]
        with pytest.raises(A.AuditInputError):
            A.audit_project(broken)


def test_stub_hash_mismatch_status_removes_the_artifact_from_the_count():
    arts = [a for a in full() if a["kind"] != "test"] + [
        art("t1", "test", "tests/test_engine.py", status="HASH_MISMATCH")]
    rep = A.audit_project(result(arts))
    assert rep["categories"]["test"]["verdict"] == "ABSENT"


# ---- added after the first mutant run (survivor-driven) -------------------------
@pytest.mark.parametrize("kind,path,ok", [
    ("verification_script", "verify_a.js", True), ("verification_script", "verify_a.ts", False),
    ("test", "test/helper.py", True), ("test", "spec/helper.py", False),
])
def test_path_hints_extra(kind, path, ok):
    cat = A.audit_project(result([art("x1", kind, path)]))["categories"][kind]
    assert (cat["verdict"] == "PRESENT_CORROBORATED") is ok


@pytest.mark.parametrize("src", ["\\alpha + 1", "\\beta + 1", "\u2211 x", "\u222b f", "\u221a 2", "\u2202 u",
                                 "a \u2248 b", "a \u2264 b", "a \u2265 b"])
def test_formula_markers_each_symbol(src):
    rep = A.audit_project(result([art("f1", "formula", "f.md", content=src)]), contents={"f.md": src})
    assert rep["categories"]["formula"]["verdict"] == "PRESENT_CORROBORATED"


def test_unknown_artifact_status_rejected():
    with pytest.raises(A.AuditInputError):
        A.audit_project(result([art("t1", "test", "tests/test_a.py", status="BOGUS")]))


def test_not_counted_lists_only_audited_categories():
    arts = full() + [art("d1", "dataset", "data/d.csv", status="EMPTY_FILE")]
    rep = A.audit_project(result(arts))
    assert rep["not_counted"] == []
