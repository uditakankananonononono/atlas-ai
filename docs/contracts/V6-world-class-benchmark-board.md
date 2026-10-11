# V6 — world-class benchmark board (c30.worldclass)



## What the code does

`backend/app/modules/c30/worldclass.py`, stdlib only (`math`, `re`, `unicodedata`, `datetime`, `urllib.parse`, `app.modules.c30.policy`), deterministic (sorted keys, floats rounded to 6 places for output, no wall clock except the caller-supplied `as_of`).

`run(request)` — request `{as_of: YYYY-MM-DD, runs: [...], baselines: [...]}` (allowlists; any other key at any level refused `PLAN_REFUSED_UNKNOWN:<schema parent field>`). Records SUPPLIED benchmark runs against SUPPLIED reported baselines and prints the numbers. Claims are limited to measured ones: every pair row naming a product carries its number and `source_url`; no summary adjectives, no 'world class' phrase. Nothing is run or fetched here; differing test sets or settings are not detected (LIMITS).

Validation order (first failure raises): (1) request is a dict; (2) bounded resource/type admission, then recursive forbidden-key scan over dict keys (through dict values and list items), key normalized casefold + `-` to `_`, exact match only; precedence SEND > SPEND > EFFECT > NOCREDS, alphabetically-first match within a class; (3) non-str dict key -> BAD_TYPE:key; (4) unknown keys -> UNKNOWN:<schema parent field>; (5) top-level types; empty required lists -> EMPTY:<field>; (6) caps -> OVERSIZE:<schema field>, checked BEFORE any character handling so over-cap always wins over every other field code; (7) per-field validation in list order (runs then baselines); (8) compute.

Behavior: value numeric (not bool, not NaN/inf); higher_is_better must be a bool (no default); benchmark/metric/name/run_id take a uniform Unicode refusal: non-str -> BAD_TYPE:<field>, over-cap -> OVERSIZE:<field> (cap first), blank -> EMPTY:<field>, any character of Unicode category Cc/Cf/Zl/Zp -> BAD_TYPE:<field>, and the refused value is never echoed; separator characters (Zs: plain space, NBSP, and the rest) are ACCEPTED in these fields ('MMLU Pro' is legitimate); as_of/run_date/reported_date strict calendar-valid ISO YYYY-MM-DD; run_date later than as_of -> BAD_TYPE:run_date; duplicate run_id -> BAD_TYPE:runs; duplicate (benchmark, metric, name) baseline -> BAD_TYPE:baselines. Baseline source_url missing/null/blank/unparseable/wrong scheme (casefolded, HTTPS accepted)/hostless/carrying userinfo/carrying any character with ord <= 32, DEL, or Unicode category Cc/Cf/Zl/Zp/Zs (whitespace and format characters included, so an inner space, tab, newline, NBSP, zero-width space or DEL all drop) -> baseline dropped, counted `no_source` (blank is a drop, never an EMPTY refusal; an over-cap source_url is OVERSIZE:source_url; a non-str source_url is BAD_TYPE:baselines); the URL is gated only, kept unchanged (port/query/fragment retained, percent-escapes such as %20 untouched, no normalization). Baseline reported_date after as_of -> dropped, counted `future_date` (a drop, never a refusal); equal to as_of is kept. Precedence: baseline checks run in this order and the first failure decides the single outcome: URL validity (failure counts once as no_source), then date (future_date), then verdict. A baseline that fails more than one check is counted once, under the earliest failing check. Pairing by (benchmark, metric), exact string equality, case-sensitive, no strip, no normalization, no whitespace collapse ('MMLU Pro' and 'MMLU  Pro' are different keys); one pair per baseline name. A run with no surviving baseline -> `no_baseline_rows` entry (raw value only). margin = value - baseline_value (reversed when higher_is_better is false); relative_margin = margin / abs(baseline_value) when baseline != 0, else null with flag `baseline_zero`. Verdict on the UNROUNDED margin: `ahead` if > 1e-9, `behind` if < -1e-9, else `tied`; only these words; rounding to 6 places is display-only. Zero pairs -> PLAN_REFUSED_UNMEASURED. Output `{pairs, no_baseline_rows, counts{ahead, behind, tied, no_baseline, no_source}, baseline_coverage, scope}`. `baseline_coverage` reports every supplied baseline exactly once: `{baselines_supplied, baselines_matched, baselines_unmatched, baselines_dropped_by_reason{no_source, future_date}}`, with the invariant supplied = matched + unmatched + no_source + future_date; the existing verdict counts are unchanged.

## Refusal table

All refusals are `ValueError` with message `PLAN_REFUSED_<REASON>[:field]`:

| Message | When |
|---|---|
| `PLAN_REFUSED_BAD_TYPE:request` | request not a dict |
| `PLAN_REFUSED_SEND:<key>` | normalized key in SEND table (highest precedence) |
| `PLAN_REFUSED_SPEND:<key>` | normalized key in SPEND table |
| `PLAN_REFUSED_EFFECT:<key>` | normalized key in unit EFFECT table (publish/post/file/register/submit/signup/sign_up/trade) |
| `PLAN_REFUSED_NOCREDS:<key>` | normalized key in NOCREDS table |
| `PLAN_REFUSED_BAD_TYPE:key` | non-str dict key |
| `PLAN_REFUSED_UNKNOWN:request|runs|baselines` | key outside the allowlist at that level |
| `PLAN_REFUSED_BAD_TYPE:as_of|run_date|reported_date` | date not strict calendar-valid ISO; run_date after as_of |
| `PLAN_REFUSED_BAD_TYPE:runs|baselines` | wrong list/item type, value not numeric, higher_is_better not bool, duplicate run_id or (benchmark, metric, name), non-str source_url |
| `PLAN_REFUSED_EMPTY:runs|baselines` | required list empty |
| `PLAN_REFUSED_OVERSIZE:runs|baselines|benchmark|metric|name|run_id|source_url` | >500 items; field over its cap (200 chars; source_url 2000), checked before clean_text |
| `PLAN_REFUSED_BAD_TYPE/EMPTY/CONTROL_CHARS:<field>` | clean_text's own codes, unremapped |
| `PLAN_REFUSED_UNMEASURED` | zero pairs after drops |

## LIMITS

Does not run benchmarks; runs and baselines are supplied and unverified; differing test sets or settings are not detected. No URL fetch, no live source verification. This unit does NOT call `policy.check` (no action path); it uses the real `policy.clean_text` and `policy.scope`, no adapter, no fallback. It recognizes only the standing-rule forbidden-key classes; nothing in an input field can grant spend/send/effect/credential permission.

## Neighbor check (own read on main `6fef7fc9`)

`c30/` holds only `__init__.py` (empty blob, untouched) and `policy.py`; this unit adds `worldclass.py` only. Neighbors not duplicated: `c31/bench.py` (pass/best/ceiling bools — different mechanism), SelfImprovementLab / instinct_doc improvement modules (absolute gain — different mechanism), agi_evaluation hash freeze and m21 holdout comparison (different mechanisms). No collision.


## Resource admission

Before forbidden-key normalization or scanning, exact builtin dict/list containers and exact builtin string keys are admitted. Subclass containers refuse BAD_TYPE:<constant schema parent>, malformed keys refuse BAD_TYPE:key, raw keys longer than200 refuse OVERSIZE:key before casefold/replace. Every dict, including the request envelope, has a200-key cap. Lists default to200 items; lists under runs/baselines retain500-item caps. These per-dict caps deliberately include schema envelopes and differ from a no-total-envelope-cap policy. Oversized containers refuse OVERSIZE:request|runs|baselines before their child iterator is requested.

Traversal charges containers only, with a10000-container budget and maximum depth32 (root depth0; scalar depth checked too). Cycles refuse BAD_TYPE:request; shared noncyclic aliases are traversed and charged separately. Children use bounded recursive iterators, no comprehension copy or pending-child list. Each container's count/depth/width is checked before its child iterator. A complete admission pass finishes before any forbidden key is normalized, so malformed keys, resource refusals and cycles now precede forbidden classes. Ordinary admitted forbidden precedence is unchanged. Scalar schema validators otherwise retain their existing behavior.
