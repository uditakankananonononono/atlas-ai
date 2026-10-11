"""Row 696 Branch by Abstraction: residual pins for the static scan and the removal gate.

Tests only; the module is not changed. Everything marked KNOWN_LIMIT, DECLARED_NOT_DETECTED or
KNOWN_QUIRK pins CURRENT behaviour that is documented in docs/branch_abstraction696_gaps.md.
None of it is a goal. A CLEAR removal gate means only that none of the caller-supplied files
showed a static reference; it never means no reference exists anywhere.
"""
import pytest

from app.modules.m20_general_cognitive_worker.branch_abstraction696 import BranchByAbstraction


class _Impl:
    def price(self, q):
        return q * 10


def ready():
    """An instance that satisfies every gate except the scan."""
    b = BranchByAbstraction("Pricer", ["price"], _Impl(), _Impl())
    b.register_caller("c")
    b.mark_caller_migrated("c")
    b.verify_equivalence("price", [((1,), {})])
    b.set_route("new")
    return b


def findings(src_by_file, symbol="OldPricer", **kw):
    return BranchByAbstraction("P", ["price"], _Impl(), _Impl()).scan_direct_usage(src_by_file, symbol, **kw)


# --- (b) over-report: fail-safe, KNOWN_LIMIT -------------------------------------------------
def test_KNOWN_LIMIT_alias_attribute_with_the_old_name_is_reported_twice():
    """`X.OldPricer` after `from m import OldPricer as X`: the alias Name and the Attribute both fire."""
    b = BranchByAbstraction("P", ["price"], _Impl(), _Impl())
    out = b.scan_direct_usage({"a.py": "from m import OldPricer as X\nX.OldPricer\n"}, "OldPricer")
    assert sorted((d["line"], d["kind"]) for d in out) == [(1, "import"), (2, "alias"), (2, "attribute")]


def test_KNOWN_LIMIT_over_report_blocks_removal_it_does_not_let_it_through():
    b = ready()
    b.scan_direct_usage({"a.py": "import pkg.OldPricer as x\ndef g(x):\n    return x\nX = 5\n"}, "OldPricer")
    ok, why = b.can_remove_old()
    assert ok is False and why == ["direct-usage scan has 2 finding(s)"]


def test_KNOWN_LIMIT_rebinding_and_scope_blind_alias_are_still_reported():
    out = findings({"a.py": "from m import OldPricer as X\nX = 5\n"})
    assert [(d["line"], d["kind"]) for d in out] == [(1, "import"), (2, "alias")]


# --- (c) fail-open: DECLARED_NOT_DETECTED ----------------------------------------------------
@pytest.mark.parametrize("src", [
    "import m\ngetattr(m, 'OldPricer')\n",
    "import importlib\nimportlib.import_module('m').__dict__['OldPricer']\n",
    "name = 'OldPricer'\n",
    "from OldPricer import z\n",
    "import pkg.OldPricer.sub\n",
    "from m import *\n",
])
def test_DECLARED_NOT_DETECTED_references_the_static_scan_cannot_see_leave_the_gate_clear(src):
    b = ready()
    assert b.scan_direct_usage({"a.py": src}, "OldPricer") == []
    assert b.can_remove_old() == (True, [])


def test_DECLARED_NOT_DETECTED_dotted_symbol_from_import_leaves_the_gate_clear():
    b = ready()
    assert b.scan_direct_usage({"a.py": "from pkg import OldPricer\n"}, "pkg.OldPricer") == []
    assert b.can_remove_old() == (True, [])


# --- (d)(e) CLEAR means none of the supplied files showed a static reference -----------------
def test_clear_gate_says_nothing_about_files_that_were_not_supplied():
    b = ready()
    supplied = {"clean.py": "x = 1\n"}
    unsupplied = {"caller_not_in_inventory.py": "OldPricer()\n"}
    assert b.scan_direct_usage(supplied, "OldPricer") == []
    assert b.can_remove_old() == (True, [])
    assert findings(unsupplied)  # the reference exists, the scan just never saw that file


def test_KNOWN_QUIRK_empty_inventory_satisfies_the_scan_gate():
    b = ready()
    assert b.scan_direct_usage({}, "OldPricer") == []
    assert b.can_remove_old() == (True, [])
    b.remove_old()


def test_partial_inventory_is_not_detected_as_partial():
    b = ready()
    b.scan_direct_usage({"only_one.py": "y = 2\n"}, "OldPricer")
    assert b.report()["direct_usage_findings"] == 0
    assert b.can_remove_old()[0] is True


# --- (f) last scan wins ----------------------------------------------------------------------
def test_KNOWN_QUIRK_rescan_with_another_symbol_replaces_a_dirty_scan():
    b = ready()
    b.scan_direct_usage({"a.py": "OldPricer()\n"}, "OldPricer")
    assert b.can_remove_old() == (False, ["direct-usage scan has 1 finding(s)"])
    b.scan_direct_usage({"a.py": "OldPricer()\n"}, "SomethingElse")
    assert b.can_remove_old() == (True, [])


# --- (g) allowed_files is an exact string match, no normalisation ---------------------------
def test_allowed_files_exact_string_is_skipped():
    assert findings({"a.py": "OldPricer()\n"}, allowed_files=["a.py"]) == []


@pytest.mark.parametrize("allowed", [["./a.py"], ["A.py"], ["a.py "], ["svc/a.py"], ["/a.py"]])
def test_allowed_files_does_not_normalise_paths(allowed):
    assert findings({"a.py": "OldPricer()\n"}, allowed_files=allowed) == [{"file": "a.py", "line": 1, "kind": "name"}]


def test_allowed_files_does_not_normalise_the_source_key_either():
    out = findings({"./a.py": "OldPricer()\n"}, allowed_files=["a.py"])
    assert out == [{"file": "./a.py", "line": 1, "kind": "name"}]


# --- (h) bare str allowed_files: substring match, fail-open ---------------------------------
def test_KNOWN_QUIRK_bare_string_allowed_files_matches_by_substring():
    """allowed_files="svc/a.py" (a str, not a list) skips "a.py" because `path in allowed_files`."""
    assert findings({"a.py": "OldPricer()\n"}, allowed_files="svc/a.py") == []
    assert findings({"a.py": "OldPricer()\n"}, allowed_files="svc/a.py/other.py") == []


def test_bare_string_allowed_files_does_not_match_an_unrelated_path():
    out = findings({"b.py": "OldPricer()\n"}, allowed_files="svc/a.py")
    assert out == [{"file": "b.py", "line": 1, "kind": "name"}]
