# Instinct-doc group 2: dataset artifact evidence (contract)

Source request (instinct doc, group 2): "120+ real datasets per project."

## What the landed p254 register does and does not do

`dataset_register_p254.py` validates and renders caller-SUPPLIED dataset
declarations. It never counts anything in the world. Group 2's missing
scope is program-wide evidence over the real repos; this bundle closes it
the honest way.

## What this instrument measures

`dataset_evidence_g2.py` walks repository trees read-only and counts
dataset ARTIFACTS: files with recognized data extensions (.csv .tsv .json
.jsonl .ndjson .parquet .xml .yaml .yml .db .sqlite .sqlite3 .arrow
.feather .h5 .hdf5 .txt) under dataset-named directories (data/, datasets/,
dataset/, case-insensitive), per project repo, against the 120 gate.
Refuses: missing roots, oversize trees (200k walked files), more than 64
repos, non-integer/positive targets. Symlinks escaping the repo are not
evidence; in-repo symlinks/aliases are deduped by realpath so one physical
file counts once. Presence includes tests/data fixtures and config .json
files under data directories - they count toward the floor, which is why
verdicts are labeled EVIDENCE, not "real datasets confirmed". verify() re-runs the deterministic scan and compares every
reported field; that is internal consistency, not proof the artifacts are
genuine, loadable datasets (stated limit).

## Honest scope

Artifact presence is not dataset quality, record counts, licensing, or
proof a dataset is loaded or used. A repo can pass with junk and fail with
datasets in LFS/object storage/databases. Verdicts are an evidence floor,
labeled EVIDENCE_AT_TARGET / EVIDENCE_BELOW_TARGET - never "120 real
datasets confirmed".

## Executed evidence (this build, 2026-10-13)

- atlas-ai: 14 artifacts (.json 2, .jsonl 12) -> EVIDENCE_BELOW_TARGET
- sugarcode-ai: 41 artifacts (.csv 5, .json 25, .tsv 6, .txt 5) ->
  EVIDENCE_BELOW_TARGET
- verify() receipts: verified=true for both.

## Verification

21 hermetic stdlib-unittest tests: scan behavior, extension/dir filtering,
symlink-escape exclusion, cap and refusal behavior, multi-repo ledger,
and tamper rejection (count, verdict, extra key, measure label), plus
auditor-8 round pins: realpath dedupe, tests/data presence, docstring
wording.
