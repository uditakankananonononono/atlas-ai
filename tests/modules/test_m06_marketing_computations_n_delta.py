"""Hardening pins for legacy marketing_computations._n (delta on main 298fe826).

SOURCE repair (marketing_computations.py, one catch clause). _n leaked raw
OverflowError on huge int values/defaults (float(10**400)) and raw RuntimeError
on hostile __float__/__index__ objects. Contract kept verbatim: raise
ValueError "<key> must be numeric". Every pin verified failing raw on the
298fe826 pre-image; valid-input behavior byte-identical.
"""
import pytest

from app.modules.m06_social_media_manager.marketing_computations import _n, segmentation


class _HostileFloat:
    def __float__(self): raise RuntimeError("FUZZ_HOSTILE_FLOAT")


class _HostileIndex:
    def __index__(self): raise RuntimeError("FUZZ_HOSTILE_INDEX")


def test_n_huge_int_value_coded():
    with pytest.raises(ValueError, match="customers must be numeric"):
        _n({"customers": 10**400}, "customers")


def test_n_huge_int_default_coded():
    with pytest.raises(ValueError, match="customers must be numeric"):
        _n({}, "customers", 10**400)


def test_n_hostile_float_coded():
    with pytest.raises(ValueError, match="customers must be numeric"):
        _n({"customers": _HostileFloat()}, "customers")


def test_n_hostile_index_coded():
    with pytest.raises(ValueError, match="customers must be numeric"):
        _n({"customers": _HostileIndex()}, "customers")


def test_n_engine_level_huge_int_coded():
    with pytest.raises(ValueError, match="customers must be numeric"):
        segmentation({"facts": {"segment_metrics": [{"name": "a", "customers": 10**400}]}})


def test_n_contract_unchanged():
    assert _n({"k": "3.5"}, "k") == 3.5
    assert _n({"k": 2}, "k") == 2.0
    assert _n({}, "k") == 0.0
    assert _n({"k": 2**64}, "k") == float(2**64)
    with pytest.raises(ValueError, match="k must be numeric"):
        _n({"k": "x"}, "k")
    with pytest.raises(ValueError, match="k must be numeric"):
        _n({"k": None}, "k")
