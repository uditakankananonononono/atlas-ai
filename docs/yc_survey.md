# Survey of public descriptions: Cellcog, Strawberry browser, and YC multi-agent companies

Retrieved 2026-10-11 from the public pages listed below. Everything here is what each vendor says about
itself on its own pages. None of it was tested, and no product was used.

**Gaps, stated as given in the unit:** Cellcog and Strawberry browser internals are not public; this
survey is from public pages only. "YC companies" is unspecified, so the two YC entries below are a
small, non-exhaustive sample picked because their YC pages describe teams of cooperating agents. This
document does not claim the doc line is fulfilled. It records only what the vendors publish and what the
troop runner in this branch does and does not cover.

## Cellcog (https://cellcog.ai/support/product-overview)

- "General-purpose AI employees for any role, each with its own inbox, routines, cloud browser, and a memory that lasts, built on the CellCog super-agent."
- An AI employee "pulls in your other AI employees when the job needs them".
- Listed features on that page: a name and its own email address, routines with time triggers, an inbox, and one task board for the organization where every task has a status, a priority and an assignee.
- Also described at https://cellcog.ai/for-agents: employees "form teams, onboard and manage each other".

## Strawberry browser (https://strawberrybrowser.com/for-ai)

- "Strawberry is an agentic browser: a full web browser with AI companions built into it."
- "Strawberry companions work across many tabs in parallel, in the user's own logged-in sessions."
- "Strawberry asks for the user's approval before consequential actions such as sending email, making payments, or anything destructive."
- Runs on macOS and Windows; credit-based pricing, free plan with 500 credits per month, paid plans from $20/month (as stated on that page).
- "Strawberry Routines run recurring work on a schedule".

## YC sample (public YC company pages)

- Spine AI (https://www.ycombinator.com/companies/spine-ai): "a single prompt spins up a swarm of AI agents that plan, delegate, and execute complex tasks together — with humans fully in the loop." Work is shown as visible steps on a shared canvas.
- Dock (https://www.ycombinator.com/companies/dock): "a multiplayer agent workspace where you spin up teams of specialized, proactive agents". The agents "communicate, unblock each other, and manage each other".

## Recurring mechanisms across these pages

1. A planner step that breaks a goal into steps.
2. Several agents working in parallel.
3. Human approval before consequential actions.
4. A task board or visible step list.
5. Memory, inboxes, schedules and a real browser (Cellcog, Strawberry).

## What `backend/app/troop` covers

`roles.py` and `runner.py` implement mechanisms 1, 2 and 4 in a small form: a planner returns steps with
dependencies, independent steps run in parallel threads, a reviewer checks every result and rejects it
with feedback, the worker retries up to a limit, dependents of a failed step are blocked, and the run
returns a step-status table and a transcript. Two fixture task kinds exist (`text_stats`, `sum_table`).

## What it does not cover

- The planner is a fixed template per task kind. It is not a language-model planner.
- No language model, no browser, no email inbox, no memory across runs, no schedules, no human-approval gate, no tool integrations, no persistence.
- Not wired into any route, module registry or module of this repository.
- No comparison against the named products was run, so nothing here shows it is better than any of them.

## Scanner fixture note (S1.1)

The S1.1 scanner tests (`tests/troop/test_landscape_s1_1.py`) read the Cellcog, Strawberry browser and YC sample
sections above as saved-text fixtures. What the scanner extracts from them is vendor-stated keyword matches, not
tested product facts. The matrix covers only these pages. See `docs/TROOP_S1_FLEET_CONTRACT.md`.
