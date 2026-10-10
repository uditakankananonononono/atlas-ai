# M23 vector contract 02: additive integration

Base: f37156c7fc7aec8cf7bec6ecbd0f8aa39ecb18fa.
No existing file is changed. No route, registration, persistence, migration,
ranking adapter or service binding is supplied. Existing unsafe behavior remains.
Helper and additive route tests executed; legacy adapters remain unchanged. See ../M23_CONTRACT_INTEGRATION_20261010.md.

## Explicit local interface

All exports below are in the new standalone vector_contract.py only. These are
proposed local interfaces, not assumed or adopted shared project APIs.

- validate_vector(values, *, dimensions=None) returns an immutable float tuple.
  Accept a nonempty list/tuple containing built-in int/float only; reject bool,
  strings, nonfinite, unrepresentable integers, nested components, generators,
  third-party scalars and an explicit dimension mismatch. Dimensions, when
  supplied, must be a positive built-in integer (not bool).
- validated_cosine(left, right) first validates both vectors and equal lengths.
  Reject zero direction. Scale each vector independently before normalization,
  use math.fsum, and clamp roundoff to [-1, 1]. Finite numeric result for valid
  nonzero inputs. Repeatability is within the same Python/platform, not a promise
  of cross-platform identical bits. This raw primitive checks numbers only.
- VectorRecord(values, kind, model, dimensions) is frozen and validates at
  construction. kind is lexical_hash or semantic_embedding; model is a nonblank
  exact space label. as_dict() exports values, kind, model, dimensions. No
  ambiguous legacy embedding field and no automatic wire deserializer.
- lexical_hash_vector(text, *, dimensions=16) returns a lexical_hash record with
  model sha256-ascii-token-set-v1. Lowercase ASCII regex [a-z0-9']+, unique tokens,
  sorted traversal, SHA-256 integer modulo dimensions, collision counts and L2
  normalization. Reject no-token input. It is not a semantic model, multilingual
  understanding, training, or identity inference. Token-set behavior matches the
  existing algorithm's intent. Empty/non-ASCII-only acceptance is narrowed.
- semantic_embedding(values, *, model, dimensions) wraps external values as
  semantic_embedding without normalization or inference. Caller supplies the
  entire model/revision/preprocessing space label and must establish provenance.
  A label does not independently prove a model ran.
- labeled_cosine(left, right) requires VectorRecord inputs with matching kind,
  exact model label and dimensions; then calls the numeric primitive. Matching
  numeric lengths alone never authorize semantic/lexical comparisons.
- Invalid input raises VectorContractError (a ValueError). Zero vectors may be
  stored or wrapped but cannot be used for cosine.

## Decisions for the integrator

1. Choose route input/output adapter and whether to persist kind/model/space
   metadata. Existing row 52 query/items/embedding shape has no such metadata;
   no automatic inference of a semantic label is safe.
2. Choose semantic provider, revision, preprocessing and provenance checks.
   None is selected, downloaded, trained or adopted by this unit.
3. Decide error response mapping, zero-vector policy and compatibility migration.
   This helper rejects zero cosine and mismatch instead of returning zero or
   silently truncating. Existing callers may depend on the old behavior.
4. Decide ranking/tie policy and bounds on text length/dimension/resource usage
   at the service boundary. This helper does not rank or enforce a service quota.
5. Independently run authored tests and regression/canaries. The test file loads
   the helper directly to avoid app package import wiring; normal package/route
   import and integration remain explicitly unverified.

No live HTTP, services, PostgreSQL, test execution, main writes or remote pushes
are part of this preparation. The peer owns integration and independent verdict.

## Integration status superseding historical preparation text
Numeric/lexical endpoints are now bound and tested. Dimensions/vector length cap
4096. Zero cosine rejects with422. No ranking/tie policy or semantic provider;
legacy row52 unchanged rather than inventing metadata for old inputs.
