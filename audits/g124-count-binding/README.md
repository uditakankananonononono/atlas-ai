# G124 parsed dataset count integration

Bind_artifacts real call sites on base c95aba26: only
 tests/test_dataset_artifact_binding.py and tests/test_row124_validation_deepening.py.
No production call site discovered. Dataset registers remain declarations unless
bound through this integration. No all-program adoption claim.

Peer reader and its tests imported unchanged from parent attachments:
- dataset_count_reader_p254.py SHA256 f04e6efdf3f5efd502e9f7321940b5259794e6f9901e3b0c8a45aa8c837e875a
- test_dataset_count_reader_p254.py SHA256 1265a751e6b7c716d2d9bf23a1fe7ef4deec7a13e72fcb0d41638d05e7d1d6c8

New bind_artifacts format field is operator-named jsonl/csv/json. Old bindings
without format remain accepted structurally, but counts and provenance now
UNVERIFIED. No file suffix/byte equality implies a count. The unchanged bounded
reader counts parsed JSONL records, CSV data rows excluding header and JSON array
length. Unsupported, missing or malformed formats never produce VERIFIED.
Non-standard JSON NaN/Infinity refused by reader. Fixed byte cap 8,000,000.
JSON duplicate keys/huge integer and CSV ragged-width validation are not covered.

Entries expose counted_records, record_count_status and source_bytes_match
separately. VERIFIED requires nonempty source-byte equality AND COUNT_MATCH;
COUNT_MISMATCH/UNVERIFIED remains UNVERIFIED even for equal bytes. Local
COUNT_MATCH without source read is DECLARED-ONLY, not provenance VERIFIED.
Empty artifact/source matches remain excluded. Reference mappings and counts
never prove authorship, licensing, semantic record quality or source authenticity.
Reader callback must bound network byte allocation itself and enforce source
scope/authorization; no fetch occurs automatically here. Local file hashes still
appear in artifact reference inventory even when record count is UNVERIFIED.

The previously unchecked VERIFIED test paths (reader exact bytes and separate
local source exact bytes with declaration 999) were downgraded and pinned.
Old missing-format existence test is also downgraded. Tests pin real count
matches, source mismatch despite count match, equal bytes/wrong counts,
unsupported/missing formats, malformed JSON/JSONL, empty and oversize artifacts.

Reproduce on Python 3.12:
```
PYTHONPATH=backend python -m pytest --noconftest -q tests/test_dataset_count_binding_g124.py tests/test_dataset_artifact_binding.py tests/test_row124_validation_deepening.py tests/modules/test_dataset_count_reader_p254.py tests/modules/test_instinct_dataset_register_p254.py
```
Red 10 failures against existing bind_artifacts (new schema/count invariants).
Green local tests are builder evidence, independent audit pending. Full Atlas
suite/deployment/all-caller coverage not established. Reader is peer-authored,
not audited by this builder. This delta closes unchecked declared-count upgrade
paths on this API, not the requirement of 120 actual datasets per project.

1b cap repair: bind_artifacts checks local stat against the unchanged reader's
MAX_BYTES before opening and reads at most MAX_BYTES+1. A growing/raced file is
also refused on returned length; no unlimited read_bytes allocation. Sparse-file
regression replaces safe_file with a test-only passthrough to ensure this API's
own pre-read cap refuses opening, not only repo_evidence's existing size check.
