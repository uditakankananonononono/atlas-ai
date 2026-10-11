# FLAG697: finite supplied-rule Feature Toggle evaluator

Candidate scoped replacement, not a rollout service. Ledger
`audits/additional-2000-features.json` row697 names "Feature Toggle" and
"Controls deployment". Live original Google Doc
`1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY`, read via the connected
uditakankana@gmail.com account, contains the exact entry
"Feature Toggle - Controls deployment" between Branch by Abstraction and
Trunk-Based Development. Its export does not expose a document title or row
number; ledger697 is pinned by exact entry text, not inferred document numbering.
Existing main 7885256e reports PARTIAL and provides
supplied-input diagnostics only. This package computes flag values from supplied
rules; it does not control any deployment, verify caller facts, persist state,
contact a service, infer protected traits or authorize a release.

## API and bounds

`evaluate_flags697(data)` takes exactly `context_schema`, `evaluation_context`
and `flags`. Schema maps at most64 field IDs to bool/int/number/string. Missing
context fields are allowed; unknown fields refuse. bool is never numeric; int
is exact Python int with absolute value <=2**53-1; number is finite int/float
in that magnitude range; strings have <=256 Unicode code points and no
surrogate code points. No coercion/null/containers. Numbers have Python finite
comparison semantics, not arbitrary precision decimal semantics.

There are0..32 flags, each with unique nonblank `name` (<=64 code points),
`source_id` (<=128), Boolean `default`, and0..32 rules. Optional Boolean `safe`
is echoed only as `caller_diagnostic_safe`, never accepted as proof. Rules have
unique per-flag `id`, source_id, distinct integer priority0..1000000, Boolean
value and condition. Unknown keys refuse. IDs may be supplied private labels;
source IDs are caller references, not independently authenticated sources.

Conditions: eq/ne over declared typed scalars; lt/le/gt/ge over int/number only;
all/any over1..127 child conditions; not over one child; bucket over a declared
string field with nonblank seed<=128 and integer percent0..100. Each condition
has at most128 AST nodes and depth8 (root depth1), including nested Boolean
nodes. Validation covers all rules even after a matching priority.

Missing leaves evaluate to unknown (`matched: null`), not false. not unknown
is unknown. all is false if any false, else unknown if any unknown; any is true
if any true, else unknown if any unknown. Trace includes sorted missing fields
even when another operand decides a Boolean expression. First true rule in
ascending priority wins, including a false-valued rule. Unknown/unmatched rules
fall back to explicit default. Flags are sorted by name, traces by priority;
rule/flag input order cannot change output. Input is not mutated.

Bucket uses UTF-8 of canonical compact JSON `[seed,user_key]` with
`ensure_ascii=False`; SHA256 first8 bytes interpreted big-endian, modulo10000.
Match if bucket<percent*100.0% always false,100% always true. Modulo hashing
is deterministic partitioning with slight modulo bias, not a promise of exact
population percentages, randomized trials or a demographic targeting service.
There is no trait inference; caller must supply an opaque string key. No
persistence, network, independent user identity or experiment statistics.

Errors are ValueError with stable FLAG697_ codes and local path/ID context:
SCHEMA, BOUND, ID, TYPE, FIELD, OPERATOR, OPERATOR_TYPE, BUCKET, PRIORITY,
DUPLICATE_FLAG, DUPLICATE_RULE, DUPLICATE_PRIORITY. Whole request refuses before
returning partial decisions. Error context is not a telemetry redaction layer.

## Integration and remaining gates

Only new core/test/contract files are committed. Separate row697-only dispatcher
patch is unapplied. Existing diagnostic outputs remain unchanged until the
integrator adopts the patch. Adoption must retain honest diagnostic labeling
for legacy payloads and must not certify deployments. Current route lacks a
local tenant dependency; parent router authentication and payload tenant binding
must be tested after wiring. No mounted auth/tenant execution is claimed here.

Tests use stdlib unittest/source loading on pre-existing Python3.10.12, not the
project's required3.12 toolchain.19 cases include exhaustive small comparator
and Boolean truth tables, defaults, missing fields, duplicate priority, typed
refusals, all exact documented bounds and hash oracle.9 independent one-change
mutants are killed. Base25-method stdlib floor verifies untouched existing
source and output/missing-field behavior, not the original mounted pytest suite.
Missing pytest/fastapi prevent that original suite without a scoped install;
no install was performed. Full3.12/mounted/independent integration acceptance
remain deferred to the peer integrator. Scoped title acceptance is not closure
of the broad Feature Toggle capability.
