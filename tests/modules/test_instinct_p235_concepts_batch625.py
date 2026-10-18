import pytest
from fractions import Fraction as F
from app.modules.instinct_doc import p235_concepts_batch625 as m


def test_counts_and_sum_exact():
    assert (m.farey_count(1), m.farey_count(2), m.farey_count(3), m.farey_count(4), m.farey_count(5)) == (2, 3, 5, 7, 11)
    assert m.farey_count(10) == 33
    assert m.farey_sum(4) == F(7, 2)
    assert m.farey_sum(1) == F(1, 2) * 2 / 2 + F(1, 2)  # (0/1 + 1/1) = 1
    assert m.farey_sum(5) == F(11, 2)


def test_seq_and_term_exact():
    assert m.farey_seq(1) == ((0, 1), (1, 1))
    assert m.farey_seq(4) == ((0, 1), (1, 4), (1, 3), (1, 2), (2, 3), (3, 4), (1, 1))
    assert m.farey_term(5, 0) == (0, 1)
    assert m.farey_term(5, 4) == (2, 5)
    assert m.farey_term(5, 10) == (1, 1)
    assert m.farey_term(1, 1) == (1, 1)


def test_rank_members_and_nonmembers():
    assert m.farey_rank(5, 0, 1) == 0
    assert m.farey_rank(5, 1, 1) == 10
    assert m.farey_rank(5, 2, 5) == 4
    assert m.farey_rank(5, 3, 4) == 8
    assert m.farey_rank(5, 2, 4) is None      # not reduced
    assert m.farey_rank(4, 1, 5) is None      # denominator above order
    assert m.farey_rank(5, 3, 2) is None      # above 1


def test_seq_check_roundtrip_and_wrong():
    assert m.seq_check(4, m.farey_seq(4)) is True
    assert m.seq_check(1, ((0, 1), (1, 1))) is True
    wrong = list(m.farey_seq(4)); wrong[2] = (1, 2)
    assert m.seq_check(4, tuple(wrong)) is False


def test_mediant_and_between():
    assert m.mediant(1, 3, 1, 2) == (2, 5)
    assert m.mediant(0, 1, 1, 1) == (1, 2)
    assert m.mediant_between(1, 3, 1, 2) is True
    assert m.mediant_between(1, 2, 1, 3) is False
    assert m.mediant_between(1, 2, 1, 2) is False


def test_neighbor_certificate():
    assert m.neighbor_check(3, 0, 1, 1, 3) is True
    assert m.neighbor_check(3, 1, 3, 1, 2) is True   # adjacent in F3
    assert m.neighbor_check(4, 1, 3, 1, 2) is True   # adjacent in F4
    assert m.neighbor_check(3, 1, 2, 1, 3) is False  # reversed order
    assert m.neighbor_check(3, 0, 1, 1, 2) is False  # b + d == n, 1/4 intervenes later
    assert m.neighbor_check(4, 0, 1, 1, 3) is False  # 1/4 intervenes at order 4
    assert m.neighbor_check(2, 0, 1, 1, 2) is True
    assert m.neighbor_check(3, 1, 2, 2, 3) is True
    assert m.neighbor_check(3, 2, 3, 3, 4) is False  # denominator above order


def test_mediant_witness():
    assert m.mediant_witness(3, 0, 1, 1, 3) == 4
    assert m.mediant_witness(3, 1, 2, 2, 3) == 5
    assert m.mediant_witness(3, 1, 2, 1, 3) is None  # reversed
    assert m.mediant_witness(4, 0, 1, 1, 3) is None  # not adjacent at order 4
    assert m.mediant_witness(3, 2, 3, 3, 4) is None  # denominator above order


def test_stern_brocot_paths():
    assert m.stern_brocot_path(1, 1) == ''
    assert m.stern_brocot_path(1, 2) == 'L'
    assert m.stern_brocot_path(2, 1) == 'R'
    assert m.stern_brocot_path(2, 5) == 'LLR'
    assert m.stern_brocot_path(5, 2) == 'RRL'
    assert m.stern_brocot_path(1, 4) == 'LLL'
    assert m.stern_brocot_path(3, 7) == 'LLRR'
    assert m.stern_brocot_depth(1, 1) == 0
    assert m.stern_brocot_depth(2, 5) == 3
    assert m.stern_brocot_depth(1, 4) == 3


def test_stern_brocot_check_roundtrip():
    for a, b in ((1, 1), (2, 5), (5, 2), (3, 7), (7, 3), (1, 4), (4, 1), (1, 512), (511, 512)):
        assert m.stern_brocot_check(a, b, m.stern_brocot_path(a, b)) is True
    assert m.stern_brocot_check(2, 5, 'LRL') is False
    assert m.stern_brocot_check(2, 5, 'LLRR') is False
    assert m.stern_brocot_check(1, 1, '') is True
    assert m.stern_brocot_check(1, 1, 'L') is False


def test_validation_refusals():
    with pytest.raises(ValueError, match='P235:farey_count:bad_type:n'):
        m.farey_count(True)
    with pytest.raises(ValueError, match='P235:farey_count:bad_value:n'):
        m.farey_count(0)
    with pytest.raises(ValueError, match='P235:farey_term:bad_value:k'):
        m.farey_term(5, 11)
    with pytest.raises(ValueError, match='P235:mediant:bad_value:first'):
        m.mediant(2, 4, 1, 2)                      # not reduced
    with pytest.raises(ValueError, match='P235:mediant:bad_value:second'):
        m.mediant(1, 2, 3, 2)                      # above 1
    with pytest.raises(ValueError, match='P235:neighbor_check:bad_type:first den'):
        m.neighbor_check(3, 0, True, 1, 3)
    with pytest.raises(ValueError, match='P235:stern_brocot_path:bad_value:target'):
        m.stern_brocot_path(2, 4)                  # not reduced
    with pytest.raises(ValueError, match='P235:stern_brocot_check:bad_type:cert'):
        m.stern_brocot_check(2, 5, ('L', 'L', 'R'))
    with pytest.raises(ValueError, match='P235:stern_brocot_check:bad_value:cert element'):
        m.stern_brocot_check(2, 5, 'LLX')
    with pytest.raises(ValueError, match='P235:seq_check:bad_type:cert'):
        m.seq_check(4, list(m.farey_seq(4)))
    with pytest.raises(ValueError, match='P235:seq_check:bad_shape:cert'):
        m.seq_check(4, m.farey_seq(3))
    with pytest.raises(ValueError, match='P235:seq_check:bad_value:cert element'):
        m.seq_check(4, ((0, 1),) * 6 + ((1, 513),))


def test_boundary_length_and_element_type_pins():
    big = ((0, 1),) * 100000  # exactly SEQ_MAX: passes the cap, fails the shape check
    with pytest.raises(ValueError, match='P235:seq_check:bad_shape:cert'):
        m.seq_check(4, big)
    with pytest.raises(ValueError, match='P235:seq_check:bad_type:cert element'):
        m.seq_check(4, ((F(1, 2), 1),) * 7)  # non-int numerator caught in the type phase


def test_mutation_battery_pins():
    assert m.seq_check(4, ((512, 511),) * 7) is False        # numerator at N_MAX stays inside the cap
    assert m.seq_check(4, ((0, 512),) * 7) is False          # denominator at N_MAX stays inside the cap
    with pytest.raises(ValueError, match='P235:seq_check:bad_value:cert element'):
        m.seq_check(4, ((-1, 1),) * 7)                       # negative numerator caught per-element
    assert m.farey_rank(1, 0, 1) == 0                        # order 1 accepted
    assert m.neighbor_check(1, 0, 1, 1, 1) is True           # F1 endpoints are adjacent
    assert m.mediant_witness(1, 0, 1, 1, 1) == 2
    assert m.mediant_witness(3, 1, 3, 1, 2) == 5             # denominator equal to the order is allowed
    assert m.stern_brocot_depth(3, 1) == 2                   # R-first descent keeps exact steps
    assert m.stern_brocot_check(2, 5, 'L' * 8192) is False   # path at PATH_MAX stays inside the cap
