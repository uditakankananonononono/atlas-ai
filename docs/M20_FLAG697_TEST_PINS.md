# FLAG697 independent test-only boundary pins

New test file only, plus this note. Runtime file is frozen at blob
b5c9f31455fe7ccf287f97576532bd32079d3415. True original base:
7885256e9791f9eab4239ecab1b8fb7fd4c8787c. Original full tip:
3c2100cf5b6d0ecdb505b615e74861b4ae197371. New commit stacks directly on
that tip, not on live main. No source rebase/thinning/amend or runtime change.
The first two pins explicitly assume the documented supplied-rule contract:

1. Percent boundary uses `score < percent * 100`, not `<=`. With seed `s`
   and key `key-1`, the independent SHA256 oracle is exactly 7100. 71 percent
   excludes that key; 72 includes it. This is deterministic bucket partitioning,
   not a promise of exact population percentages or deployment authority.
2. Hash serialization uses compact JSON `[seed,user_key]`, `ensure_ascii=False`,
   UTF-8 encoding. This applies to a non-ASCII seed as well as the user key.
   Seed `é`, key `key-88` hashes to 1800; escaping Unicode would yield 8066.
   The test separates them at 19 percent and separately checks exact 18 percent.

Other pins cover exact ID/string/int/number bounds and types, both surrogate
endpoints and adjacent legal values, condition node/op shape, child array type
and arity, nested error path/index, all-child depth eight, seed/rule-source 128,
64-field schema and error classification when context type is invalid. Tests
load the exact pure module by path. They do not wire dispatcher, auth, tenant,
rollout, deployment, persistence or network. No science/discovery claim.

All new tests were actually run before commit. No historical RED was retained,
because tests are added to a correctly executing frozen runtime and no baseline
assertion failure was seen. Mutation RED logs are actual
copy-only runs, not reconstructed build logs. Counts and environment are in the
separate evidence package. Mutation counts reported earlier are not credited.

The independent token campaign distinguishes assertion kills, runtime/collection
errors, timeout, noncompile and survivors. An empty-ID lower-bound `1 -> 0`
mutation survives: for exact built-in strings, `not value.strip()` already
rejects empty string. This is an equivalent guard-redundancy survivor, not a
hidden test kill. Schema-error classification survivors were exposed by adding
a real invalid-context / legal-schema test and rerunning; original result passes.

Scope: this change adds only the two new files
`tests/modules/test_m20_flag697_boundary_pins.py` and this note. Existing core,
original tests and contract remain unmodified. These test pins make no
integration or release claim.
