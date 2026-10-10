# M02 embedding batch validation - PREP ONLY

Base efa5649f7cbee5800e1cb38d0d38fbd3e5c55eca. Historical base beaf700275a24829440a5e96c3919ed572061503.
Additive helper only. Existing product paths are unchanged. Separate
UNAPPLIED patch proposes integration into profile_corpus.py and the three
profile_routes.py indexing/retrieval endpoints. Not a completed repair.

## Interface

- require_sources(sources): nonempty list/tuple, returns count; empty rejects.
- validate_embedding_batch(vectors, expected_count, expected_dimension=None):
  exact count, each nonempty list/tuple, same dimensions, optional explicit
  dimension. Coordinates finite Real numbers, never bool, convertible to
  finite floats. Returns copied float vectors. Empty only with expected_count
  zero (valid stored-empty-corpus boundary), never empty source/query batches.
- validated_cosine(a,b): validates equal finite shape, scales before arithmetic
  to avoid finite-value norm overflow. Zero norm scores zero as before.
- EmbeddingBatchValidationError extends ValueError. Errors contain no inputs.

No global dimension constant, model ID, provider changes or migration. Shape
is inferred from this batch or established query, not a global model policy.
JSON int/float coordinates are supported; strings, complex, Decimal and bool
are refused by the Real contract. No source item schema changes are proposed.

## UNAPPLIED product proposal

Ingest: reject empty sources before provider call. Validate whole embedding
batch before self.sessions.begin(). Exact one-to-one pairs give indexed count
from validated vectors. Existing create/update and tenant/provenance predicates
unchanged. Query: exactly one validated vector before read-session entry;
validate every tenant-filtered stored row against query dimension before any
ranking. Invalid stored row refuses the result rather than silently omitting it.
Profile routes map only the new validation error to HTTP 422, matching the
onboarding route's ValueError-to-422 style, preserving Google client finally.
Other application endpoints using ProfileCorpus are not changed by this patch.

Important existing limitation: ProfileCorpus.__init__ still calls global
Base.metadata.create_all(engine). No-transaction-on-rejection here covers the
method's corpus transaction; it does NOT claim no database effect when a route
constructs the existing service. Constructor lifecycle is outside this unit.
Stored dimension mismatch requires a read session to inspect existing rows.
No model identity drift or existing-row migration is fixed or claimed.

## Acceptance tests, authored NOT RUN

Pure helper tests run against path-loaded standalone helper. Integration
proposal tests explicitly fail if peer wiring is absent; no silent skips.
They cover invalid ingest/query without transaction/session entry, empty
sources without provider call, stored dimension mismatch, empty corpus,
accurate create/update counts and tenant/provenance retention. Constructor
bypass is explicit for method-level guard tests. SQLite fixture only runs on
the peer side; no DB/test/runtime execution occurred during preparation.

## Suggested peer procedure, NOT EXECUTED

1. Inspect additive patch and unapplied product patch for exact base and scope.
2. Apply additive patch on a peer-owned branch based on the selected SHA.
3. git apply --check ATLAS-M02-EMBEDDING-BATCH-VALIDATION-01-UNAPPLIED.patch
4. Decide and apply product wiring, keeping existing API error conventions.
5. With backend import path configured, run pure helper and integration proposal
   tests, then existing test_m02_profile_corpus.py and peer-selected regression.
6. Inspect HTTP 422/client close behavior for Docs, Sheets and retrieve;
   report independent verdict. No runtime or API result is verified here.

## Fix-pass source bounds and residual error consequence

The unapplied product patch remains limited to profile_corpus.py and
profile_routes.py. routes.py:155-169 evidence_completeness calls
score_from_corpus(ProfileCorpus(...), fields) without a validation-error catch.
If that consumer invokes retrieve with an invalid embedding batch or mismatched
stored vector, the new validation error still propagates as HTTP 500 there.
This is deliberately disclosed, not fixed by silently widening API scope.
The coordinator may separately authorize a matching 422 boundary for that
consumer. Other application endpoints can likewise surface uncaught errors.

New authored tests cover TestClient 422 for Docs, Sheets and retrieve; exact
Google client closure on validation failures and on grounding failures; exact
retrieval score/order (including a non-leading best row); and a distinct
RankingStarted sentinel that must not be reached for stored mismatch. These
are authored NOT RUN and do not claim any mutant result on the new head.

## Historical peer audit attribution, not builder results

Coordinator relay identifies OLD HEAD 6c1018b4fc6fa113be4479eeb2df16e719d69494
at base beaf700275a24829440a5e96c3919ed572061503:
- 39 PASS + 14 expected wiring-absent FAIL on the additive package.
- 105 PASS with the separate product proposal applied.
- Peer observed proposal applies clean; base NaN indexing returned HTTP 200
  indexed 1, patched returned 422; onboarding 422 precedent and generic error
  behavior, method-level invalid input without transaction begin.
- Peer reported 8 mutant classes killed, but a zero-cosine mutant survived.
These are peer-observed old-head results relayed by the coordinator, not
builder executions, not independently reproduced, and not PASS for this fix
or rebased head. All builder tests remain NOT RUN. New head awaits peer re-audit.
