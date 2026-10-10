"""Standalone numeric and vector-space contracts. Additive numeric/lexical routes use these contracts.

Lexical hashes are not semantic embeddings. Semantic records wrap caller-supplied
values and provenance labels only; this module never loads or invokes a model.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Literal

VectorKind = Literal['lexical_hash', 'semantic_embedding']
LEXICAL_MODEL = 'sha256-ascii-token-set-v1'


class VectorContractError(ValueError):
    """Input does not meet the explicit local vector contract."""


def _dimension(value: int) -> int:
    if type(value) is not int or not 1<=value<=4096:
        raise VectorContractError('dimensions must be integer1..4096')
    return value


def validate_vector(values: list[int | float] | tuple[int | float, ...], *,
                    dimensions: int | None = None) -> tuple[float, ...]:
    """Copy a nonempty list/tuple of finite built-in int/float values.

    No string conversion, bool, nested values, numpy scalars or lazy iterables.
    Integers outside finite float range are rejected rather than overflowed.
    Zero vectors are valid data but have no cosine direction.
    """
    if dimensions is not None:
        _dimension(dimensions)
    if not isinstance(values, (list, tuple)) or not 1<=len(values)<=4096:
        raise VectorContractError('vector must be a nonempty list or tuple')
    if dimensions is not None and len(values) != dimensions:
        raise VectorContractError('vector dimension mismatch')
    result = []
    for value in values:
        if type(value) not in (int, float):
            raise VectorContractError('components must be int or float, not bool')
        try:
            component = float(value)
        except (OverflowError, ValueError) as exc:
            raise VectorContractError('component is outside finite float range') from exc
        if not math.isfinite(component):
            raise VectorContractError('components must be finite')
        result.append(component)
    return tuple(result)


def _unit(values: tuple[float, ...]) -> tuple[float, ...]:
    # Scale first: avoid squaring huge values or underflowing tiny vectors.
    scale = max(abs(value) for value in values)
    if scale == 0:
        raise VectorContractError('zero vector has no cosine direction')
    scaled = tuple(value / scale for value in values)
    norm = math.sqrt(math.fsum(value * value for value in scaled))
    return tuple(value / norm for value in scaled)


def validated_cosine(left: list[int | float] | tuple[int | float, ...],
                     right: list[int | float] | tuple[int | float, ...]) -> float:
    """Finite cosine in [-1, 1], rejecting mismatches before any pairing.

    Deterministic for the same inputs on the same Python/platform. Exact
    cross-platform bit equivalence is not promised. No zero-norm fallback.
    This numeric primitive makes no vector-space/provenance claim.
    """
    a = validate_vector(left)
    b = validate_vector(right, dimensions=len(a))
    a, b = _unit(a), _unit(b)
    score = math.fsum(a[index] * b[index] for index in range(len(a)))
    return max(-1.0, min(1.0, score))


@dataclass(frozen=True)
class VectorRecord:
    """Immutable values with explicit kind, model/space and dimensions.

    model identifies the entire space, including revision and preprocessing.
    A semantic label is caller-supplied, not independent model verification.
    """
    values: tuple[float, ...]
    kind: VectorKind
    model: str
    dimensions: int

    def __post_init__(self) -> None:
        _dimension(self.dimensions)
        if self.kind not in ('lexical_hash', 'semantic_embedding'):
            raise VectorContractError('unknown vector kind')
        if not isinstance(self.model, str) or not self.model.strip():
            raise VectorContractError('model/space label must be a nonblank string')
        if self.kind == 'lexical_hash' and self.model != LEXICAL_MODEL:
            raise VectorContractError('unsupported lexical hash model')
        object.__setattr__(self, 'values', validate_vector(
            self.values, dimensions=self.dimensions))

    def as_dict(self) -> dict:
        """Explicit JSON-ready labels; no legacy ambiguous embedding field."""
        return {'values': list(self.values), 'kind': self.kind,
                'model': self.model, 'dimensions': self.dimensions}


def lexical_hash_vector(text: str, *, dimensions: int = 16) -> VectorRecord:
    """Normalized distinct ASCII token counts in SHA-256 modulo buckets.

    Preserves the legacy lowercase ASCII token-set/hash arithmetic, with
    sorted traversal. Collisions are expected. Not multilingual semantics,
    identity understanding, model inference, training, or model adoption.
    """
    _dimension(dimensions)
    if not isinstance(text, str):
        raise VectorContractError('lexical input must be a string')
    tokens = sorted(set(re.findall(r"[a-z0-9']+", text.lower())))
    if not tokens:
        raise VectorContractError('lexical input has no supported ASCII tokens')
    counts = [0.0] * dimensions
    for token in tokens:
        index = int.from_bytes(hashlib.sha256(token.encode('utf-8')).digest(), 'big') % dimensions
        counts[index] += 1.0
    return VectorRecord(_unit(tuple(counts)), 'lexical_hash', LEXICAL_MODEL, dimensions)


def semantic_embedding(values: list[int | float] | tuple[int | float, ...], *,
                       model: str, dimensions: int) -> VectorRecord:
    """Validate and label an externally produced embedding; no inference.

    Values retain their supplied magnitudes. The caller must establish model
    provenance and include revision/preprocessing in its space label.
    """
    return VectorRecord(validate_vector(values, dimensions=dimensions),
                        'semantic_embedding', model, dimensions)


def labeled_cosine(left: VectorRecord, right: VectorRecord) -> float:
    """Require the same kind, space and dimension before numeric comparison."""
    if not isinstance(left, VectorRecord) or not isinstance(right, VectorRecord):
        raise VectorContractError('labeled cosine requires VectorRecord inputs')
    if (left.kind, left.model, left.dimensions) != (right.kind, right.model, right.dimensions):
        raise VectorContractError('incompatible vector spaces')
    return validated_cosine(left.values, right.values)
