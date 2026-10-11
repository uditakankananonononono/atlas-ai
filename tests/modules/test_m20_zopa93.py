"""Row 93 ZOPA Mapping: declared-interval intersection, tests written before the core."""
import itertools
from fractions import Fraction

import pytest

from app.modules.m20_general_cognitive_worker.zopa93 import ZopaError, map_zopa


def iv(i, lo, hi, li=True, hi_inc=True, **kw):
    d = {"id": i, "low": lo, "high": hi, "low_inclusive": li, "high_inclusive": hi_inc}
    d.update(kw)
    return d


def req(buyer, seller, currency="USD", unit="per_unit"):
    return {"currency": currency, "unit": unit, "buyer_intervals": buyer, "seller_intervals": seller}


def member(r, x):
    for z in r["zopa_intervals"]:
        lo, hi = Fraction(z["low"]), Fraction(z["high"])
        if (x > lo or (x == lo and z["low_inclusive"])) and (x < hi or (x == hi and z["high_inclusive"])):
            return True
    return False


def in_iv(d, x):
    lo, hi = Fraction(d["low"]), Fraction(d["high"])
    return (x > lo or (x == lo and d["low_inclusive"])) and (x < hi or (x == hi and d["high_inclusive"]))


def test_simple_overlap_with_provenance_and_limits():
    r = map_zopa(req([iv("b1", 90, 100)], [iv("s1", 80, 95)]))
    assert r["status"] == "overlap"
    assert r["zopa_intervals"] == [
        {"low": "90", "high": "95", "low_inclusive": True, "high_inclusive": True,
         "buyer_ids": ["b1"], "seller_ids": ["s1"]}
    ]
    assert r["currency"] == "USD" and r["unit"] == "per_unit"
    assert r["overlap_is_agreement"] is False and r["inferred_reservation_values"] is False
    assert "overlap is not agreement" in r["limits"].lower()
    assert r["limits"]


def test_no_overlap_is_not_a_claim_about_agreement():
    r = map_zopa(req([iv("b", 1, 2)], [iv("s", 3, 4)]))
    assert r["status"] == "no_overlap" and r["zopa_intervals"] == []
    assert r["overlap_is_agreement"] is False


def test_touching_endpoints_inclusive_vs_open():
    assert map_zopa(req([iv("b", 0, 5)], [iv("s", 5, 9)]))["zopa_intervals"][0]["low"] == "5"
    r = map_zopa(req([iv("b", 0, 5, hi_inc=False)], [iv("s", 5, 9)]))
    assert r["status"] == "no_overlap"
    r = map_zopa(req([iv("b", 0, 5)], [iv("s", 5, 9, li=False)]))
    assert r["status"] == "no_overlap"
    r = map_zopa(req([iv("b", 0, 5)], [iv("s", 5, 9)]))
    z = r["zopa_intervals"][0]
    assert z["low"] == z["high"] == "5" and z["low_inclusive"] and z["high_inclusive"]


def test_multiple_disjoint_alternatives_preserved_with_provenance():
    b = [iv("b1", 0, 10), iv("b2", 20, 30)]
    s = [iv("s1", 5, 25)]
    r = map_zopa(req(b, s))
    assert [(z["low"], z["high"]) for z in r["zopa_intervals"]] == [("5", "10"), ("20", "25")]
    assert r["zopa_intervals"][0]["buyer_ids"] == ["b1"] and r["zopa_intervals"][1]["buyer_ids"] == ["b2"]
    assert r["zopa_intervals"][0]["seller_ids"] == ["s1"] and r["zopa_intervals"][1]["seller_ids"] == ["s1"]


def test_union_normalization_merges_overlap_and_touching_closed():
    r = map_zopa(req([iv("b1", 0, 5), iv("b2", 5, 9)], [iv("s", 0, 100)]))
    assert len(r["zopa_intervals"]) == 1
    z = r["zopa_intervals"][0]
    assert (z["low"], z["high"]) == ("0", "9") and z["buyer_ids"] == ["b1", "b2"]


def test_half_open_touching_merges_but_both_open_does_not():
    r = map_zopa(req([iv("b1", 0, 5, hi_inc=False), iv("b2", 5, 9)], [iv("s", 0, 100)]))
    assert len(r["zopa_intervals"]) == 1
    r = map_zopa(req([iv("b1", 0, 5, hi_inc=False), iv("b2", 5, 9, li=False)], [iv("s", 0, 100)]))
    assert [(z["low"], z["high"], z["high_inclusive"], z["low_inclusive"]) for z in r["zopa_intervals"]] == [
        ("0", "5", False, True), ("5", "9", True, False)]


def test_rational_and_string_inputs_exact():
    r = map_zopa(req([iv("b", "1/3", "2/3")], [iv("s", "0.5", 1)]))
    z = r["zopa_intervals"][0]
    assert (z["low"], z["high"]) == ("1/2", "2/3")
    r = map_zopa(req([iv("b", 0.1, 0.3)], [iv("s", 0.2, 0.4)]))
    assert (r["zopa_intervals"][0]["low"], r["zopa_intervals"][0]["high"]) == ("1/5", "3/10")


def test_order_independence():
    b = [iv("b1", 0, 4), iv("b2", 6, 10), iv("b3", 3, 7, li=False)]
    s = [iv("s1", 2, 8), iv("s2", 9, 12, hi_inc=False)]
    base = map_zopa(req(b, s))
    for pb in itertools.permutations(b):
        for ps in itertools.permutations(s):
            assert map_zopa(req(list(pb), list(ps))) == base


def test_idempotent_on_own_output_shape():
    b = [iv("b1", 0, 4), iv("b2", 3, 10)]
    s = [iv("s1", 2, 8)]
    r1 = map_zopa(req(b, s))
    z = r1["zopa_intervals"]
    r2 = map_zopa(req([iv("b", z[0]["low"], z[0]["high"], z[0]["low_inclusive"], z[0]["high_inclusive"])],
                      [iv("s", z[0]["low"], z[0]["high"], z[0]["low_inclusive"], z[0]["high_inclusive"])]))
    assert [(a["low"], a["high"]) for a in r2["zopa_intervals"]] == [(a["low"], a["high"]) for a in z]


@pytest.mark.parametrize("bl,bh,bli,bhi", [(a, b, li, hi) for a in range(4) for b in range(a, 4) for li in (True, False) for hi in (True, False) if a < b or (li and hi)])
def test_exhaustive_single_pair_oracle(bl, bh, bli, bhi):
    # grid of half-integers covers every endpoint and every open gap between integer endpoints
    buyer = iv("b", bl, bh, bli, bhi)
    for sl in range(4):
        for sh in range(sl, 4):
            for sli in (True, False):
                for shi in (True, False):
                    if sl == sh and not (sli and shi):
                        continue
                    seller = iv("s", sl, sh, sli, shi)
                    r = map_zopa(req([buyer], [seller]))
                    for k in range(-2, 11):
                        x = Fraction(k, 2)
                        want = in_iv(buyer, x) and in_iv(seller, x)
                        assert member(r, x) == want, (buyer, seller, x)
                    assert (r["status"] == "overlap") == any(
                        in_iv(buyer, Fraction(k, 2)) and in_iv(seller, Fraction(k, 2)) for k in range(-2, 11))


def test_multi_interval_oracle_pseudo_exhaustive():
    import random
    rng = random.Random(93)
    def rand_side(prefix):
        out = []
        for n in range(rng.randint(1, 3)):
            lo = rng.randint(0, 6); hi = rng.randint(lo, 7)
            li, hi_i = rng.choice([True, False]), rng.choice([True, False])
            if lo == hi:
                li = hi_i = True
            out.append(iv(f"{prefix}{n}", lo, hi, li, hi_i))
        return out
    for _ in range(400):
        b, s = rand_side("b"), rand_side("s")
        r = map_zopa(req(b, s))
        for k in range(-2, 17):
            x = Fraction(k, 2)
            want = any(in_iv(d, x) for d in b) and any(in_iv(d, x) for d in s)
            assert member(r, x) == want
        # normalized: sorted, no two intervals mergeable
        zs = r["zopa_intervals"]
        for a, c in zip(zs, zs[1:]):
            assert Fraction(a["high"]) < Fraction(c["low"]) or (
                Fraction(a["high"]) == Fraction(c["low"]) and not a["high_inclusive"] and not c["low_inclusive"])


@pytest.mark.parametrize("bad", [
    dict(low=5, high=1),
    dict(low=5, high=5, low_inclusive=False),
    dict(low=5, high=5, high_inclusive=False),
    dict(low="x", high=1),
    dict(low=float("nan"), high=1),
    dict(low=0, high=float("inf")),
    dict(low=True, high=1),
    dict(low=None, high=1),
    dict(low=0, high=1, low_inclusive="yes"),
])
def test_invalid_interval_refused(bad):
    b = iv("b", 0, 1)
    b.update(bad)
    with pytest.raises(ZopaError):
        map_zopa(req([b], [iv("s", 0, 1)]))


def test_missing_currency_unit_and_mismatch_refused():
    with pytest.raises(ZopaError):
        map_zopa({"buyer_intervals": [iv("b", 0, 1)], "seller_intervals": [iv("s", 0, 1)], "unit": "u"})
    with pytest.raises(ZopaError):
        map_zopa({"currency": "USD", "buyer_intervals": [iv("b", 0, 1)], "seller_intervals": [iv("s", 0, 1)]})
    with pytest.raises(ZopaError):
        map_zopa(req([iv("b", 0, 1, currency="EUR")], [iv("s", 0, 1)]))
    with pytest.raises(ZopaError):
        map_zopa(req([iv("b", 0, 1, unit="per_kg")], [iv("s", 0, 1)]))
    with pytest.raises(ZopaError):
        map_zopa(req([iv("b", 0, 1)], [iv("s", 0, 1)], currency=""))
    # matching per-interval currency is accepted
    assert map_zopa(req([iv("b", 0, 1, currency="USD")], [iv("s", 0, 1)]))["status"] == "overlap"


def test_duplicate_ids_refused_within_and_across_sides():
    with pytest.raises(ZopaError):
        map_zopa(req([iv("x", 0, 1), iv("x", 2, 3)], [iv("s", 0, 3)]))
    with pytest.raises(ZopaError):
        map_zopa(req([iv("x", 0, 1)], [iv("x", 0, 1)]))


def test_missing_or_empty_sides_and_bad_ids_refused():
    with pytest.raises(ZopaError):
        map_zopa(req([], [iv("s", 0, 1)]))
    with pytest.raises(ZopaError):
        map_zopa(req([iv("b", 0, 1)], []))
    with pytest.raises(ZopaError):
        map_zopa(req([iv("", 0, 1)], [iv("s", 0, 1)]))
    with pytest.raises(ZopaError):
        map_zopa(req([iv(3, 0, 1)], [iv("s", 0, 1)]))
    with pytest.raises(ZopaError):
        map_zopa([1])
    with pytest.raises(ZopaError):
        map_zopa(dict(req([iv("b", 0, 1)], [iv("s", 0, 1)]), reservation_estimate=5))


def test_no_inference_or_message_fields_in_output():
    r = map_zopa(req([iv("b", 0, 10, source="doc-1")], [iv("s", 5, 15, source="doc-2")]))
    assert r["sources"] == {"b": "doc-1", "s": "doc-2"}
    forbidden = {"recommended_price", "suggested_offer", "message", "persuasion", "predicted_agreement"}
    assert not forbidden & set(r)


def test_input_not_mutated():
    b = [iv("b", 0, 10)]
    s = [iv("s", 5, 15)]
    snap = (repr(b), repr(s))
    map_zopa(req(b, s))
    assert (repr(b), repr(s)) == snap


# --- second-audit pins (replacement owner; core frozen, pins only) ---
from app.modules.m20_general_cognitive_worker.zopa93 import _contains, _normalize


def _fiv(lo, hi, li, hi_i):
    return {"lo": Fraction(lo), "hi": Fraction(hi), "li": li, "hi_i": hi_i}


def test_contains_inclusive_low_at_bound_contained():
    assert _contains(_fiv(0, 10, True, True), Fraction(0)) is True


def test_contains_exclusive_low_at_bound_excluded():
    assert _contains(_fiv(0, 10, False, True), Fraction(0)) is False


def test_contains_inclusive_high_at_bound_contained():
    assert _contains(_fiv(0, 10, True, True), Fraction(10)) is True


def test_contains_exclusive_high_at_bound_excluded():
    assert _contains(_fiv(0, 10, True, False), Fraction(10)) is False


def test_contains_strictly_inside_contained_regardless_of_flags():
    assert _contains(_fiv(0, 10, False, False), Fraction(5)) is True


def test_contains_below_low_excluded():
    assert _contains(_fiv(0, 10, True, True), Fraction(-1)) is False


def test_contains_above_high_excluded():
    assert _contains(_fiv(0, 10, True, True), Fraction(11)) is False


def test_num_guard_arms_independently_for_nan_and_infinities():
    # The finite guard raises ZopaError (a ValueError) inside a try whose
    # except wraps ValueErrors, so the outer message is the wrapper's; the
    # guard's own arming is observable on the exception's __cause__.
    for name in ("low", "high"):
        for bad in (float("nan"), float("inf"), float("-inf")):
            b = iv("b", 0, 1); b[name] = bad
            with pytest.raises(ZopaError) as e:
                map_zopa(req([b], [iv("s", 0, 1)]))
            assert str(e.value) == f"{name} is not a valid number", bad
            assert isinstance(e.value.__cause__, ZopaError), bad
            assert str(e.value.__cause__) == f"{name} must be finite", bad


def test_missing_inclusivity_keys_default_inclusive():
    b = {"id": "b", "low": 0, "high": 5}
    s = {"id": "s", "low": 5, "high": 9}
    r = map_zopa(req([b], [s]))
    assert r["status"] == "overlap"
    z = r["zopa_intervals"][0]
    assert z["low"] == z["high"] == "5" and z["low_inclusive"] and z["high_inclusive"]


def test_normalize_same_low_inclusive_sorts_first_and_survives_merge():
    merged = _normalize([
        dict(_fiv(0, 5, False, True), id="x", source=None),
        dict(_fiv(0, 9, True, True), id="y", source=None),
    ])
    assert len(merged) == 1
    assert merged[0]["li"] is True
    assert merged[0]["lo"] == 0 and merged[0]["hi"] == 9


def test_feature_row_is_exactly_93():
    r = map_zopa(req([iv("b", 0, 1)], [iv("s", 0, 1)]))
    assert r["feature_row"] == 93


def test_same_low_buyer_intervals_merge_keeps_inclusive_lower_endpoint():
    # L99 sort-key pin via the public map_zopa path: two same-low pieces with different
    # lower inclusivity must merge so the inclusive lower endpoint survives.
    # Buyer intervals [lo,3] inclusive and (lo,5) exclusive intersect a covering seller
    # to produce the two same-low pieces that reach _normalize.
    b = [iv("b1", 0, 3), iv("b2", 0, 5, li=False)]
    r = map_zopa(req(b, [iv("s1", 0, 10)]))
    assert r["status"] == "overlap"
    assert r["zopa_intervals"] == [
        {"low": "0", "high": "5", "low_inclusive": True, "high_inclusive": True,
         "buyer_ids": ["b1", "b2"], "seller_ids": ["s1"]}
    ]
