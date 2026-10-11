# S1.1-S1.3 fleet units: tool-landscape scanner, replication planner, troop roster (contract)

Source pins (from the v2 mega-spec lines 42-50, as relayed by the integrator; I did not see the spec itself):

> S1.1 tool-landscape-scanner | /c31/tool-scan | FLEET_REFUSED_* (NOSOURCE, UNLICENSED, SPEND)
> Source: "Has a whole troop of agents inspired but better than Cellcog, strawberry browser and similar tools maybe search up yc companies and replicate them and integrate into atlas".
> Scope: takes a supplied list (YC directory export, GitHub repos, product pages saved as text), extracts capabilities, license, price tier; outputs a capability matrix and gap list against Atlas modules. No live crawling beyond free public pages with robots respected.

> S1.2 capability-replication-planner | /c31/replicate-plan
> Source: same + "replicate them and integrate into atlas".
> Scope: from the matrix, emits a per-capability build ticket (acceptance tests first) for the builder fleet; marks each "integrate (open source, license ok)" or "build ourselves" per her line "actually integrate it into themselves if its opensource of build it into themselves if itsnt". Refuses closed-source copying (FLEET_REFUSED_UNLICENSED).

> S1.3 agent-troop-roster | /c31/troop
> Source: "a whole troop of agents"; "Autonomously build whole digital companies with autonomous worker ai bots".
> Scope: typed worker roles (researcher, analyst, builder, writer, critic, auditor) with a deterministic scheduler, budget ledger, and per-agent audit log, wrapping existing m20 worker. Max concurrency is a configured number reported back.

Source pin: instinct doc S1.1-S1.3, v2 mega-spec lines 42-50. The integrator's follow-up brief adds the line "come across any tool and rewrite its code to integrate it in it.", says S1.2 also refuses any paid tier (FLEET_REFUSED_SPEND), says S1.3 wraps `backend/app/troop/runner.py`, `roles.py` and `docs/yc_survey.md`, and says vendor claims are labelled vendor-stated and matrix coverage is "pages supplied, reported".

## Honest scope (read this first)

- This is a fixture-runner bookkeeping prototype. It is not an M20 or model troop and not autonomous companies. Nothing here is a model agent, builds a company, or acts on its own.
- The roster's roles only decide which agent a job is assigned to and logged under. The worker is always the fixed toy `ActionWorker` and the planner is the fixed template planner. There is no worker injection: `run_roster` takes only the request, so no object with its own I/O, network, build or spend can be passed in.
- Jobs run sequentially. `max_concurrency` is the per-job runner pool size (the runner's `max_workers` for the steps inside one job), not a count of agents running at once.
- S1.2 takes the supplied pages and derives everything itself: matrix, license and price are re-derived from the supplied pages by the S1.1 scanner on every call. It does not accept a scan result, so a scan with an edited tier cannot be fed in.
- The wrapper of the existing M20 worker named in the source scope was not built (see choice 9).

## What was built

Mechanisms only, under `backend/app/troop/` (the existing package), stdlib only, offline, proposals only. No routes are added: the `/api/v1/c31/...` routes and any wiring belong to the integrator.

| File | Role |
|---|---|
| `fleet_common.py` | shared refusal codes, `FleetRefusal`, exact-type and control-character scan |
| `landscape.py` | S1.1 `scan_landscape(request)`, `render(request)` |
| `replicate.py` | S1.2 `plan_replication(request)` |
| `roster.py` | S1.3 `run_roster(request)` |
| `runner.py` (edited) | `RunResult` gains `max_workers`, set from the runner's configured value (two added lines) |
| `docs/yc_survey.md` (edited) | one short appended section naming it as the scanner's fixture |

Tests: `tests/troop/test_fleet_common_s1.py`, `tests/troop/test_landscape_s1_1.py`, `test_replicate_s1_2.py`, `test_roster_s1_3.py`, `test_s1_contract_doc.py`.

## S1.1 scanner

Input: `records` (each `name`, `source_kind` of yc_export / github_repo / product_page, `text`, optional `source_ref`), `atlas_capabilities`,
optional `spend_usd` (must be 0) and `require_open_license`. Output: per-record capabilities, license class, price tier; a capability matrix;
a gap list (matrix capabilities not in `atlas_capabilities`); `coverage` ("pages_supplied", "supplied pages only"). Nothing is fetched: a
`source_ref` is stored and never opened, so no crawling and no robots question arises. Every statement is labelled `vendor-stated`.
Page text is data: it may carry newlines, but nothing in it can change behaviour, and it is never echoed.

## S1.2 planner

Input: `records` and `atlas_capabilities` (the same supplied pages S1.1 takes), optional `adopt` (tool names), optional `spend_usd` (must be 0). Output: one `PROPOSED` ticket per gap, sorted by
capability, each with three acceptance tests, steps starting "write acceptance tests (red)", `estimated_spend_usd` 0, and a decision of
"integrate (open source, license ok)" or "build ourselves". Nothing is built, copied or bought. The matrix is re-derived from the pages on every call, so price and license always come from the page text.

## S1.3 roster

Input: `agents` (id, role), `max_concurrency` (1..16), `budget_units`, `jobs` (id, role, cost, task). A job's task kind must be one of the template planner's kinds (`text_stats`, `sum_table`), else the whole request is refused with `S1.3:bad_task_kind` before anything is charged. A planner error during a run (for example a non-numeric `top_n`) is recorded as a failed job with `error` `planner_error`, charged, and logged; it does not escape. Each job goes to the least-loaded agent of its role
(ties by id), is charged against the budget, then runs through the existing `TroopRunner` with `max_workers` set to the configured concurrency. Output reports the
configured `max_concurrency`, results, unassigned jobs, the budget ledger and a sequenced audit log per agent. Budget units are abstract counters, not money.

## Refusals

Policy refusals are `FleetRefusal` (a `ValueError`) whose message is exactly the code: `FLEET_REFUSED_NOSOURCE`, `FLEET_REFUSED_UNLICENSED`, `FLEET_REFUSED_SPEND`.
All others read `S1.1:<code>`, `S1.2:<code>` or `S1.3:<code>`, for example `S1.1:bad_type:records`, `S1.1:control_chars:records`, `S1.1:limit_exceeded:records`,
`S1.3:bad_task_kind`, `S1.3:duplicate_agent`. Messages never contain input text. Every string and dict key is checked first for Unicode categories Cc, Zl and Zp
(page text keeps only newline, carriage return and tab). Exact types only: subclasses and foreign objects are refused.

## Interpretation choices

Nothing below is pinned by the source text. Each is mine.

1. INTERPRETATION CHOICE: capability tags and their keyword patterns (agent_teams, browser_automation, email_inbox, human_approval, memory, parallel_execution, planning, scheduled_routines, task_board) are a small fixed vocabulary. A capability is "found" when a pattern matches the supplied text. A capability a page does not mention is not shown absent from the product.
2. INTERPRETATION CHOICE: "Atlas modules" in the gap list is a caller-supplied list of Atlas capability tags (`atlas_capabilities`). I could not derive Atlas capabilities from the repository, so the gap list is only as good as that list.
3. INTERPRETATION CHOICE: license classes OPEN_PERMISSIVE (MIT, Apache-2.0, BSD, ISC), OPEN_COPYLEFT (GPL family, MPL-2.0), CLOSED (proprietary, all rights reserved, closed-source), UNKNOWN. Both open and closed statements in one text give UNKNOWN with `conflicting_statements` true. A license reading is not legal advice.
4. INTERPRETATION CHOICE: price tiers FREE, FREEMIUM ("free plan/tier" plus a money amount), PAID (money amount without a free plan), UNKNOWN. Money amounts are `$`, `€` or `£` followed by a digit.
5. INTERPRETATION CHOICE: FLEET_REFUSED_NOSOURCE means a record with blank text. FLEET_REFUSED_SPEND in S1.1 means `spend_usd` other than 0. FLEET_REFUSED_UNLICENSED in S1.1 happens only when the caller sets `require_open_license` and a record is not open-licensed.
6. INTERPRETATION CHOICE: in S1.2 only OPEN_PERMISSIVE with a non-PAID price counts as "integrate (open source, license ok)". Copyleft is open source but is sent to "build ourselves" with reason `copyleft_needs_human_review`. Other reasons: `paid_tier_not_adopted`, `no_open_provider_license_ok`.
7. INTERPRETATION CHOICE: S1.2 refuses by explicit `adopt` request: a named tool that is not OPEN_PERMISSIVE refuses FLEET_REFUSED_UNLICENSED, then one with a PAID tier refuses FLEET_REFUSED_SPEND. Without an `adopt` list, closed or paid providers do not refuse; they only produce "build ourselves" tickets.
8. INTERPRETATION CHOICE: three fixed acceptance-test templates per capability, and four fixed steps. A real ticket would need real tests written by the builder fleet.
9. INTERPRETATION CHOICE: S1.3 "wrapping existing m20 worker" was not done. `m20_general_cognitive_worker` is a large module collection with no single worker entry point I could identify, and the integrator's later brief names the troop runner and roles instead. The roster wraps `TroopRunner` with the fixed toy `ActionWorker` only. `run_roster` takes no worker argument, so no other worker can be supplied.
10. INTERPRETATION CHOICE: scheduler rule is least assigned jobs, then smallest agent id; jobs are processed in the order given. A job whose role has no agent is `unassigned`. A job that exceeds the remaining budget is `refused` with FLEET_REFUSED_SPEND and later cheaper jobs still run.
11. INTERPRETATION CHOICE: configured concurrency is the runner's `max_workers` for the steps inside one job. Jobs run one after another, so it is not a count of agents running at once.
12. INTERPRETATION CHOICE: limits: 200 records, 100000 text chars, 100 name chars, 500 ref chars, 200 atlas tags; 100 gaps, 100 adopt names; 50 agents, 200 jobs, concurrency 1..16, 64 id chars, 10^9 budget or cost; nesting depth 8.

## Limits

- The roles do not change what the worker does; they only decide who a job is assigned to and logged under. Nothing here is a model agent, autonomous, or a digital company.
- The scanner finds keywords. It does not test products, fetch pages, check licenses or verify any vendor claim.
- Routes `/api/v1/c31/{tool-scan,replicate-plan,troop}/run`, wiring, ledgers and push belong to the integrator.

## Mutation battery and the six survivors

Program: `mutauto.py` (attached to the delivery). It parses each of the four modules, and one at a time swaps a comparison operator, flips an and/or, drops a `not`, flips a bool, adds 1 to an int, or appends `~` to a string (docstrings skipped), runs `tests/troop` with `-x` in an isolated copy, and records the original and mutated expression, the status and the first failing test. `mutation.jsonl` holds every mutant. Result: fleet_common 48 mutants, 0 survivors; replicate 113, 0 survivors; landscape 183, 4 survivors; roster 194, 2 survivors. Argument for each survivor:

1. landscape line 66, `p and c` to `p or c`: this is the last branch of `_license`. The earlier branches have already returned for closed-with-open, permissive-only and copyleft-only, so the only inputs that reach it are "both open classes" (p and c true) and "neither" (both false). `p or c` is true for exactly the first and false for the second, the same as `p and c`. Equivalent on every reachable input.
2. landscape line 109, keys `"a"`, `"s"`, `"o"` (three mutants): the dict `{"a": atlas, "s": spend, "o": req_open}` exists only to be walked by the type and control-character scan. Its keys are never read back. Renaming a key changes nothing observable. Equivalent.
3. roster line 91, initial load `0` to `1`: every agent starts with the same load, so the order of "least loaded, then id" is unchanged. Equivalent.
4. roster line 106, `load += 1` to `+= 2`: every assignment adds the same step, so the order of loads is unchanged. Equivalent.
