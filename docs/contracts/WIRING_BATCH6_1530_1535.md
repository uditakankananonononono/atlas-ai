# Mounted supplied-input engines: rows 1530 and 1535

Two stateless POST routes under `/api/v1/api/modules/20`:
- `/design-for-six-sigma/1530/run`: calls `design_for_six_sigma1530.run(data)` for supplied CTQ specifications, DMADV phase and verification-plan reference bookkeeping. No sigma computation or statistical validation claim.
- `/quality-assurance/1535/evaluate`: calls `qa_evidence1535.evaluate_qa_evidence(data)` for supplied requirement conditions and observations. Runs no tests, persists nothing and grants no release authority.

Envelope: required `data` object; optional `tenant_id`, `actor_id`, and at most 64 `resource_refs`. Production tenant context is required. Conflicting identity labels and cross-owner/actor references are refused with 403. References are metadata only and retrieve nothing. Shared computation boundaries check depth, nodes and nonfinite numbers. Surrogates are refused before model validation. Engine ValueError, TypeError and KeyError map to 422. Successful engine output is preserved with authenticated tenant_id and actor_id added. No state or last-report endpoint is introduced.

## Scope

closed-scoped, NOT literal breadth. Accepted only as what the engine's own module docstring states it does, over caller-supplied inputs, and only to the extent its own tests prove. It does not establish the row's literal capability and authorizes, executes, merges, releases or approves nothing.

The route wiring does not verify supplied observations, signatures, scientific validity or physical measurements. Both engine files remain unchanged. FULL-SUITE UNVERIFIED: only the engine and mounted route floors were run. Independent review and current-main composition remain required before landing.
