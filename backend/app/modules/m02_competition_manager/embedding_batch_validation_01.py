"""Pure embedding validation, no provider, database or application imports.

No global dimension or model identity policy. Dimensions are established by
this batch or an explicit expected dimension. Wiring is an unapplied proposal.
"""
import math
from numbers import Real


class EmbeddingBatchValidationError(ValueError):
    """Invalid source/batch/vector shape or numerical content."""


def require_sources(sources):
    if not isinstance(sources, (list, tuple)) or not sources:
        raise EmbeddingBatchValidationError("sources must be a non-empty list or tuple")
    return len(sources)


def validate_embedding_batch(vectors, expected_count, expected_dimension=None):
    """Return fresh float vectors; reject entire malformed batch before use.

    Numeric inputs must be finite Real values (int/float supported), never
    bool. Values must be representable as finite floats for cosine arithmetic.
    Empty batch is permitted only for expected_count=0 (e.g. empty stored rows).
    """
    if type(expected_count) is not int or expected_count < 0:
        raise EmbeddingBatchValidationError("expected count must be a nonnegative integer")
    if expected_dimension is not None and (
            type(expected_dimension) is not int or expected_dimension < 1):
        raise EmbeddingBatchValidationError("expected dimension must be a positive integer")
    if not isinstance(vectors, (list, tuple)) or len(vectors) != expected_count:
        raise EmbeddingBatchValidationError("embedding batch must contain exactly one vector per input")
    dimension, validated = expected_dimension, []
    for vector in vectors:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise EmbeddingBatchValidationError("each embedding must be a non-empty list or tuple")
        if dimension is None:
            dimension = len(vector)
        if len(vector) != dimension:
            raise EmbeddingBatchValidationError("embedding dimensions must match within batch and query")
        values = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise EmbeddingBatchValidationError("embedding coordinates must be finite numeric non-bool values")
            try:
                converted = float(value)
            except (OverflowError, ValueError) as exc:
                raise EmbeddingBatchValidationError("embedding coordinate is not a finite float") from exc
            if not math.isfinite(converted):
                raise EmbeddingBatchValidationError("embedding coordinates must be finite")
            values.append(converted)
        validated.append(values)
    return validated


def validated_cosine(left, right):
    """Equal finite shape only; scale first to avoid overflow in norms/dot.

    Zero-norm vectors retain the existing score-zero policy.
    """
    a, b = validate_embedding_batch([left, right], 2)
    scale_a, scale_b = max(map(abs, a)), max(map(abs, b))
    if not scale_a or not scale_b:
        return 0.0
    a = [value / scale_a for value in a]
    b = [value / scale_b for value in b]
    norm = math.sqrt(math.fsum(value * value for value in a)) * math.sqrt(
        math.fsum(value * value for value in b))
    score = math.fsum(x * y for x, y in zip(a, b)) / norm
    return max(-1.0, min(1.0, score))
