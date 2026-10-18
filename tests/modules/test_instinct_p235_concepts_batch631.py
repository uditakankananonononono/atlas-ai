import pytest
from app.modules.instinct_doc import p235_concepts_batch631 as m

PLUS = ((0, 0, 1, 4), (1, 0, 4, 1))   # plus-sign union, area 7, perimeter 16
OVER = ((0, 0, 2, 2), (1, 1, 3, 3))   # overlapping squares, area 7, perimeter 12


def test_interval_merge_and_length():
    assert m.interval_union(((1, 3), (2, 4), (6, 8))) == ((1, 4), (6, 8))
    assert m.interval_union(((5, 6),)) == ((5, 6),)
    assert m.interval_union(((-3, -1), (0, 2))) == ((-3, -1), (0, 2))
    assert m.interval_union(((1, 5), (2, 3))) == ((1, 5),)
    assert m.interval_union_length(((1, 3), (2, 4), (6, 8))) == 5
    assert m.interval_union_length(((1, 5), (2, 3))) == 4
    assert m.interval_union(((-2, 0), (-1, 1))) == ((-2, 1),)   # touching merges


def test_interval_certificates():
    assert m.merge_check(((1, 3), (2, 4)), ((1, 4),)) is True
    assert m.merge_check(((1, 3), (2, 4)), ((1, 3), (2, 4))) is False
    assert m.length_check(((1, 3), (2, 4)), 3) is True
    assert m.length_check(((1, 3), (2, 4)), 4) is False
    assert m.is_covered(((1, 3),), 1) is True
    assert m.is_covered(((1, 3),), 2) is True
    assert m.is_covered(((1, 3),), 3) is False   # half-open top end
    assert m.is_covered(((-2, 0),), -2) is True


def test_rectangle_area_and_perimeter():
    assert m.rect_union_area(OVER) == 7
    assert m.rect_union_area(((0, 0, 2, 2), (2, 0, 4, 2))) == 8   # edge-touching
    assert m.rect_union_area(PLUS) == 7
    assert m.rect_union_area(((0, 0, 1, 1),)) == 1
    assert m.rect_union_area(((-2, -2, 0, 0), (0, 0, 2, 2))) == 8
    assert m.rect_union_perimeter(((0, 0, 2, 2),)) == 8
    assert m.rect_union_perimeter(OVER) == 12
    assert m.rect_union_perimeter(PLUS) == 16
    assert m.rect_union_perimeter(((0, 0, 2, 2), (2, 0, 4, 2))) == 12


def test_rectangle_certificates():
    assert m.area_check(OVER, 7) is True
    assert m.area_check(OVER, 8) is False
    assert m.area_check(PLUS, 7) is True
    assert m.rect_overlap((0, 0, 2, 2), (1, 1, 3, 3)) == (1, 1, 2, 2)
    assert m.rect_overlap((0, 0, 1, 1), (1, 1, 2, 2)) is None     # corner touch is not overlap
    assert m.rect_overlap((0, 0, 2, 2), (2, 0, 4, 2)) is None     # edge touch is not overlap
    assert m.rect_contained((1, 1, 2, 2), (0, 0, 3, 3)) is True
    assert m.rect_contained((0, 0, 2, 2), (1, 1, 3, 3)) is False
    assert m.point_covered(OVER, 1, 1) is True
    assert m.point_covered(OVER, 2, 1) is True
    assert m.point_covered(OVER, 3, 3) is False


def test_validation_refusals():
    with pytest.raises(ValueError, match='P235:interval_union:bad_type:ivs'):
        m.interval_union([(1, 2)])
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs element'):
        m.interval_union(((2, 2),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs element'):
        m.interval_union(((3, 2),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_type:ivs element'):
        m.interval_union(((1, 2, 3),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs element'):
        m.interval_union(((0, 65),))
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects element'):
        m.rect_union_area(((0, 0, 0, 1),))
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_value:s'):
        m.rect_overlap((0, 0, 1, 1), (0, 0, 5, 1)[:3] + (0,))
    with pytest.raises(ValueError, match='P235:length_check:bad_type:cert'):
        m.length_check(((1, 2),), 'one')
    with pytest.raises(ValueError, match='P235:is_covered:bad_value:x'):
        m.is_covered(((1, 3),), 65)
    with pytest.raises(ValueError, match='P235:point_covered:bad_type:y'):
        m.point_covered(OVER, 1, True)


IV64 = tuple((-64 + 2 * i, -63 + 2 * i) for i in range(64))   # exactly at SEQ_MAX
RECT64 = tuple((-64 + 2 * i, 0, -63 + 2 * i, 1) for i in range(64))


def test_merge_boundaries():
    assert m.interval_union(((1, 3), (3, 5))) == ((1, 5),)     # touching merges (a<=end)
    assert m.interval_union(((1, 5), (2, 5))) == ((1, 5),)     # nested equal end
    assert m.interval_union(IV64) == IV64                      # len at SEQ_MAX passes
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs$'):
        m.interval_union(IV64 + ((62, 63),))                 # len 65 over cap
    assert m.interval_union(((-64, 64),)) == ((-64, 64),)      # exact C_MAX bounds pass
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs element$'):
        m.interval_union(((-65, 2),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_value:ivs element$'):
        m.interval_union(((-2, 65),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_type:ivs element$'):
        m.interval_union((('a', 1),))
    with pytest.raises(ValueError, match='P235:interval_union:bad_type:ivs element$'):
        m.interval_union(((1, 'a'),))


def test_merge_check_boundaries():
    assert m.merge_check(IV64, IV64) is True                   # cert len at SEQ_MAX passes
    with pytest.raises(ValueError, match='P235:merge_check:bad_value:cert$'):
        m.merge_check(((1, 2),), IV64 + ((62, 63),))
    assert m.merge_check(((1, 2),), ((-64, 64),)) is False     # cert at exact bounds
    assert m.merge_check(((1, 2),), ((64, 64),)) is False      # cert v[0] at C_MAX
    assert m.merge_check(((1, 2),), ((-64, -64),)) is False    # cert v[1] at -C_MAX
    with pytest.raises(ValueError, match='P235:merge_check:bad_value:cert element$'):
        m.merge_check(((1, 2),), ((-65, 2),))
    with pytest.raises(ValueError, match='P235:merge_check:bad_type:cert element$'):
        m.merge_check(((1, 2),), (('a', 1),))
    with pytest.raises(ValueError, match='P235:merge_check:bad_type:ivs$'):
        m.merge_check('x', 'x')                                # ivs phase before cert phase


def test_length_check_boundaries():
    assert m.length_check(((1, 2),), 0) is False               # cert 0 passes validation
    assert m.length_check(((1, 2),), 128) is False             # cert at 2*C_MAX passes
    with pytest.raises(ValueError, match='P235:length_check:bad_value:cert$'):
        m.length_check(((1, 2),), 129)
    with pytest.raises(ValueError, match='P235:length_check:bad_type:ivs$'):
        m.length_check('x', 'x')                               # container before scalar cert


def test_is_covered_boundaries():
    assert m.is_covered(((1, 3),), -64) is False               # x at -C_MAX passes
    assert m.is_covered(((1, 3),), 64) is False                # x at C_MAX passes
    assert m.is_covered(((-64, -63),), -64) is True            # covered at lower bound
    with pytest.raises(ValueError, match='P235:is_covered:bad_value:x$'):
        m.is_covered(((1, 3),), -65)


def test_rect_boundaries():
    assert m.rect_union_area(((5, 0, 6, 1),)) == 1             # x coords disjoint from y
    assert m.rect_union_area(((0, 5, 2, 6),)) == 2
    assert m.rect_union_area(RECT64) == 64                     # len at SEQ_MAX passes
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects$'):
        m.rect_union_area(RECT64 + ((0, 0, 1, 2),))
    assert m.rect_union_area(((-64, -64, 64, 64),)) == 16384   # exact C_MAX bounds pass
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects element$'):
        m.rect_union_area(((0, 0, 65, 1),))
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_type:rects element$'):
        m.rect_union_area(((0, 0, 1),))
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_type:rects element$'):
        m.rect_union_area(([0, 0, 1, 1],))
    for bad in ((0.5, 0, 1, 1), (0, 0.5, 1, 1), (0, 0, 1.5, 1), (0, 0, 1, 1.5)):
        with pytest.raises(ValueError, match='P235:rect_union_area:bad_type:rects element$'):
            m.rect_union_area((bad,))
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects element$'):
        m.rect_union_area(((3, 0, 2, 4),))                     # x order fails
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects element$'):
        m.rect_union_area(((1, 0, 1, 2),))                     # x degenerate
    with pytest.raises(ValueError, match='P235:rect_union_area:bad_value:rects element$'):
        m.rect_union_area(((0, 3, 1, 3),))                     # y degenerate


def test_area_check_boundaries():
    assert m.area_check(((0, 0, 1, 1),), 0) is False           # cert 0 passes validation
    assert m.area_check(((0, 0, 1, 1),), 16384) is False       # cert at 4*C_MAX*C_MAX
    with pytest.raises(ValueError, match='P235:area_check:bad_value:cert$'):
        m.area_check(((0, 0, 1, 1),), 16385)
    with pytest.raises(ValueError, match='P235:area_check:bad_type:rects$'):
        m.area_check('x', 'x')                                 # container before scalar cert


def test_rect_pair_boundaries():
    assert m.rect_overlap((0, 0, 2, 2), (0, 2, 2, 4)) is None  # horizontal edge touch
    assert m.rect_overlap((2, 0, 4, 1), (0, 0, 1, 1)) is None  # x-disjoint, y inside
    assert m.rect_overlap((-64, -64, 64, 64), (-64, -64, 64, 64)) == (-64, -64, 64, 64)
    assert m.rect_contained((0, 0, 2, 2), (0, 0, 2, 2)) is True    # shared edges
    assert m.rect_contained((0, 5, 1, 6), (0, 0, 3, 3)) is False   # y outside
    assert m.rect_contained((5, 0, 6, 1), (0, 0, 3, 3)) is False   # x outside
    assert m.rect_contained((0, 0, 4, 1), (0, 0, 3, 3)) is False   # x2 exceeds
    assert m.rect_contained((0, 0, 1, 4), (0, 0, 3, 3)) is False   # y2 exceeds
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_type:s$'):
        m.rect_overlap((1, 0, 1, 2), 'x')   # s shape phase before r well-formedness
    with pytest.raises(ValueError, match='P235:rect_contained:bad_type:s$'):
        m.rect_contained((1, 0, 1, 2), 'x')
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_type:r$'):
        m.rect_overlap([0, 0, 1, 1], (0, 0, 1, 1))
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_type:s$'):
        m.rect_overlap((0, 0, 1, 1), (0.5, 0, 1, 1))
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_value:r$'):
        m.rect_overlap((0, 0, 65, 1), (0, 0, 1, 1))
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_value:r$'):
        m.rect_overlap((1, 0, 1, 2), (0, 0, 1, 1))
    with pytest.raises(ValueError, match='P235:rect_overlap:bad_value:r$'):
        m.rect_overlap((3, 0, 2, 4), (0, 0, 1, 1))


def test_point_covered_boundaries():
    assert m.point_covered(OVER, -64, 0) is False              # x at -C_MAX passes
    assert m.point_covered(OVER, 64, 0) is False               # x at C_MAX passes
    assert m.point_covered(OVER, 0, -64) is False              # y at -C_MAX passes
    assert m.point_covered(OVER, 0, 64) is False               # y at C_MAX passes
    assert m.point_covered(((0, 0, 2, 2),), 0, 1) is True      # x on left edge covered
    assert m.point_covered(((0, 0, 2, 2),), 2, 1) is False     # x on right edge not covered
    assert m.point_covered(((0, 0, 2, 2),), 1, 0) is True      # y on bottom edge covered
    assert m.point_covered(((0, 0, 2, 2),), 1, 2) is False     # y on top edge not covered
    assert m.point_covered(((5, 0, 6, 4),), 4, 1) is False     # x left of rect, y inside
    with pytest.raises(ValueError, match='P235:point_covered:bad_value:x$'):
        m.point_covered(OVER, -65, 0)
    with pytest.raises(ValueError, match='P235:point_covered:bad_value:y$'):
        m.point_covered(OVER, 0, 65)
    with pytest.raises(ValueError, match='P235:point_covered:bad_type:x$'):
        m.point_covered(OVER, 'x', 'y')


def test_rect_pair_type_positions():
    for bad in ((0, 0.5, 1, 1), (0, 0, 1.5, 1), (0.5, 0, 1, 1), (0, 0, 1, 1.5)):
        with pytest.raises(ValueError, match='P235:rect_overlap:bad_type:r$'):
            m.rect_overlap(bad, (0, 0, 1, 1))
        with pytest.raises(ValueError, match='P235:rect_contained:bad_type:r$'):
            m.rect_contained(bad, (0, 0, 2, 2))
        with pytest.raises(ValueError, match='P235:rect_overlap:bad_type:s$'):
            m.rect_overlap((0, 0, 1, 1), bad)


def test_rect_contained_index_pins():
    assert m.rect_contained((1, 0, 2, 1), (2, 0, 4, 1)) is False  # s[0] > r[0]
    assert m.rect_contained((0, 2, 1, 6), (1, 0, 3, 7)) is False  # s[0] > r[0] but s[0] <= r[1]
    assert m.rect_contained((1, 0, 3, 1), (0, 2, 4, 3)) is False  # s[1] > r[1] but s[1] <= r[2]
