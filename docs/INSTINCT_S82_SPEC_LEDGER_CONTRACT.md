# S8.2 spec-to-ledger mapper contract

Source line, verbatim: "keep an eye out for top secret projects, governement stuff too, super elite stuff"

Source pin: two owner messages (WhatsApp, 2026-10-11 IST), referenced by digest only because the repository is public and the text is private.
- 15:01:13 IST message, 8,525 chars, sha256 e364bf663808e5637762ea6f2c6d80f348d9718c94573b5f6a2a85a0bea7a6b1
- 15:03:34 IST message, 10,459 chars, sha256 5b41901ebe3070b5129f6031249f8d116488fc3cb3869ac8483c37cdf2e95bc5
- v2.1.1 mega-spec (registry seed), sha256 9079f7c8e30779d329b4b158e2163910f534f9146c0a342c8de2a4d3c4a0f792
- owner-map data used for the green real run, sha256 f913ac1f465e8b3ba1b9fbc3501991b361ff7d9b68eaaebf42b415a7f9abf159
`source_digest` in the public report is a sha256 over the canonical supplied sources. The full private text is not committed.

Module: `backend/app/modules/instinct_doc/spec_ledger_s82.py`. Tests: `tests/modules/test_instinct_spec_ledger_s82.py`. No routes, no wiring, no network, stdlib only. The routes named in the brief (`/api/v1/c30/ledger/run`, `/report`) are not created.

## Fixtures and privacy
- Committed fixtures under `tests/fixtures/s82/` are SYNTHETIC (invented spec, two invented source messages, invented reviewed maps). They exercise the same parser and mapping paths (whitespace runs, bullets, chat-line prefixes, ellipsis fragments, short quotes, case drift, empty quote, ADD- and V2- headings, gate and parked records, an ignored section).
- The real files live in the git-ignored `tests/fixtures/s82_private/` (`source-msg-150113.txt`, `source-msg-150334.txt`, `spec-v2.1.1.md`, `v21-owner-maps.json`). `PrivateRealInput` tests run only when all four exist and pin their sha256 above; otherwise they SKIP.
- Lineage: this branch is exactly clean commits on top of base fc366e2b and contains only synthetic fixtures. A separate, rejected local chain (starting e2b769d7) held the private files; it is not part of this history, its objects are not in this branch, and it must stay local and unpushed (do not push it).

## API
- `split_spans(text)`: lossless partition of a message into sentence/bullet spans.
- `parse_spec(text)`: registry from the spec (units under "## 2." and "## V2-1"/"## ADD-1", X rows under "## 1." and "## V2-2"/"## ADD-2", gate/parked under "## V2-0"/"## ADD-0"; the trailing space keeps ADD-10 out).
- `map_ledger(sources, registry, explicit_maps=None, exclusions=None)`: rows `{source_msg, line_no, verbatim, unit_ids, status}` plus a public report without source text.
- `require_complete(ledger)`: raises `PLAN_REFUSED_UNMAPPED_LINE:<n>`, then `PLAN_REFUSED_DRIFT:<n>`.
Refusals use the `PLAN_REFUSED_` prefix (source, registry, map, spec-line, UNMAPPED_LINE, DRIFT), are single-line and never echo source text. Cc/Zl/Zp characters are rejected in interpolated fields.

## Gate
passed iff UNMAPPED == 0 and no excerpt drift. Every unit excerpt (split on "...") must be a whitespace-normalised, case-sensitive substring of a supplied source. Dropping a unit un-maps its lines and flips the gate (tested on the synthetic and, locally, the private input).

## Status enum and B1 reconciliation
S8.2 states are B1's six (IMPLEMENTED, PARKED_BY_USER, STOPPED_BY_USER, SUPERSEDED, REFUSED_WITH_SUBSTITUTE, UNMAPPED) plus PLANNED. Decision: S8.2 keeps its OWN ledger vocabulary and does not import B1. Reasons: B1 is a chat-claim ledger with owner-channel evidence rules; S8.2 maps spec text to units from a supplied spec, so its rows must not pretend to be owner-channel rows; importing B1's package fails on Python 3.10 and would couple the two. PLANNED means "mapped to a unit that is not built yet" and has no B1 equivalent; it becomes IMPLEMENTED only when B1-style evidence exists. Drift guard: `B1EnumGuard` compares `B1_STATES` with the `STATES` literal in B1's `chat_bind.py` and runs wherever that file is present (verified equal against main). If B1's enum changes, that test fails and the owner reconciles. IMPLEMENTED-BOUNDED is a claim label, not a state.

## Interpretation choices (IC)
- IC1: PLANNED is a seventh, non-B1 state (above).
- IC2: whitespace-only spans are structural non-requests (status None), not UNMAPPED.
- IC3: quote fragments under 8 chars are "unmatched", never wildcards.
- IC4: `explicit_maps` and `exclusions` are reviewed inputs and each needs a reason; no keyword heuristics.
- IC5: any span overlapping an exact match maps to the unit; every occurrence counts.
- IC6: X rows without a unit reference use unit "UNSPECIFIED".
- IC7: a pin_ref resolves only to a supplied span id; unresolved pins are listed, not failing.
- IC8: excerpt matching is whitespace-normalised (runs and newlines equal one space) and case-sensitive.
- IC9: spec headings "## ADD-0/1/2" are accepted alongside "## V2-0/1/2".
- IC10: precedence STOPPED > PARKED > SUPERSEDED > REFUSED_WITH_SUBSTITUTE > IMPLEMENTED > PLANNED.

## LIMITS
- The ledger proves mapping, not that code works or that a line is fulfilled.
- The green private real run depends on supplied owner-map data (`v21-owner-maps.json`). That is mapping supplied as data, NOT owner approval; the mapper does not verify who authored it.
- The private real run is green only on v2.1.1. The v2.1 to v2.1.1 spec edits (the empty quote removed on the parked-CBSE line, and the X12, X21, X22 excerpts recased to match the message text) were made by the spec owner and are what turned the gate green. Any "S8.2 green" claim must name those edits.
- Pins the spec cites (the gate, P1 to P3 and CBSE records) do not resolve to supplied spans and stay in `unresolved_pins`. The spec's claim that the 27-task gate is superseded is recorded as data, not treated as an approval.
- The public report holds no source text; the text-bearing ledger is private.
- The spec text claims 80 active units; its headers parse to 79 (51 + 28) plus 3 parked.
- Developed on Python 3.10 with `--noconftest`; the auditor runs the 3.12 real-conftest gate.
- Private run result (local, v2.1.1 + owner maps): 159 candidate spans, 28 non-requests, PLANNED 75, REFUSED_WITH_SUBSTITUTE 47, PARKED_BY_USER 7, SUPERSEDED 2, UNMAPPED 0, drift 0, 114 registry units.

## Mutation battery (repair child, auto-generated, 615 mutants)
Header: 615 generated, 612 killed, 3 equivalent, 0 unadjudicated survivors. Generator: comparison flips, boolean flips, +-1 on integers, raise->pass, string suffix edits, any/all swap, in/not-in swap, over the module (docstrings and imports excluded); only mutants that compile were run. Run on Python 3.10, PYTHONDONTWRITEBYTECODE=1, --noconftest.
Equivalent (3):
1. L95 and L119 (2 mutants): `"other"` section sentinel renamed. The value is only compared against known section names, so any other string behaves identically.
2. L323 `pos + 1` -> `pos + 2`: an overlapping occurrence at offset 1 needs a one-character-period fragment; span boundaries fall only after such a run, so both occurrences touch the same spans and the mapped set is unchanged.
Earlier auditor survivors (L170, L207, L259, L66, L30, L370-372, L151-163, L148, L331, L183, L296) are pinned by the repair tests; L66 leading-whitespace normalisation is killed or equivalent per the run above (not among the 3 survivors).
