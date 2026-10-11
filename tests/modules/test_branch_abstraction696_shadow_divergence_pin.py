"""Row 696 Branch by Abstraction: shadow divergence gate pin and small construction pins (tests only)."""
import pytest

from app.modules.m20_general_cognitive_worker.branch_abstraction696 import (
    BranchAbstractionError,
    BranchByAbstraction,
)


class Old:
    def price(self, q):
        return q * 10


class New:
    """Same as Old except for q == 7, which only the shadow route can reveal here."""

    def price(self, q):
        return q * 10 + (1 if q == 7 else 0)


def ready_with_shadow_divergence():
    b = BranchByAbstraction("Pricer", ["price"], Old(), New())
    b.register_caller("c")
    b.mark_caller_migrated("c")
    b.verify_equivalence("price", [((1,), {}), ((2,), {})])  # equal on these inputs: equivalence gate passes
    b.scan_direct_usage({"a.py": "x = 1\n"}, "Pricer")
    b.set_route("shadow")
    assert b.call("price", 7) == 70  # shadow returns the OLD result and records the divergence
    b.set_route("new")
    return b


def test_shadow_divergence_is_recorded_from_the_real_old_and_new_routes():
    b = ready_with_shadow_divergence()
    assert b.divergences == [{"operation": "price", "old": "70", "new": "71"}]
    assert b.route_log[-1] == ("price", "old")


def test_shadow_divergence_alone_blocks_removal_with_the_exact_entry():
    b = ready_with_shadow_divergence()
    assert b.can_remove_old() == (False, ["1 shadow divergence(s) recorded"])


def test_remove_old_refuses_with_the_exact_message_and_keeps_the_old_implementation():
    b = ready_with_shadow_divergence()
    with pytest.raises(BranchAbstractionError) as ei:
        b.remove_old()
    assert str(ei.value) == "removal refused: 1 shadow divergence(s) recorded"
    assert b._old is not None and b.phase != "old_removed"


def test_without_a_shadow_call_the_same_setup_is_clear():
    b = BranchByAbstraction("Pricer", ["price"], Old(), New())
    b.register_caller("c")
    b.mark_caller_migrated("c")
    b.verify_equivalence("price", [((1,), {})])
    b.scan_direct_usage({"a.py": "x = 1\n"}, "Pricer")
    b.set_route("new")
    assert b.can_remove_old() == (True, [])


def test_two_shadow_divergences_are_counted():
    b = ready_with_shadow_divergence()
    b.set_route("shadow")
    b.call("price", 7)
    b.set_route("new")
    assert b.can_remove_old() == (False, ["2 shadow divergence(s) recorded"])


# --- small construction and call pins ---------------------------------------------------------------
@pytest.mark.parametrize("name", ["", "   ", None, 5])
def test_abstraction_name_must_be_a_non_blank_string(name):
    with pytest.raises(BranchAbstractionError) as ei:
        BranchByAbstraction(name, ["price"], Old(), New())
    assert str(ei.value) == "abstraction name is required"


@pytest.mark.parametrize("ops", [[], None, [""], [5], ["price", ""], ["price", None]])
def test_operation_names_must_all_be_non_empty_strings(ops):
    with pytest.raises(BranchAbstractionError) as ei:
        BranchByAbstraction("P", ops, Old(), New())
    assert str(ei.value) == "at least one operation name is required"


def test_unknown_operation_is_refused_by_call_and_by_verify_equivalence():
    b = BranchByAbstraction("P", ["price"], Old(), New())
    with pytest.raises(BranchAbstractionError) as ei:
        b.call("nope", 1)
    assert str(ei.value) == "unknown operation nope"
    with pytest.raises(BranchAbstractionError) as ej:
        b.verify_equivalence("nope", [((1,), {})])
    assert str(ej.value) == "unknown operation nope"
    assert b.route_log == [] and b._equiv == {}


def test_canary_default_percent_is_zero_so_every_key_routes_old():
    b = BranchByAbstraction("P", ["price"], Old(), New())
    b.set_route("canary")
    assert b._canary_percent == 0
    assert {b.route_for(k) for k in range(200)} == {"old"}
