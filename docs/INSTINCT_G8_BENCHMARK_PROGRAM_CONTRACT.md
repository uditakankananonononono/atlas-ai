# Group 8 benchmark program contract

Source request (instinct doc, group 8, paragraph 72): compare every project
against leading field benchmarks.

## What is built (real runtime behavior)

`backend/app/modules/instinct_doc/benchmark_program_g8.py` adds the two
pieces the landed c30.worldclass board does not have:

1. Every-project coverage. Runs are keyed by project against a supplied
   project registry; unregistered projects are refused and a per-project
   ledger reports UNMEASURED projects instead of silently omitting them.
   Program summary includes measured/total coverage.
2. Independent checking. A baseline only supports an AHEAD/TIED/BEHIND
   verdict when at least two independent registrable source domains report
   values whose max-min spread fits a relative tolerance (default 5%,
   configurable to 50%) - order-independent, permutation-tested. Domains
   are grouped by a small eTLD+1 approximation (last two labels, or three
   under common second-level suffixes like co.uk): www.vendor.com and
   blog.vendor.com are ONE source. Stated limit: this is not the full
   public-suffix list; multi-part suffixes outside the small built-in set
   are treated as plain TLDs (a.blogspot.com groups as blogspot.com).
   - single-source baselines are computed and flagged but never support a
     verdict (project verdict MEASURED_UNVERIFIED)
   - two or more domains that disagree are reported as conflicting and the
     comparison is marked unchecked_conflict
   - the representative value per domain is the latest report; the checked
     value is the median across domains
   - runs per project/benchmark/metric are aggregated by median
   - future-dated baselines are dropped and counted; future-dated runs and
     malformed inputs are refused

A task-bound verification receipt (verify()) validates the exact result
envelope (no extra or missing top-level fields), then re-derives every
median, agreement check, comparison, ledger entry and summary count from
the original task inputs with separately written logic, comparing field by
field; run() flips to verification_failed on any mismatch. Nothing in a
result is trusted. Honest limit: verify() shares validation helpers with
analyze() (and the static scope block), so the receipt proves internal
consistency between task and result - it is not an independent measurement
of the underlying benchmark runs.

Bounds: at most 256 projects, 2000 runs, 2000 baselines; values finite and
within 10**18; strict ISO dates; HTTPS source URLs only; unknown keys,
duplicate projects/run ids, booleans and non-finite numbers refused.

## Verification

31 hermetic stdlib-unittest tests in
`tests/modules/test_group8_benchmark_program.py`: cross-checked ahead with
coverage ledger, single-source and conflicting-source teeth, tolerance
boundary, same-domain dedup, latest-per-domain representative, behind/tied,
lower-is-better, median aggregation, future-drop, zero baseline,
determinism, every refusal class, and tamper cases proving the receipt
rejects edited verdicts, medians, baseline statuses, ledger entries,
coverage, hidden projects and unknown envelope fields - including a full
leaf-tamper sweep over every scalar in a result (69 tampers, 0 survivors).
All green.

## What is NOT achieved (named missing scope)

- Benchmarks are not run here: run values are caller-supplied.
- Leading-tool figures are not fetched or verified live: baselines are
  caller-supplied; the two-domain check proves consistency between sources,
  not truth. "Leading" is by caller declaration.
- Library surface only: no HTTP route, no UI, no CI enforcement.

Verdict for group 8 remains PARTIAL.
