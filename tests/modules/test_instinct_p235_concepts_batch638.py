import pytest
from app.modules.instinct_doc import p235_concepts_batch638 as m


def test_representations():
    assert m.representations(1729) == ((1, 12), (9, 10))   # Ta(2)
    assert m.representations(4104) == ((2, 16), (9, 15))   # second
    assert m.representations(91) == ((3, 4),)
    assert m.representations(2) == ((1, 1),)
    assert m.representations(9) == ((1, 2),)
    assert m.representations(3) == ()
    assert m.representations(1000000) == ()                # 100^3 alone is not a sum
    assert m.representation_count(1729) == 2
    assert m.representation_count(91) == 1
    assert m.representation_count(3) == 0
    assert m.is_sum_of_two_cubes(1729) is True
    assert m.is_sum_of_two_cubes(3) is False
    assert m.is_sum_of_two_cubes(999983) is False


def test_cube_roots():
    assert m.icbrt_floor(0) == 0
    assert m.icbrt_floor(1) == 1
    assert m.icbrt_floor(7) == 1
    assert m.icbrt_floor(8) == 2
    assert m.icbrt_floor(999) == 9
    assert m.icbrt_floor(1000) == 10
    assert m.icbrt_floor(10 ** 18) == 10 ** 6
    assert m.icbrt_floor(10 ** 18 - 1) == 999999
    assert m.is_perfect_cube(1000) is True
    assert m.is_perfect_cube(1001) is False
    assert m.is_perfect_cube(0) is True
    assert m.is_perfect_cube(10 ** 18) is True


def test_taxicab():
    assert m.taxicab(1) == 2
    assert m.taxicab(2) == 1729
    assert m.taxicab(3) is None                            # Ta(3) = 87539319 > N_MAX
    assert m.taxicab(4) is None


def test_certificates():
    assert m.representations_check(1729, ((1, 12), (9, 10))) is True
    assert m.representations_check(1729, ((1, 12),)) is False
    assert m.representations_check(1729, ((9, 10), (1, 12))) is False
    assert m.representations_check(91, ((3, 4),)) is True
    assert m.representations_check(3, ()) is True
    assert m.count_check(1729, 2) is True
    assert m.count_check(1729, 1) is False
    assert m.count_check(3, 0) is True
    assert m.taxicab_check(2, 1729) is True
    assert m.taxicab_check(2, 4104) is False
    assert m.taxicab_check(3, None) is True
    assert m.taxicab_check(1, 2) is True


def test_validation_refusals():
    with pytest.raises(ValueError, match='P235:representations:bad_type:n$'):
        m.representations(True)
    with pytest.raises(ValueError, match='P235:representations:bad_value:n$'):
        m.representations(0)
    with pytest.raises(ValueError, match='P235:representations:bad_value:n$'):
        m.representations(10 ** 6 + 1)
    with pytest.raises(ValueError, match='P235:icbrt_floor:bad_value:n$'):
        m.icbrt_floor(-1)
    with pytest.raises(ValueError, match='P235:icbrt_floor:bad_value:n$'):
        m.icbrt_floor(10 ** 18 + 1)
    with pytest.raises(ValueError, match='P235:taxicab:bad_value:k$'):
        m.taxicab(0)
    with pytest.raises(ValueError, match='P235:taxicab:bad_value:k$'):
        m.taxicab(5)
    with pytest.raises(ValueError, match='P235:representations_check:bad_type:cert$'):
        m.representations_check(1729, [(1, 12), (9, 10)])
    with pytest.raises(ValueError, match='P235:representations_check:bad_type:cert element$'):
        m.representations_check(1729, ((1, 12, 3),))
    with pytest.raises(ValueError, match='P235:representations_check:bad_type:cert element$'):
        m.representations_check(1729, (('a', 12),))
    with pytest.raises(ValueError, match='P235:representations_check:bad_value:cert element$'):
        m.representations_check(1729, ((0, 12),))
    with pytest.raises(ValueError, match='P235:representations_check:bad_value:cert element$'):
        m.representations_check(1729, ((1, 101),))
    with pytest.raises(ValueError, match='P235:representations_check:bad_type:n$'):
        m.representations_check('n', ((1, 12),))
    with pytest.raises(ValueError, match='P235:count_check:bad_type:cert$'):
        m.count_check(1729, 'two')
    with pytest.raises(ValueError, match='P235:count_check:bad_value:cert$'):
        m.count_check(1729, 65)
    with pytest.raises(ValueError, match='P235:count_check:bad_value:cert$'):
        m.count_check(1729, -1)
    with pytest.raises(ValueError, match='P235:taxicab_check:bad_value:cert$'):
        m.taxicab_check(2, 10 ** 6 + 1)


def test_audit_pins_boundaries():
    # lower range bound on n is exactly 1
    assert m.representations(1) == ()
    assert m.representation_count(1) == 0
    assert m.is_sum_of_two_cubes(1) is False
    assert m.representations_check(1, ()) is True
    assert m.count_check(1, 0) is True
    # a single representation suffices
    assert m.is_sum_of_two_cubes(9) is True
    # cert == 1 is inside 1..N_MAX and simply mismatches taxicab(1) == 2
    assert m.taxicab_check(1, 1) is False
    # cert length exactly SEQ_MAX passes the cap; content then mismatches
    cert = ((1, 12), (9, 10)) + ((1, 1),) * 62
    assert len(cert) == m.SEQ_MAX == 64
    assert m.representations_check(1729, cert) is False
    # element value B_MAX is in range; the pair just is not a representation
    assert m.representations_check(3, ((100, 100),)) is False
    # element value 1 is in range
    assert m.representations_check(2, ((1, 1),)) is True


def test_audit_pins_validation_order():
    # scalar types positional across args, then scalar ranges positional
    with pytest.raises(ValueError, match='P235:count_check:bad_type:cert$'):
        m.count_check(0, True)
    with pytest.raises(ValueError, match='P235:count_check:bad_type:n$'):
        m.count_check('0', True)
    with pytest.raises(ValueError, match='P235:count_check:bad_value:n$'):
        m.count_check(0, 65)
    with pytest.raises(ValueError, match='P235:count_check:bad_value:cert$'):
        m.count_check(2, 65)
    with pytest.raises(ValueError, match='P235:taxicab_check:bad_type:cert$'):
        m.taxicab_check(0, True)
    with pytest.raises(ValueError, match='P235:taxicab_check:bad_value:k$'):
        m.taxicab_check(0, 10 ** 6 + 1)
    with pytest.raises(ValueError, match='P235:taxicab_check:bad_value:k$'):
        m.taxicab_check(0, None)
