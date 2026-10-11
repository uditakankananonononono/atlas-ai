# M20-STRANGLER695-ROUTE-01: Strangler Fig Pattern, finite route dispatch

Candidate target: row695 "Strangler Fig Pattern" (audits/additional-2000-features.json, description
"Gradually replaces"; title and description verified against the source Google Doc
1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY on 2026-10-11). Existing owner at base
7885256e: `software_practice_685_709.py::_strangler`, which only set-diffs declared route names. It does
no method/path dispatch, no precedence, no fixture comparison, no rollback. That is the gap. This unit is a
bounded SCOPED capability, not full title closure. Ledgers, STATUS and wiring are untouched (integrator owns).

## What it is
`strangler_router695.evaluate(data)` is a pure, finite evaluator. Handlers are labels. Old/new
"handlers" are supplied recorded fixture outputs `{status, body}`. It does not route network
traffic, read production traffic, or run any handler or code. Result flags `handler_executed`,
`network_routing_performed`, `production_traffic_verified` are always false.

## Input (unknown keys refused at every level; malformed input raises ValueError, 422 once mounted)
- `targets`: exactly `legacy` and `replacement`, each `{handler: id}`.
- `rules` 1..64: `{id, method ('*' or uppercase GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS), match (exact|prefix), path, target}`.
- `requests` 1..64: `{id, method, path}` (already normalized).
- `fixtures` 0..64 (optional): `{id, request_id, legacy:{status,body}, replacement:{status,body}, golden?:{parity, mismatched_fields}}`.
- `default_target` (optional, legacy|replacement).
- ids: `[A-Za-z0-9_.:-]{1,64}`. status: integer 100..599, not boolean. body: JSON data, depth <= 8,
  <= 256 nodes, strings <= 4096, object keys <= 64 chars, finite numbers, ints <= 256 bits.

## Path normalization: refuse, never repair
Paths must start with `/`, be ASCII, 1..256 chars, <= 16 segments, with no empty or `.`/`..` segment, no trailing
slash (except root), no `? # \`, space or control characters, and percent-escapes only as uppercase `%XX`
that do not encode an unreserved character, `/ \ % ? # .`, or a control octet. Anything else is refused:
a request becomes `decision: refused` with reason codes and is never routed; a rule path raises ValueError.
Methods are not case-folded: non-uppercase or unknown methods are refused.

## Precedence
Specificity key (higher wins): exact over prefix; among prefixes more segments; then method-specific
over `*`. Prefix matching is on segment boundaries (`/api` matches `/api` and `/api/x`, not `/apix`;
`/` matches everything). Duplicate rule ids and duplicate (match, method, path) selectors are refused.
Overlapping rules with different targets where neither wins on both path and method specificity
(e.g. `GET /a` prefix vs `* /a/b` prefix) are refused as `ambiguous_precedence`. Overlaps are reported
(`exact_vs_prefix`, `prefix_vs_prefix`, `method_specific_vs_wildcard`). No match uses `default_target`
if declared, else `no_route`. Output is sorted by id; permuting input lists changes nothing. Each routed
request carries a trace of every matching rule in precedence order with `selected`.

## Parity and rollback
Per fixture: parity, `mismatched_fields` (subset of `body`, `status`, sorted), `effective_target` from
routing, and `served_output`. Comparison is structural and type-strict (`1` != `True` != `1.0`;
object key order ignored). A supplied `golden` must be self-consistent and is checked against the
computed result (`golden_ok`, `golden_violations`). `rollback_candidates` are rules (or `@default`) whose
replacement-served requests have a mismatch or golden violation. `rollback_effect` and
`after_rollback_routes` re-run dispatch with those rules forced to legacy and list requests whose effective
target changed; other rules are unaffected. `unverified_replacement_rules` lists replacement-serving
rules with any routed request lacking a fixture. `legacy_removal_safe` is always false:
matching fixtures never imply safe removal; `legacy_removal_blockers` states why.

## Residual limits
Only status and body are compared (no headers, latency, side effects, ordering, concurrency). Fixtures
are caller-supplied and unauthenticated; their representativeness is not checked. No query strings,
host/scheme, regex/glob rules, weights, canary percentages or sticky sessions. Candidate selection is a
diagnostic, not a rollback executor. Not a production migration or traffic verifier. Does not close other
rows or the full "Strangler Fig Pattern" title.

## Wiring (separate, unapplied patch; integrator owns)
Route `POST /api/v1/api/modules/20/strangler-route695/evaluate` via `strangler_routes695.py`, included
from `routes.py`; the patch adds a mounted auth test (401 unauthenticated, 200 exact body equality,
422 malformed).
