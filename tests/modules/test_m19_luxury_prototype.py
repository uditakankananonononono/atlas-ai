from pathlib import Path
from app.modules.m19_idea_incubator.luxury_prototype import build_prototype, COMPONENTS

def idea(levers): return {"idea_id": "+".join(levers), "levers": levers, "mechanism": "test mechanism"}

def test_every_supported_lever_builds_and_its_own_tests_pass(tmp_path):
    for lever in COMPONENTS:
        r = build_prototype(idea([lever]), tmp_path / lever)
        assert r["all_tests_passed"] and r["test_results"][0]["tests_run"] >= 5, (lever, r)
        assert (tmp_path / lever / f"{lever}.py").exists() and (tmp_path / lever / "README.md").exists()

def test_combined_idea_builds_both_and_reports_unsupported(tmp_path):
    r = build_prototype(idea(["provenance", "no_such_lever"]), tmp_path)
    assert r["built"] == ["provenance"] and r["unsupported_levers"] == ["no_such_lever"] and r["all_tests_passed"]

def test_only_unsupported_levers_is_not_a_pass(tmp_path):
    r = build_prototype(idea(["no_such_lever"]), tmp_path)
    assert r["built"] == [] and r["all_tests_passed"] is False

def test_a_broken_component_is_reported_failed_not_hidden(tmp_path, monkeypatch):
    code, test = COMPONENTS["provenance"]
    monkeypatch.setitem(COMPONENTS, "provenance", (code.replace("seq\": len(self.records)", "seq\": 99"), test))
    r = build_prototype(idea(["provenance"]), tmp_path)
    assert r["all_tests_passed"] is False and r["test_results"][0]["returncode"] != 0

def test_readme_makes_no_affiliation_claim(tmp_path):
    build_prototype(idea(["scarcity_access"]), tmp_path)
    assert "Not affiliated" in (tmp_path / "README.md").read_text()


def test_all_eight_ideation_levers_have_components():
    from app.modules.m19_idea_incubator.luxury_ideation import LEVERS
    assert set(LEVERS) <= set(COMPONENTS)


def test_stale_files_in_output_dir_do_not_contaminate(tmp_path):
    (tmp_path / "test_stale.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_x(self): self.fail('stale')\n")
    (tmp_path / "provenance.py").write_text("raise RuntimeError('old broken component')\n")
    r = build_prototype(idea(["provenance"]), tmp_path)
    assert r["all_tests_passed"] and not (tmp_path / "test_stale.py").exists()
