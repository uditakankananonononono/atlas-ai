# M20 Row 1548 Thermal Cycling contract

Ledger source pin: audits/coverage-register.json row 1548, requirement verbatim "Thermal Cycling", description verbatim "" (empty - the requirement title is the whole spec). Row status in the ledger ("verified-practitioner-depth") is a builder attribution read from the ledger, not re-verified by this unit.

Purpose: validation and aggregation bookkeeping over one caller-supplied thermal-cycle declaration. This is NOT a thermal-cycling capability and NOT a chamber model: unlike row 1547 there is no existing formula to reuse. The cycle-time figure is new interface-level arithmetic over the supplied numbers (dwell_low + dwell_high + 2 x swing / ramp), labeled an idealized estimate, not a simulation. It is a bounded plan over a supplied cycle profile, cycle count, specimen count, preconditioning, measurements and declared acceptance criteria. Pure stdlib, no I/O, deterministic.

Delta against the existing mechanism `_env(d, 'thermal_cycling')` in `backend/app/modules/m20_general_cognitive_worker/engineering_1510_1559.py` (read on live main 98bbd4ecb888c3c18271336bb42a2c434fca65ee, line 223):
- Existing: a passive echo of `profiles`, `specimen_count`, `preconditioning`, `measurements`, `acceptance_criteria` with `test_executed: False`; no validation, no schema, untagged failure modes. It computes nothing.
- New (interface only): exact input and profile key sets with THERM1548-tagged refusals, cycles (integer 1..100000), specimen_count (integer 1..1000), preconditioning (0..10) and measurements (1..20) and acceptance_criteria (0..10) as non-empty texts of at most 64 chars (never evaluated), temperature order enforcement (low < high), idealized cycle-time and total-time arithmetic labeled plan_only with test_executed False.

Input keys (exactly): profile, cycles, specimen_count, preconditioning, measurements, acceptance_criteria. Profile keys (exactly): low_temperature_c, high_temperature_c, ramp_rate_c_per_min, dwell_low_min, dwell_high_min. Temperatures finite in [-273.15, 1000] with low strictly below high; ramp in (0, 1000]; dwells in [0, 100000] (zero dwell allowed); all non-bool numbers.
Refusals: ThermError (a ValueError) with prefix "THERM1548: ". Output carries three fixed limits strings.
Validation order pins: strict builtin types only (type(x) is, never isinstance, so subclasses and bool are refused); strict key types; container length and key counts before any set construction or iteration, pinned by sys.setprofile ordering tests. Raw text caps run first (64 chars cap before strip, before Unicode). Unicode refusal (Cc/Cf/Zl/Zp refuse, Zs accept, explicit U+00AD and U+2060 pins) applies to preconditioning, measurements and acceptance_criteria. Cs surrogates: the text lists carry the Cs residual (consumers must treat them as opaque).

Scope: bounded exact deterministic bookkeeping over caller-supplied declarations. No chamber execution, solver run, certification, or release authority; plans are labeled plans, never results. Estimated cycle time assumes constant ramp rate and instant turnaround at each dwell; real chambers deviate.

New files only: thermal_cycling1548.py, test_m20_thermal_cycling1548.py, this document. The shared cluster file engineering_1510_1559.py is not edited.

Limits and residual disclosures:
- The cycle-time figure is idealized arithmetic (constant ramp, no soak lag, no gradients), not a measured or simulated chamber response.
- Supplied preconditioning, measurements and acceptance criteria are carried as bookkeeping only and are never checked against anything.
- Temperature bounds are wide bookkeeping sanity limits, not a standard's envelope.

## Change note

Build order disclosure: the module was drafted before its test file in this session (opposite of the family's red-first convention); the tests were then written to pin the behavior and a mutation battery was run against the result. No commit history was rewritten; both artifacts land together.

## Arithmetic-honesty repair (2026-10-12)

Defect found by audit: a finite positive ramp as small as the least positive float (5e-324) with low 0 / high 100 and zero dwells produced estimated_cycle_time_min = inf and estimated_total_time_min = inf and was ACCEPTED - an arithmetic-honesty defect: the plan claimed inf "estimates" instead of refusing.

Repair (this commit): two explicit finite-derived-result checks with tagged ThermError refusals, after the supplied numbers are admitted and before the plan is returned:
- "THERM1548: derived cycle time is not finite" when the per-cycle figure (dwells plus two ramp legs) is not finite;
- "THERM1548: derived total time is not finite" when the per-cycle figure is finite but the total over the supplied cycles overflows (e.g. ramp 1e-304, swing 100, cycles 100000 -> per-cycle 2e306 finite, total inf).

Admission is NOT narrowed: the contract still admits any finite positive ramp through 1000 and any finite temperatures in range with low < high. No arbitrary minimum ramp, swing, dwell or cycle count was introduced. Stay-green pins prove the boundary: a subnormal ramp with a matching subnormal swing (estimated cycle time exactly 2.0), a 1e-305 ramp (result 2e307, finite), and ramp 1000 all remain admitted. The refusal covers derived results only, never input values.

Change note: red commit 4b877956f42678a6913d7942732cadddd48c2936 (the two refusal pins fail against the pre-repair module; the no-narrowing pin already passed) precedes this repair commit.
