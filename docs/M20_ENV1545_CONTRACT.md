# M20 Row 1545 Environmental Testing contract

Ledger source pin: audits/coverage-register.json row 1545, requirement verbatim "Environmental Testing", description verbatim "" (empty - the requirement title is the whole spec). Row status in the ledger ("verified-practitioner-depth") is a builder attribution read from the ledger, not re-verified by this unit.

Purpose: multi-profile validation and aggregation bookkeeping over caller-supplied environmental exposure declarations. This is NOT an environmental-testing capability and NOT a physical model: unlike row 1547 there is no existing formula to reuse. It is a bounded plan over caller-supplied condition declarations (condition, setpoint, unit, dwell hours), for supplied specimen count, preconditioning, measurements and declared acceptance criteria. Pure stdlib, no I/O, deterministic.

Delta against the existing mechanism `_env(d, 'environmental')` in `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py` (read on live main 98bbd4ecb888c3c18271336bb42a2c434fca65ee, line 223):
- Existing: a passive echo of `profiles`, `specimen_count`, `preconditioning`, `measurements`, `acceptance_criteria` with `test_executed: False`; no validation, no schema, untagged failure modes. It computes nothing.
- New (interface only): bounded multi-profile declaration (1 to 20 profiles) with exact input and profile key sets, ENV1545-tagged refusals, specimen_count (integer 1..1000), preconditioning (0..10) and measurements (1..20) and acceptance_criteria (0..10) as non-empty texts of at most 64 chars (never evaluated), condition/unit bookkeeping enums, wide setpoint sanity bounds, condition counts in sorted order, fsum total dwell and max dwell, plan explicitly labeled plan_only with test_executed False.

Input keys (exactly): profiles, specimen_count, preconditioning, measurements, acceptance_criteria. Profile keys (exactly): condition, setpoint, unit, dwell_hours. Conditions: temperature (units celsius/fahrenheit/kelvin), humidity (percent_rh), pressure (kpa), salt_fog (percent), dust (g_per_m3), solar (w_per_m2). Setpoint sanity bounds (bookkeeping, not physical limits): temperature [-273.15, 1000], humidity [0, 100], pressure [0, 10000], salt_fog [0, 100], dust [0, 1000], solar [0, 2000]; dwell_hours in (0, 100000], finite, non-bool numbers.
Refusals: EnvError (a ValueError) with prefix "ENV1545: ". Output carries three fixed limits strings.
Validation order pins: strict builtin types only (type(x) is, never isinstance, so subclasses and bool are refused); strict key types (every mapping key must be exactly str); container length and key counts before any set construction or iteration, pinned by sys.setprofile ordering tests. Raw text caps run first where they apply (64 chars cap before strip, before Unicode; condition and unit capped at 32 before the enum). Unicode refusal (Cc/Cf/Zl/Zp refuse, Zs accept, explicit U+00AD and U+2060 pins) applies to free text that is echoed or carried: preconditioning, measurements, acceptance_criteria, and the condition/unit strings after their enum checks. Cs surrogates: the text lists carry the Cs residual (a lone surrogate is neither refused nor normalized there; consumers must treat them as opaque); finite enums refuse surrogates outright.

Scope: bounded exact deterministic bookkeeping over caller-supplied declarations. No environmental conditioning, solver execution, certification, or release authority; plans are labeled plans, never results. The unit enums and bounds are bookkeeping conventions chosen by the builder (interpretation choice, disclosed), not test standards.

New files only: environmental_testing1545.py, test_m20_environmental_testing1545.py, this document. The shared cluster file engineering_1510_1559.py is not edited.

Limits and residual disclosures:
- Conditions, units and setpoint bounds are builder bookkeeping conventions, not IEC/ISO/MIL-STD parameters; a human test engineer owns the real standard.
- Supplied preconditioning, measurements and acceptance criteria are carried as bookkeeping only and are never checked against anything.
- Dwell totals are arithmetic sums of supplied numbers, not a schedule or sequence claim.

## Change note

Build order disclosure: the module was drafted before its test file in this session (opposite of the family's red-first convention); the tests were then written to pin the behavior and a mutation battery was run against the result. No commit history was rewritten; both artifacts land together.
