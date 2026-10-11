"""Row 696 Branch by Abstraction: desired-behaviour pins for disclosed gaps.

G1/G2 (boolean refusal) and G3 (ast.Import and alias tracking) tests are ordinary tests.
KNOWN_RESIDUAL tests pin what a static scan cannot see (getattr, strings, star import, importlib).
"""
import pytest

from app.modules.m20_general_cognitive_worker.branch_abstraction696 import (
    BranchAbstractionError,
    BranchByAbstraction,
)


class Old:
    def price(self, q):
        return q


class New:
    def price(self, q):
        return q


def _b(**kw):
    return BranchByAbstraction("P", ["price"], Old(), New(), **kw)


@pytest.mark.parametrize("bad", [True, False])
def test_canary_percent_refuses_booleans(bad):
    with pytest.raises(BranchAbstractionError):
        _b().set_route("canary", bad)


def test_min_equivalence_cases_refuses_true():
    with pytest.raises(BranchAbstractionError):
        _b(min_equivalence_cases=True)


def _scan(src):
    out = _b().scan_direct_usage({"a.py": src}, "OldPricer")
    return sorted(out, key=lambda d: (d["line"], d["kind"]))  # walk order is not source order


def test_scan_finds_plain_import_of_old_name():
    assert _scan("import OldPricer\n") == [{"file": "a.py", "line": 1, "kind": "import"}]


def test_scan_finds_dotted_import_by_last_segment():
    assert _scan("import pkg.OldPricer\n") == [{"file": "a.py", "line": 1, "kind": "import"}]


def test_scan_finds_dotted_import_with_old_name_in_the_middle_is_not_a_match():
    assert _scan("import OldPricerTools\nimport pkg.OldPricer.sub\n") == []


def test_scan_dotted_attribute_use_after_import():
    out = _scan("import pkg\npkg.OldPricer()\n")
    assert out == [{"file": "a.py", "line": 2, "kind": "attribute"}]


def test_scan_import_alias_use_is_found():
    out = _scan("import pkg.OldPricer as x\nx()\n")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}, {"file": "a.py", "line": 2, "kind": "alias"}]


def test_scan_plain_import_alias_use_is_found():
    out = _scan("import OldPricer as op\nop.run()\n")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}, {"file": "a.py", "line": 2, "kind": "alias"}]


def test_scan_importfrom_alias_use_is_found():
    out = _scan("from m import OldPricer as X\nX()\nY = X\n")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}, {"file": "a.py", "line": 2, "kind": "alias"},
                   {"file": "a.py", "line": 3, "kind": "alias"}]


def test_scan_alias_equal_to_old_name_is_not_double_reported():
    out = _scan("from m import OldPricer as OldPricer\nOldPricer()\n")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}, {"file": "a.py", "line": 2, "kind": "name"}]


def test_scan_unrelated_alias_is_not_reported():
    assert _scan("import other as x\nfrom m import Other as y\nx()\ny()\n") == []


def test_scan_alias_names_are_per_file():
    out = BranchByAbstraction("P", ["price"], Old(), New()).scan_direct_usage(
        {"a.py": "import pkg.OldPricer as x\n", "b.py": "x()\n"}, "OldPricer")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}]


@pytest.mark.parametrize("src", [
    "import m\ngetattr(m, 'OldPricer')\n",
    "x = 'OldPricer'\n",
    "from m import *\n",
    "import importlib\nimportlib.import_module('m').__dict__['OldPricer']\n",
])
def test_KNOWN_RESIDUAL_dynamic_access_is_not_detected_static_scan_only(src):
    assert _scan(src) == []


def test_scan_plain_import_alias_equal_to_old_name_is_not_double_reported():
    out = _scan("import pkg.OldPricer as OldPricer\nOldPricer()\n")
    assert out == [{"file": "a.py", "line": 1, "kind": "import"}, {"file": "a.py", "line": 2, "kind": "name"}]


def test_scan_unused_aliased_import_is_still_reported_at_the_import_line():
    assert _scan("import pkg.OldPricer as x\n") == [{"file": "a.py", "line": 1, "kind": "import"}]
