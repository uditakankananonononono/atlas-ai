"""Authored-not-run pure helper tests. No app import during helper load."""
import importlib.util
import math
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m02_competition_manager/embedding_batch_validation_01.py'
SPEC = importlib.util.spec_from_file_location('m02_embedding_batch_validation_01', PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def test_exact_batch_returns_fresh_vectors():
    original = [[1, 2], [3, 4]]
    result = helper.validate_embedding_batch(original, 2)
    assert result == [[1.0, 2.0], [3.0, 4.0]] and result is not original
    result[0][0] = 99
    assert original[0][0] == 1


@pytest.mark.parametrize('batch', [[], [[1]], [[1], [2], [3]]])
def test_short_long_or_empty_batch_rejected(batch):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch(batch, 2)


@pytest.mark.parametrize('batch', [None, {}, 'bad', [None], [[]], [[1], [2, 3]]])
def test_malformed_empty_and_ragged_vectors_rejected(batch):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch(batch, 1 if batch != [[1], [2, 3]] else 2)


@pytest.mark.parametrize('value', [True, False, '1', None, {}, [], float('nan'),
                                  float('inf'), float('-inf'), 10 ** 400])
def test_invalid_coordinates_rejected(value):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch([[value]], 1)


def test_no_global_dimension_and_query_compatibility():
    assert helper.validate_embedding_batch([[1, 2, 3]], 1) == [[1, 2, 3]]
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch([[1, 2]], 1, expected_dimension=3)


@pytest.mark.parametrize('sources', [[], (), None, {}, 'source'])
def test_empty_or_invalid_sources_rejected(sources):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.require_sources(sources)


def test_sources_count_and_empty_stored_rows():
    assert helper.require_sources([object(), object()]) == 2
    assert helper.validate_embedding_batch([], 0, 2) == []


@pytest.mark.parametrize('count', [-1, True, 1.5, None])
def test_invalid_expected_counts(count):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch([], count)


@pytest.mark.parametrize('dimension', [0, -1, True, 1.5])
def test_invalid_expected_dimensions(dimension):
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validate_embedding_batch([[1]], 1, dimension)


def test_cosine_uses_equal_shape_and_zero_norm_policy():
    assert helper.validated_cosine([1, 0], [0, 1]) == 0
    assert helper.validated_cosine([0, 0], [1, 0]) == 0
    assert helper.validated_cosine([1, 0], [-1, 0]) == -1
    with pytest.raises(helper.EmbeddingBatchValidationError):
        helper.validated_cosine([1], [1, 2])


def test_finite_large_and_small_values_do_not_overflow_norms():
    for value in (1e308, 1e-308):
        score = helper.validated_cosine([value, value], [value, value])
        assert math.isfinite(score) and score == pytest.approx(1)
