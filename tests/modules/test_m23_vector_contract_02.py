"""Integrator-executed helper contracts; route imports covered separately."""
import importlib.util
import math
from pathlib import Path
import sys

import pytest

_PATH = (Path(__file__).resolve().parents[2] / 'backend' / 'app' / 'modules' /
         'm23_study_abroad' / 'vector_contract.py')
_SPEC = importlib.util.spec_from_file_location('atlas_m23_vector_contract_02', _PATH)
vc = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = vc
_SPEC.loader.exec_module(vc)


def test_dimension_mismatch_never_truncates_in_either_order():
    for left, right in [([1, 2], [1]), ([1], [1, 2])]:
        with pytest.raises(vc.VectorContractError, match='dimension mismatch'):
            vc.validated_cosine(left, right)


@pytest.mark.parametrize('bad', [True, False, math.nan, math.inf, -math.inf,
                                  '1', None, [1], 10 ** 400])
def test_rejects_nonfinite_bool_coercion_and_overflow(bad):
    with pytest.raises(vc.VectorContractError):
        vc.validate_vector([bad])
    with pytest.raises(vc.VectorContractError):
        vc.validated_cosine([1], [bad])


@pytest.mark.parametrize('bad', [[], (), '12', {0: 1}, iter([1])])
def test_rejects_empty_or_nonsequence_vectors(bad):
    with pytest.raises(vc.VectorContractError):
        vc.validate_vector(bad)


@pytest.mark.parametrize('dimensions', [True, False, 0, -1, 1.0, '1'])
def test_dimensions_are_positive_integers_not_bool(dimensions):
    with pytest.raises(vc.VectorContractError):
        vc.validate_vector([1], dimensions=dimensions)
    with pytest.raises(vc.VectorContractError):
        vc.lexical_hash_vector('a', dimensions=dimensions)


def test_validation_copies_to_immutable_floats():
    original = [1, 2.5]
    result = vc.validate_vector(original, dimensions=2)
    original[0] = 9
    assert result == (1.0, 2.5)
    assert all(type(value) is float for value in result)


def test_cosine_identical_opposite_orthogonal_and_known_angle():
    assert vc.validated_cosine([1, 2], [1, 2]) == pytest.approx(1)
    assert vc.validated_cosine([1, 2], [-1, -2]) == pytest.approx(-1)
    assert vc.validated_cosine([1, 0], [0, 1]) == 0
    assert vc.validated_cosine([1, 0], [1, 1]) == pytest.approx(1 / math.sqrt(2))


def test_cosine_handles_extreme_finite_magnitudes():
    for magnitude in [1e308, 1e-308, 5e-324]:
        score = vc.validated_cosine([magnitude, magnitude], [magnitude, magnitude])
        assert math.isfinite(score) and -1 <= score <= 1
        assert score == pytest.approx(1)
    assert vc.validated_cosine([1e308, 0], [1e-308, 0]) == pytest.approx(1)


def test_zero_vectors_rejected_for_cosine_but_valid_for_storage():
    assert vc.validate_vector([0, -0.0]) == (0, 0)
    for left, right in [([0, 0], [1, 0]), ([1, 0], [0, 0]), ([0], [0])]:
        with pytest.raises(vc.VectorContractError, match='zero vector'):
            vc.validated_cosine(left, right)


def test_numeric_cosine_is_repeatable_and_symmetric():
    left, right = [3, -8, 2.5], [7, 1, -4]
    score = vc.validated_cosine(left, right)
    assert score == vc.validated_cosine(left, right)
    assert score == vc.validated_cosine(right, left)


def test_lexical_hash_fixed_sha256_fixture_and_distinct_token_policy():
    # SHA-256('a') ends in 0xbb, hence bucket 11 modulo 16.
    record = vc.lexical_hash_vector('A a a')
    assert record.values == tuple(1.0 if index == 11 else 0.0 for index in range(16))
    assert record.kind == 'lexical_hash' and record.model == vc.LEXICAL_MODEL
    assert record.dimensions == 16
    assert vc.lexical_hash_vector('one TWO one').values == vc.lexical_hash_vector('two one').values


def test_lexical_collisions_are_counts_not_semantic_claims():
    record = vc.lexical_hash_vector('a b c', dimensions=1)
    assert record.values == (1.0,)
    assert record.as_dict() == {'values': [1.0], 'kind': 'lexical_hash',
                                'model': vc.LEXICAL_MODEL, 'dimensions': 1}
    assert 'embedding' not in record.as_dict()


@pytest.mark.parametrize('text', ['', '   ', '!!!', '你好', None, 123])
def test_lexical_requires_string_with_supported_tokens(text):
    with pytest.raises(vc.VectorContractError):
        vc.lexical_hash_vector(text)


def test_semantic_wrapper_keeps_magnitudes_and_explicit_labels():
    record = vc.semantic_embedding([3, 4], model='external-model@revision/preprocess-v1', dimensions=2)
    assert record.values == (3, 4)
    assert record.kind == 'semantic_embedding'
    assert record.as_dict()['model'] == 'external-model@revision/preprocess-v1'


@pytest.mark.parametrize('model', ['', '   ', None, 42])
def test_semantic_rejects_missing_model_label(model):
    with pytest.raises(vc.VectorContractError):
        vc.semantic_embedding([1], model=model, dimensions=1)


def test_record_constructor_cannot_bypass_validation():
    for args in [((True,), 'semantic_embedding', 'm', 1),
                 ((1,), 'semantic_embedding', 'm', 2),
                 ((1,), 'unknown', 'm', 1),
                 ((1,), 'lexical_hash', 'made-up', 1)]:
        with pytest.raises(vc.VectorContractError):
            vc.VectorRecord(*args)


def test_labeled_cosine_rejects_cross_kind_model_and_dimension():
    lexical = vc.lexical_hash_vector('a', dimensions=1)
    semantic = vc.semantic_embedding([1], model=lexical.model, dimensions=1)
    other_model = vc.semantic_embedding([1], model='another-space', dimensions=1)
    other_dimension = vc.semantic_embedding([1, 0], model=semantic.model, dimensions=2)
    for left, right in [(lexical, semantic), (semantic, other_model),
                        (semantic, other_dimension), (semantic, [1])]:
        with pytest.raises(vc.VectorContractError):
            vc.labeled_cosine(left, right)


def test_labeled_cosine_accepts_matching_spaces_only():
    a = vc.semantic_embedding([1, 0], model='m@r/preprocess', dimensions=2)
    b = vc.semantic_embedding([1, 1], model='m@r/preprocess', dimensions=2)
    assert vc.labeled_cosine(a, b) == pytest.approx(1 / math.sqrt(2))
    lexical = vc.lexical_hash_vector('some tokens')
    assert vc.labeled_cosine(lexical, lexical) == pytest.approx(1)
