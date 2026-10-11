# S8.2 spec-to-ledger mapper contract

Source excerpt (supplied text; this module does not verify who wrote it): "keep an eye out for top secret projects, governement stuff too, super elite stuff"

Source pin: the runtime reads a supplied spec file and supplied source messages. They are source rows, not owner-channel records, and authorship is not verified. Committed fixtures are invented. Any real inputs stay in a local, git-ignored directory and are never committed; digests and expected results for them live only in a local pins file.

Module: `backend/app/modules/instinct_doc/spec_ledger_s82.py`. Tests: `tests/modules/test_instinct_spec_ledger_s82.py`. No routes, no wiring, no network, stdlib only.

## Fixtures and privacy
- Committed fixtures under `tests/fixtures/s82/` are synthetic (invented spec, two invented source messages, invented maps). They exercise the parser and mapping paths.
- `tests/fixtures/s82_private/` is git-ignored. If it holds a local pins file, an extra test class verifies the pinned digests and results; otherwise those tests skip.
- Lineage: this branch holds only clean commits on the base and only synthetic fixtures. An earlier local attempt is not part of this history and must not be pushed.

## Caller boundary
- Strict builtin types: containers must be exactly `list`/`dict`, scalars exactly `str`/`int`; subclasses are refused. Dict keys must be `str`.
- Order of checks is uniform: strict type first, then the raw length cap (before any strip, regex, enum membership or character scan), then everything else. For the spec: type, raw cap 400000 chars, empty (after strip), character policy. A whitespace-only spec of 400001 chars is `too_long`, not `empty`. The same order applies to map reasons (2000 chars), unmatched excerpts (2000), source `message_id` (64), source `ts` (64) and registry `status` (32).
- Caps: sources 16 (200000 chars each), spans 20000 in total, registry 512 entries (7 keys each), excerpts 64 per unit (2000 chars each), evidence 8 keys (strings up to 2000 chars, lists up to 64), explicit maps and exclusions 4096 entries each, 64 unit ids per map entry, span-id keys 80 chars, reasons 2000 chars, `kind` 32 chars, `spec_line` 0 to 1000000.
- Character policy: Cc, Cf, Zl and Zp characters are refused everywhere. Surrogate (Cs) characters are refused only in the digest-fed source fields (source `ts` and `text`); see IC12. Content fields (spec text, source text, excerpts) carve out exactly LF, CR and TAB, because the line parser and chat sources need newlines and tabs. Identifiers, reasons, evidence fields and ids have no carve-out. Source text is otherwise kept exactly (no normalisation).

## API
- `split_spans(text)`: lossless partition of a message into sentence/bullet spans.
- `parse_spec(text)`: registry from the spec (units under "## 2." and "## V2-1"/"## ADD-1", X rows under "## 1." and "## V2-2"/"## ADD-2", gate/parked under "## V2-0"/"## ADD-0"; the trailing space keeps ADD-10 out).
- `map_ledger(sources, registry, explicit_maps=None, exclusions=None)`: rows `{source_msg, line_no, verbatim, unit_ids, status}` plus a public report without source text.
- `require_complete(ledger)`: raises `PLAN_REFUSED_UNMAPPED_LINE:<n>`, then `PLAN_REFUSED_DRIFT:<n>`.
Refusals use the `PLAN_REFUSED_` prefix (source, registry, map, spec-line, UNMAPPED_LINE, DRIFT), are single-line and never echo source text. Control, format, line-separator and paragraph-separator characters are rejected in interpolated and identifier fields; surrogates only in digest-fed source fields (see Caller boundary).

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
- IC11: Cf is refused in source text (only LF, CR and TAB are carved out), so genuine chat text containing zero-width or other format characters (for example a zero-width joiner or a byte-order mark) is refused with `SOURCE:bad_char:text`, never silently altered or stripped. The module never alters its input; refusing text that contains such characters is a documented limitation of the refusal policy.
- IC12: lone surrogate characters (Cs) are refused only in source `ts` and `text`, because the source digest is encoded to bytes and a lone surrogate would raise a UnicodeEncodeError there. This is a mechanism-tied limitation, not a general Cs ban: spec text, excerpts, reasons and evidence are not refused for Cs alone.

## LIMITS
- The ledger proves mapping, not that code works or that a line is fulfilled.
- A green run depends on the supplied mapping data. That data is not an approval, and the mapper does not verify who produced it.
- If the supplied spec was edited to make the gate green, any "S8.2 green" claim must name those edits and who made them.
- Pins the spec cites do not resolve to supplied spans and stay in `unresolved_pins`. A spec statement that a gate is superseded is recorded as data, not treated as an approval.
- The public report holds no source text; the text-bearing ledger is private.
- Developed on Python 3.10 with `--noconftest`; an independent run on the target interpreter with the repo conftest is the landing gate.

## Mutation battery (caller-boundary repair)
Builder-only evidence; the fresh gate must verify it, and this section does not pre-claim equivalence for the auditor. Header: 754 generated, 749 killed, 5 judged equivalent by the builder, 0 unadjudicated survivors. Mutants are auto-generated over the module (comparison and boolean flips, +-1 on integers, raise to pass, string suffix edits, any/all swaps, in/not-in swaps); only mutants that compile were run, on Python 3.10 with `--noconftest` and bytecode writing off.
Builder-judged equivalent (5), each pending independent confirmation:
1. Section sentinel renamed (2 mutants): the value is only compared with known section names, so any other string behaves the same.
2. Overlap offset `pos + 1` to `pos + 2` (1 mutant): an overlapping occurrence at offset 1 needs a one-character-period fragment; span boundaries fall only after such a run, so both occurrences touch the same spans.
3. Evidence-key guard `any` to `all` (1 mutant): a non-`str` evidence key always fails the per-key `_field_ok` strict-type check that follows, so this flip changes nothing.
4. Message-id upper bound `_MID` 64 to 65 (1 mutant): the explicit 64-char guard runs before the regex, so the regex bound is never reached by a longer id.
The other raw-cap seams (source `ts` at 64/65 including a valid 64-char fractional timestamp, `message_id` 64/65, `status` 32/33) are pinned by tests, not claimed equivalent: a recording test shows the value reaches the scan at the limit and does not above it.
Withdrawn: the earlier claim that the registry, source and map-value key guards (any/all, or/and, and the registry key-count 7 to 8) are equivalent. That held only for ordinary strings. A `str` subclass whose value equals an allowlisted name compares equal to it and passes the key-set check, so dropping the strict guard would let such keys through; each of the three shapes now has a pin (single and mixed subclass keys), and the registry key-count limit is pinned as a resource-order check (an entry over the limit is refused before the key-set scan). The `_norm` leading-whitespace flip is equivalent at the public mapping level (fragments strip to non-blank before counting, the leading space never joins a match). Further dispositions from the independent battery (pending the fresh gate): the digest-guard flag on source `ts` (Cs refused in `ts`) is equivalent, because a `ts` with a surrogate cannot pass the calendar parser; the same flag for source `text` is required and pinned. Four behavior holes found there are now pinned by tests: leading-whitespace normalisation and offset mapping (`_norm`), identifier-class `ts` refusing LF/CR/TAB, LF/CR/TAB accepted in both matched and unmatched excerpts, and an exact non-ASCII source-digest known-answer value.
