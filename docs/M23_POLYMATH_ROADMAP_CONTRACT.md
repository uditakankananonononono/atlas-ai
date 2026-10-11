# M23 polymath roadmap builder - contract

Excerpt from owner request: "and guide me towards my polymaths career and college".

Module: `backend/app/modules/m23_study_abroad/polymath_roadmap.py` (pure stdlib, no database, no network).
Tests: `tests/modules/test_m23_polymath_roadmap.py`.

## What exists today in m23 and what this adds
`advising.py` ranks majors and schools by word overlap and needs a database. `planning_tools.py` holds 20 deadline, cost and checklist helpers. `university_fit.py` filters a caller table. None builds a multi-domain career roadmap. This module adds one function, `build_roadmap(profile, curriculum, bridges, colleges, today, horizon_weeks=104)`.

## What it computes, from supplied data only
- Domain map: per domain, the stated level, dated evidence counts (future-dated items are counted separately and do not count) and a depth tier: none, started, developing, deep.
- Shape: no_evidence, single_domain, broad_shallow, one_deep_few_others, t_shaped or multi_deep. The thresholds (3 evidenced domains for breadth, 2 dated evidence items at advanced level for depth) are named heuristics, not standards.
- Schedule: the steps of her wanted domains plus any prerequisite steps they need, taken one domain at a time in her wanted order, fitted to her weekly hours as week ranges. Steps ending after the horizon are listed as unscheduled. Cycles are refused.
- Bridges: caller-declared pairs of domains, marked ready only when both have dated evidence.
- Colleges: for a caller-supplied table, covered and missing wanted domains, interdisciplinary flags, and staleness (older than 365 days). Order is coverage, then flag count, then id. This order is not an admission chance and not a quality ranking.

## What it does not do
- It uses no real profile. Her actual profile data is the missing input; tests use fictional data.
- It does not verify evidence, college rows or URLs, does not fetch anything, and makes no claim that she is or will be a polymath.
- It does not send, submit or post anything. Output always carries `requires_approval_before_any_external_action: true`.
- Curriculum steps and bridges are supplied by the caller; the module invents no courses or content.
- Not run: the repo conftest, mounted auth/tenant tests, repo floor. No route or UI wiring was written.

## Core repair bounds and refusals

The repair keeps the caller-supplied roadmap scope. Inputs now require exact
built-in dict/list/str types, not subclasses. Numeric inputs require exact int
or float, excluding bool. Invalid input raises `RoadmapInputError`, never an
arithmetic overflow or recursion exception on the bounded accepted surface.

- Weekly hours: finite, from 0.000001 through 100 inclusive. Positive values
  below the lower bound are refused rather than dividing into infinity.
- Step hours: finite, above zero through 1,000,000 inclusive. Numeric magnitude
  is checked before `math.isfinite`, so arbitrarily large ints refuse cleanly.
  With at most 2,048 steps and the weekly minimum, totals and week arithmetic
  remain within finite float range.
- Text and reference ids: at most 512 raw characters, nonblank exact strings.
  Source URLs: at most 2,048 raw characters, exact strings starting `https://`.
- Dates: exactly 10 raw characters in ASCII `YYYY-MM-DD` grammar followed by
  calendar validation. Compact dates, Unicode digits, subclasses and long
  strings refuse before parsing.
- Objects: at most 64 keys, each an exact string of at most 512 characters.
- Lists: 64 curriculum domains, wanted domains, goals, profile domain rows or
  college programs; 2,048 curriculum steps; 256 prerequisites per step,
  evidence items per domain, bridges or colleges. Length is checked before
  iteration. These are processing bounds, not advising standards.
- Errors are capped at 512 characters. Caller value echoes are limited to
  the first 128 characters of exact strings; other types use a fixed marker.
- Cycle detection and prerequisite closure are iterative. No recursive depth
  limit is used. Long acyclic chains within the 2,048-step cap are accepted;
  cycles still refuse. Scheduling order and the original heuristics remain
  unchanged.

Each type, size, range or grammar failure raises the module's typed error
with a field-specific message; no new machine-readable error-code API is
claimed. Unicode text outside the date grammar is not normalized or certified.
The original "Not run" floor statement above describes the initial delivery;
the repair was tested on real Python 3.12 with repository conftest. Mounted
route/UI integration and the repository-wide suite remain unverified.
