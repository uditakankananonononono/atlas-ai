"""Row 696 Branch by Abstraction: pins for scan_direct_usage import matching.

Tests only. Behaviour pinned here is the current behaviour of the static scan; entries marked
RESIDUAL describe known limits (documented in docs/branch_abstraction696_gaps.md), not goals.
"""
import pytest

from app.modules.m20_general_cognitive_worker.branch_abstraction696 import BranchByAbstraction


class _O:
    def price(self, q):
        return q


def scan(src, symbol="OldPricer"):
    b = BranchByAbstraction("P", ["price"], _O(), _O())
    out = b.scan_direct_usage({"a.py": src}, symbol)
    return sorted(out, key=lambda d: (d["line"], d["kind"]))


def f(line, kind):
    return {"file": "a.py", "line": line, "kind": kind}


# --- dotted old_symbol -------------------------------------------------
def test_dotted_symbol_matches_a_plain_dotted_import_by_full_name():
    assert scan("import pkg.OldPricer\n", "pkg.OldPricer") == [f(1, "import")]


def test_dotted_symbol_alias_use_is_reported():
    assert scan("import pkg.OldPricer as x\nx()\n", "pkg.OldPricer") == [f(1, "import"), f(2, "alias")]


def test_RESIDUAL_dotted_symbol_never_matches_an_ImportFrom_name():
    """ImportFrom names are bare identifiers, so a dotted symbol cannot match them."""
    assert scan("from pkg import OldPricer\n", "pkg.OldPricer") == []


# --- negatives: the symbol must match a whole dotted segment at the end ---
def test_import_with_old_name_as_a_suffix_of_the_module_is_not_a_match():
    assert scan("import xOldPricer\n") == []


def test_import_with_old_name_as_a_prefix_of_the_last_segment_is_not_a_match():
    assert scan("import pkg.OldPricerX\n") == []


def test_RESIDUAL_old_name_in_a_non_final_segment_is_not_a_match():
    assert scan("import pkg.OldPricer.sub\n") == []
    assert scan("import OldPricer.sub as q\nq()\n") == []


# --- case sensitivity --------------------------------------------------
@pytest.mark.parametrize("src", ["import oldpricer\n", "import pkg.oldpricer\n", "import OLDPRICER\n"])
def test_matching_is_case_sensitive(src):
    assert scan(src) == []


# --- several names on one import line ---------------------------------------
def test_one_matching_name_among_several_is_reported_once():
    assert scan("import OldPricer, other\n") == [f(1, "import")]
    assert scan("import other, OldPricer\n") == [f(1, "import")]


def test_alias_of_the_matching_name_in_a_multi_import_is_tracked():
    assert scan("import other, OldPricer as op\nop()\n") == [f(1, "import"), f(2, "alias")]


def test_alias_of_a_non_matching_name_in_a_multi_import_is_not_tracked():
    assert scan("import OldPricer, other as op\nop()\n") == [f(1, "import")]


def test_no_matching_name_gives_no_finding():
    assert scan("import other, another\n") == []


# --- nested scopes ----------------------------------------------------------
def test_import_and_alias_inside_a_function_are_found():
    assert scan("def g():\n    import pkg.OldPricer as x\n    return x()\n") == [f(2, "import"), f(3, "alias")]


def test_importfrom_alias_inside_a_class_is_found():
    assert scan("class C:\n    from m import OldPricer as q\n    z = q\n") == [f(2, "import"), f(3, "alias")]


# --- from Old import z -------------------------------------------------------
def test_RESIDUAL_importing_from_a_module_named_like_the_symbol_is_not_flagged():
    """`from OldPricer import z` names the module, not the symbol; current behaviour is no finding."""
    assert scan("from OldPricer import z\n") == []
    assert scan("from pkg.OldPricer import z\n") == []


# --- scope-blind alias and rebinding ----------------------------------------
def test_RESIDUAL_alias_tracking_is_scope_blind():
    """A parameter named like the alias is a different binding, but the later use is still reported."""
    assert scan("import pkg.OldPricer as x\ndef g(x):\n    return x\n") == [f(1, "import"), f(3, "alias")]


def test_RESIDUAL_rebinding_an_alias_is_still_reported():
    """`X = 5` rebinds X, but every Name X (store or load) is reported as alias."""
    assert scan("from m import OldPricer as X\nX = 5\nprint(X)\n") == [f(1, "import"), f(2, "alias"), f(3, "alias")]


@pytest.mark.parametrize("src", ["from m import oldpricer\n", "from m import oldpricer as X\nX()\n", "from m import OLDPRICER as X\nX()\n"])
def test_importfrom_matching_is_case_sensitive_with_and_without_alias(src):
    assert scan(src) == []
