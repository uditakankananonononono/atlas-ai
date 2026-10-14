# Historical V2 local record, corrected by V3.md

# V2 local audit record

Original auditor-23 corpus scripts were received through Main. Hashes verified:
- mut7_original.py d274af0d32d34a2117d2ede2ba43733c1c9cc5b1dffc9ef33500c6ac93414404
- mutb_original.py 0bc8962d81b8d82016ca35944d5a14f7c7c77ba1d6ccd15d01604a55cad3699a

The optimizer core is unchanged from v1, so the unique AST mutation corpus stays
253 mutants, with 6 duplicate encodings skipped. Local Python 3.12.14, pytest
9.1.1, not the auditor's Python 3.10. Code execution did not use paid services.

Final shipped-test judge: 229 killed / 253 (90.5%), 24 survivors. Auditor's v1
result was 186/253 (73.5%), received not re-run. Full survivor names are in JSON.
Headline-totals judge: 177 killed / 253 (70.0%), 76 survivors, including 2 kills
by the original 60-second timeout rule. Auditor's v1 result was 176/253, received
not re-run. This judge only checks aggregate headline totals and is intentionally
weaker than the test judge for payload, input-validation and tie contracts.

Mut7 was split into eight disjoint shards AFTER global deduplication, so corpus
coverage is identical; each shard prints six duplicate encodings, which count
once globally, not 48. An initial incorrect sharding-before-dedup experiment
was discarded, not included in final totals. Some long shell runs were cut off;
mut7 incomplete shards were rerun, final logs each contain a complete result.
Mutb used resumable per-mutant output, retained completed judgments after shell
interruption, and ran only missing mutant IDs. No mutant IDs duplicated in the
final 253-entry progress log. Mutation generation and kill judges unchanged.

The V2 survivor explanations originally suggested redundant wrapper validation
and equivalent ties. Auditor re-audit found seven actual gaps, so those
explanations are withdrawn. Auditor's worst observed v2 count is 228/253,
25 survivors due to hash-dependent sorted-selection coverage. See V3.md for
the corrected record and ten-seed full sweep.

Test accounting: 46 candidate pytest cases locally PASS; separate 35 m20
regression cases locally PASS. These are NOT 81 candidate tests. Original v1
10 candidate cases were auditor-run; original local 45 combined cases were 10
candidate + 35 m20. Independent combinations oracle verifies all 5,964 optimal
utility values. V2 benchmark uses memoised recursive replay evaluation independent
of production replay, and tests use a separate recursive oracle too. Receipt
payload, sorted keys, validation raises, exactly-20/21 boundary, greedy ties,
frontier lexical ties and scalarization ties have explicit pins.

Reproduction: use the original scripts against a minimal root holding just the
module, research harness and candidate tests, not the whole Atlas tests tree.
Use the shipped-test judge as TESTS=tests. The original scripts copy their root
under /tmp/a; work in a writable temporary directory. Optimizer tests require
pytest, core/harness require Python standard library only. Full logs/receipts
are included; independent audit of this v2 remains outstanding.
