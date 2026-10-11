# FLAG697: finite supplied-rule Feature Toggle evaluator

Candidate scoped replacement, not a rollout service.
The additional-features ledger row697 names "Feature Toggle" and
"Controls deployment". Source entry pin:
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
adoption of the patch occurs. Adoption must retain honest diagnostic labeling
for legacy payloads and must not certify deployments. Current route lacks a
local tenant dependency; parent router authentication and payload tenant binding
must be tested after wiring. No mounted auth/tenant execution is claimed here.

HISTORICAL doc-only review: the recorded test approach uses stdlib unittest/source loading, with comparator
and Boolean truth tables, defaults, missing fields, duplicate priority, typed
refusals, documented bounds and a hash oracle. Test counts, mutation counts and
the audited toolchain version are unverified in this doc-only review: no correct
independent receipt was available. No numeric audit summary or audit-closure
claim is credited here. The original mounted suite, full-toolchain and independent
integration acceptance remain unverified in this review. No install or runtime
execution was performed for this doc-only change. Scoped title acceptance is
not closure of the broad Feature Toggle capability.

## Permanent historical RED disclosure

No genuine pre-implementation failing-test (RED) receipt was recovered.
This is a permanent historical evidence gap and must survive future edits
of this contract. Later passing tests or mutation failures do not backfill
that missing receipt. This disclosure makes no audit-closure or row-status claim.

## Explicit repair revision

This revision removes the account-bearing source phrase and the live-read
wording from the earlier contract, and removes the internal document identifier.
The neutral entry title and ledger reference remain. It separately adds the
permanent historical missing-RED disclosure; this is not a count-removal-only
revision. No correct independent audit receipt was available. The previously
offered receipt identified an unrelated export-adapter change, not this unit;
that wrong-receipt limitation remains. No earlier audit counts are borrowed.
The earlier pins note is excluded from this delivery because its internal
coordination wording and unverified audit claims have not been sanitized.

Core validation repair: dictionary counts are checked before key iteration/set
construction; keys must be exact builtin strings. Evaluation context is capped
at the schema field ceiling before iteration. Identifier and scalar-string raw
length caps precede scanning/strip; Cc/Cf/Zl/Zp are refused, Zs allowed, surrogate
refusal unchanged. Operator/kind raw lengths are capped before enum membership.
Integers use bit_length before abs. Existing numerical and rule semantics remain
supplied-only. General record shapes retain SCHEMA. Condition nodes with more than four keys
deliberately change from OLD_SCHEMA to NEW_BOUND: the count-first condition
gate refuses BOUND before shape/key/op validation. Four-key bucket nodes are
accepted; a fifth key refuses FLAG697_BOUND at the condition path. This change
is explicit, not a claim that every historical SCHEMA class is preserved.
No deployment authority or closure claim; full suite remains unverified.

Lookup-bound repair: unknown condition and context field strings are capped at
64 before schema membership; exact builtin type is checked before length.
Repair tests now load the runtime from the repository root using the same
mechanics as the existing source-loaded tests, not adjacent-file assumptions.
This changes the test file hash. Evidence output is neutralized to omit local
path prefixes; no earlier audit receipt or original RED is reconstructed.

## Repair evidence chronology (historical states kept distinct)

The first saved core-repair RED ran the original fetched runtime with the initial
repair test file: eight tests, five FAIL and one ERROR, two passing. After that
core repair, the saved lookup-cap RED ran the preceding repaired runtime before
lookup caps: nine tests, one ERROR in the AST length-order pin, eight passing.
It was not the original runtime state. An external replay reports seven failed
and two passed against a different original/runtime-test pairing; that replay
does not replace these saved receipts. Exact saved historical files are retained,
not rerun and relabeled as old evidence. The genuine original pre-implementation
RED remains permanently missing.

This test-only revision adds exact condition count, container, key, schema ID,
kind, numeric, float-bound and priority pins. Unchanged repaired runtime passes
the new tests. Fresh copy-only mutation failures are labeled mutation RED, never
claimed as a pre-runtime implementation RED. Previously reported external audit
counts and equivalent dispositions are not credited as local execution evidence.
Full suite and independent closure remain unverified.
