# E11: prediction-contract step verification for tool-use loops

Label: an authored mechanism (actor-stated executable effect
predicates + pre-execution precondition gating + structured repair
feedback) measured against a ReAct-style (Yao et al. 2022,
arXiv:2210.03629) unverified loop baseline on an authored synthetic
tool-use world. Source pins: atlas-ai commit below (new files only),
shared-models stepverify via patch agi-stepverify-sm.patch (file
sha256 6a2e38f8e84b4af3736b36c3447379315c8fa5b7f81e4dfc8f7284fe93ec4de4,
applying against shared-models tip 97aae1f; the patch is not yet
committed upstream, so no upstream commit exists to pin - A39).
No e11 commit is on any remote (no push by builders): the shipped
patches agi-e11-revN.patch are the audited artifacts.
Python 3.10.12 and 3.12.15 (identical outputs). Nothing here is a novelty claim; see
PRIOR_ART.md. The actor is a SCRIPTED noisy planner, not a language
model - results say nothing directly about LLM tool use.

Setup: virtual file world (files hold integer text; tools list, read,
write, append, add, finish). 80 fixed seeded tasks in two splits: 20
dev (used while building) and 60 held-out (reported; untouched during
design). Three families: A aggregate-and-write (3-5 files), B
read-add-write-readback chain, C aggregate with same-named decoy
files. Both loop conditions run the same scripted actor with the same
error rates (wrong-path read 0.12, transcription slip on write 0.12,
non-integer add arg 0.08, premature finish 0.05) at paired seeds (11,
22, 33). Verified condition repairs fix a blocked/violated step with
probability 0.92; the baseline's retries after an error observation
fix it with 0.60; the equal-probability control (baseline-eq) reruns
the baseline with the fix probability raised to 0.92. Max 25 steps,
max 2 repairs per step. Grader is strict: exact final answer AND
exact output file content. Files: world.py, tasks.py, actor.py,
run.py, test_e11.py (9 sanity tests), sweep.py, rows_dev.jsonl,
rows_heldout.jsonl.

| Claim | Status |
|---|---|
| HEADLINE, equal-probability control (rev1): held-out (60 tasks x 3 seeds, 180 paired runs), verified 155/180 = 0.861 vs baseline-eq (retry fix probability 0.92) 135/180 = 0.750; paired diff +0.111, bootstrap 95% [+0.067, +0.161] | VERIFIED |
| Against the original baseline (retry fix 0.60): verified 0.861 vs 0.744; paired diff +0.117 [+0.072, +0.167] | VERIFIED |
| Equalizing the repair probability buys the baseline only +0.006 (0.744 -> 0.750); the gap is attributable to the step-verification signal (pre-execution blocking + effect checks), not to a repair-rate advantage | VERIFIED (within this world and actor) |
| Silent wrong answers (finished with a wrong answer, no error signal): verified 16 vs baseline 22 of 180 | VERIFIED |
| Per family (verified / baseline / baseline-eq): A 0.983 / 0.833 / 0.850; B 0.933 / 0.833 / 0.833; C 0.667 / 0.567 / 0.567 | VERIFIED |
| Mechanism audit: 83 pre-execution blocked calls and 22 effect-miss repairs in the verified condition vs 86 error observations in the baseline | VERIFIED |
| Dev split (20 x 3 = 60 runs) showed the same direction before held-out was run: verified 0.917 vs baseline 0.867 (+0.050 [0.000, +0.117]) and vs baseline-eq 0.883 (+0.033 [0.000, +0.083]) | VERIFIED |
| Sensitivity (held-out, post-fix): verified-minus-baseline gap is positive across the whole REPAIR_FIX x RETRY_FIX grid (min +0.100, max +0.128); not an artifact of the 0.92 repair rate | VERIFIED |
| The mechanism improves tool use BY A LANGUAGE MODEL | UNVERIFIED (scripted actor only) |
| The effect survives real tools, real latencies, non-integer data, or tasks where the correct plan is not known to the actor | UNVERIFIED |
| Comparison against a model-based verifier (ToolVerifier-style) or self-critique (CRITIC-style) | UNVERIFIED (not run; neither is free-tier reproducible here) |

## DISCLOSED CORRECTION (rev0 superseded)

rev0 shipped with a defect found by its own sensitivity sweep: a step
whose tool call EXECUTED but FAILED (tool error observation) advanced
the plan past that step, so the baseline's retry path was dead code
and the verified condition's effect checks never fired a repair.
rev0's gap was inflated by comparing against that crippled baseline.
rev0 numbers, kept for the record and labeled superseded:

- rev0 held-out: verified 0.750 vs (crippled) baseline 0.444,
  paired diff +0.306 [+0.244, +0.372] - SUPERSEDED by rev1
- rev0 dev: verified 0.883 vs 0.583 - SUPERSEDED
- rev0 per family: A 0.850/0.250, B 0.833/0.583, C 0.567/0.500 -
  SUPERSEDED
- rev0 silent wrong answers: verified 22 vs baseline 86 - SUPERSEDED

rev1 fix: the actor retries a failed step with the same descriptor
(effect: equal-observation repair); the plan advances only on
success. The verified condition's effect checks now fire (22
effect-miss repairs on held-out), the baseline's retry path is live,
and the equal-probability control isolates the verification signal
from the repair rate. The honest post-fix gap is +0.117 against the
original baseline and +0.111 against the equal-probability control -
about a third of the inflated rev0 figure.

Held-out-untouched statement: the 0.92 value used for baseline-eq is
not a fitted choice. REPAIR_FIX = 0.92 was fixed as an authored
parameter during dev, before the held-out split was generated or run;
the baseline-eq control simply adopts that pre-existing constant (per
the directing instruction to give the baseline the same repair/retry
probabilities as the verified condition). The only held-out numbers
seen before the baseline-eq run existed were (a) rev0's held-out run
(pre-fix, superseded above) and (b) the post-fix held-out re-run
without the control (verified 0.861 vs baseline 0.744). No held-out
number influenced the control's probability, the task set, the seeds,
or the grader.

Data statement: world, tasks, actor and error mix are all authored
synthetic for this experiment. The held-out split was generated with
a different seed than dev and was run once for rev0 and once for
rev1 (plus interpreter-robustness re-runs on 3.10 with identical
numbers). Repair probabilities (0.92 verified / 0.60 baseline /
0.92 baseline-eq) are authored parameters; the sensitivity grid and
the baseline-eq control quantify their influence. rows_dev.jsonl and
rows_heldout.jsonl carry every run (rev1 rows include the
baseline_eq condition; rows.jsonl from rev0 was removed to avoid a
stale duplicate).

Residual silent failures in the verified condition (16/180): decoy
reads in family C (verification cannot see wrong-target reads when
the decoy is a consistent world object), premature finishes (a
planning error, not a step error), and repairs that re-failed inside
the 2-repair budget.

Remaining: real tasks + real model; replication of the closest
prior art (StepTool) before any novelty claim - none is made here.

## rev16: two-lever sweep on the fresh slice H30-H59 - levers cut wasted catches 94-99% (per task), success still 0/30

VERDICT (pre-registered endpoints, prereg commit 91c32ddd pinned
before any run, parent-acked 2026-10-22 05:03 with additions): the
SUCCESS BAR IS NOT MET - A3 did not beat C0 success (0/30 vs 0/30; C0
finished zero tasks, so the success comparison is vacuous exactly as
the prereg pre-declared).  The FALSIFIER DOES NOT FIRE - its
wasted-catch arm carries it and BOTH guard arms strictly lowered total
wasted catches vs C0 (per task: A2 8 vs 144, A3 2 vs 144; strict: 7 and 0 vs 113).  Headline: on a
fresh task slice the two levers transfer - they convert rev13's
repeated contract catches into free guard blocks and near-zero waste -
but at Qwen2.5-1.5B nothing converts into task finishes; the rev13
capability-floor finding on the contract arm replicates on H30-H59.

Naming: pre-registered under the name "rev15"; renamed rev16 after
the wipe-recovery ship took rev15 (parent 12:26 ack).

Setup (pins identical to rev13): Qwen2.5-1.5B-Instruct Q4_K_M (GGUF
sha256 6a1a2eb6...), llama.cpp b11796, temp 0, seed 20261021,
max_tokens 48, ctx 1024, 2 threads, free CPU only; n=30 int held-out
tasks (HELD_OUT[30:60], ids H30-H59 - FRESH, not used in rev13) x 1
seed x 4 conditions; rows16_llm_*.jsonl (2655 logged generations),
done manifest, meta json, run-recorded driver log committed as
rows16_llm_runlog.txt.  Arms: C0 llm-ver (run._run_verified
byte-identical control), A1 llm-ver-none (prompt EXPECT:none
discipline for unpredictable observations; loop unchanged), A2
llm-ver-guard (repeat-guard: a call whose (tool, canonical args) was
already caught twice by the contract is blocked pre-execution, free,
repair-budget consuming, forced Violation('repeat_guard')), A3
llm-ver-none-guard (combined).  Pilot disclosure: two smoke pilots
(05:05-05:19 and 12:20-12:34, 2 tasks x 4 conditions each) validated
mechanics; their rows were CLEARED before the full sweep and are part
of no number.  Sweep window 12:34-14:22 IST (120 runs).

RESULTS (n=30 per condition; success/blocked/parse_failures
RUN-RECORDED in rows16_llm_runlog.txt; misses/blocked/parse_failures/
wasted/steps/exhaustion ROW-RECOMPUTED and asserted by
analysis_rev16.py, output committed as analysis_rev16.txt):

  condition          success  blocked  misses  wasted  wasted-strict  parse_fail
  C0 llm-ver         0/30     7        181     144     113            1
  A1 llm-ver-none    0/30     13       9       5       0              2
  A2 llm-ver-guard   0/30     49       43      8       7              1
  A3 llm-ver-none-g  0/30     16       6       2       0              2

  (wasted = catches that are immediate repetitions of an
  already-caught identical call WITHIN ONE TASK, the pre-registered
  endpoint; wasted-strict = consecutive ACCEPTED steps both caught,
  same call.  A2's 49 blocks = 42 guard blocks + 7 pre-gate; A3's 16
  = 3 + 13.  rev16b correction (A55 first audit): the rev16 ship
  concatenated misses across all 30 tasks before counting adjacent
  repeats, so 13 of C0's and 13 of A2's published numbers (157 and
  21) were cross-task artefacts; per task they are 144 and 8.  A55's
  independent recount script (e16chk.py) and this lane's
  analysis_rev16.py agree on every number on both definitions.)

Findings:
1. Lever (i) is the big effect: EXPECT:none discipline cut contract
   catches 181 -> 9 (95%) - direct confirmation of rev14's
   contract-design observation that `list` was an unfair prediction
   contract (the model cannot know generated filenames).  The
   remaining 9 are genuine wrong-value predictions.
2. Lever (ii) works as designed: the repeat-guard fired 42 guard
   blocks - free pre-execution blocks of already-twice-caught calls
   (as a count of prevented repetitions this is an UPPER BOUND: a
   blocked call might not have repeated again - A59, rev16d).  A2:
   misses 43, of which 8 wasted per task, 7 strict, vs C0's
   144 / 113; combined (A3) is the floor: 6 misses, 2 wasted,
   3 guard blocks.
3. Paired per-task (pre-declared comparison): A2 fewer misses than C0
   on 13/30 tasks, more on 0; A1 fewer on 21/30, more on 1 (H31);
   A3 fewer on 21/30, more on 1 (H31).  Paired per-task wasted
   (A59, rev16d): A2 lower on 13/30 tasks, equal 17, higher 0; A1
   and A3 lower on 13/30, equal 16, HIGHER on 1 (H51: C0 wasted 0,
   arm wasted 1 - the same caught call repeated twice).  The 13/0
   pattern holds for A2 only.
3b. Early termination (A55 finding, rev16b; A59 label fix, rev16c):
   the guard's blocks consume the per-step repair budget, so 15/30
   A2 runs ended EARLY on REPAIR-BUDGET exhaustion - repair
   exhaustion only, i.e. runs ending below the 25-step cap (A2
   accepted steps 467 vs C0 731; A3 4/30 early, 681 steps; A1 3/30,
   691; C0 1/30, 731).  The production `exhausted` flag also fires
   at the 25-step cap itself and is true for 30/30 runs in every
   arm; the counts here are repair exhaustion only.  Part of A2's
   catch reduction is runs stopping sooner, not only adaptation -
   A2's per-task wasted (8) is measured on truncated trajectories.
   A1/A3's reductions are not early-stop effects (3-4 early runs,
   near-full step counts).
4. The C-family pathology reproduces on the fresh slice under C0:
   the same 22-catch 18-19x terminal chains on 5 C tasks (H32, H41,
   H47, H50, H59; C0 chains {1:41,2:8,3:4,4:5,18:3,19:2}, chain ends
   39 adapted / 23 corrected / 1 terminal).  Under A3 those 5 tasks
   drop to 0-2 misses each.
5. Registered tradeoff (prereg): the guard cannot distinguish a
   repeat carrying a CORRECTED contract; C0 had 23 such corrected
   chain ends that the guard arms forgo - the known cost, visible in
   A2's remaining 43 catches and 42 guard blocks.
6. No finishes anywhere: every arm 0/30, silent_fail 0; verified
   runs still die at MAX_STEPS.  The levers fix the waste the
   contract surfaces; they do not supply the planning capability the
   1.5B lacks.  A model above the finish threshold remains the
   deciding experiment (rev13 section, unchanged).
7. Stated limits (rev16b, A55): the four arms were not necessarily
   run within one llama-server lifetime - the rev15 cross-lifetime
   nondeterminism limit applies to every arm-to-arm comparison.  A1's
   catch drop is a PROMPT effect: the discipline tells the model to
   write EXPECT: none when it cannot predict the observation, so it
   makes fewer checkable predictions and the contract has fewer
   chances to fire - not direct evidence of better calls.

Tests: 55/55 on Python 3.10.12 and 3.12.15 (normal and -W error):
TestResultsDocIntact extended to require this heading; new offline
test pinning analysis_rev16.compute() to the registered per-arm
totals.

## rev15: wipe recovery - cumulative patch rebuilt on RERUN data (changed numbers table)

What happened: on 2026-10-22 ~09:05 IST both this lane's workspace and
the parent's /downloads were wiped, destroying every local copy of the
shipped e11 patches (rev0..rev14 cumulative a3dfd401... and earlier)
and all rev12/rev13 probe rows.  No auditor retained a copy
(A53/A54/A56/A58/A59 confirmed wiped; A51 unreachable).  The patches
were never pushed (no-push rule), so the public repo does not hold
them either.  The code and documents were rebuilt from this
lane's transcript (verified: the transcript replay of llm_sweep.py
BEFORE the A56 docstring edits hashes to the registered rev13 blob
8b28cb1f...; the SHIPPED llm_sweep.py carries the A56 docstring edits
on top of that reconstruction and hashes to blob 20939b2a...;
actor_llm.py body identical to the rev12/13 body modulo the A56
docstring edit; rows15_llm_meta.json and rows15_llm_done.txt
reproduce their registered blobs 9f7ce5b3... and 4be4c4d5...
exactly).  The probe ROW DATA could not be reproduced
byte-exact and was REGENERATED by rerun (same code, same GGUFs
sha-verified, same llama.cpp b11796 binary, same flags, same
generation parameters).

STATED LIMIT - llama.cpp cross-lifetime nondeterminism: greedy
decoding (temperature 0, fixed seed) is deterministic only within one
server lifetime.  Across server processes, slot/KV-cache prefix state
shifts logits by tiny amounts and argmax flips at different steps.
Measured on the rev13 rerun (n=30 x 3 conditions, identical setup):
the CONTRACT arm is comparatively stable (effect_misses 183 -> 182,
blocked 12 -> 12, parse_failures 6 -> 6) while the UNVERIFIED arms
swing widely (llm-ver-noexp blocked 73 -> 116, parse_failures 0 ->
77; llm-base error_obs 237 -> 681, parse_failures 0 -> 677).  The
C-family pathology reproduced task-for-task (the same 4 tasks H02,
H11, H17, H26 with 22 catches each and 18-long terminal chains).
Every number below is computed from the rerun rows; the pre-registered
headlines are UNCHANGED (rev12 kill criterion still not fired; rev13
falsifier still fires, 0/30 everywhere, silent_fail 0).

Two further audit limits of this squashed ship: (i) the
prereg-before-run ORDER for the pre-registered sweeps is not checkable
from a squashed commit - prereg text and run results land in one
commit; the order exists only in this lane's transcript record.  (ii)
The probe rows in this ship were REGENERATED by rerun after the wipe
and are not the original logged rows (see the nondeterminism limit
above).

CHANGED NUMBERS vs the rev14 ship (old -> new):

  rev13 llm-base error_obs        237 -> 681
  rev13 llm-base parse_failures   0   -> 677
  rev13 llm-ver effect_misses     183 -> 182
  rev13 llm-ver-noexp blocked     73  -> 116
  rev13 llm-ver-noexp parse_fail  0   -> 77
  rev13 total pre-gate blocks     85  -> 128
  rev14 catches total             183 -> 182
  rev14 catches on `list`         173 -> 172 (94.5% both)
  rev14 chain length dist         {1:49,2:7,3:9,4:4,5:1,18:4} -> {1:49,2:7,3:10,4:3,5:1,18:4}
  rev14 within-chain repeats      109 -> 108
  rev14 chain-end adapt/repeat/terminal  41/25/8 -> 42/25/7
  rev14 behavioral response       66/74 (89%) -> 67/74 (90.5%)
  rev14 H00 llm-ver-noexp closure 26 = 25+1 -> 8 = 3+5
  rev12 (0.5B): NO changed numbers - the rerun reproduced every
  registered aggregate exactly (tallies 106/0/0, 3/0/3, 32/0/0; 548
  generations; per-task base error observations
  (12,16,7,10,17,5,8,13,7,11); H09's 3 format failures).

The rev13 and rev14 sections below carry the rerun values; this table
is the delta against the wiped rev14 ship (patch sha256 a3dfd401...,
tree 0708eb80... - those artifacts are unrecoverable and are preserved
here only as hashes).

Naming note: the two-lever sweep pre-registered at 05:03 under the
name "rev15" is unaffected by this ship and will ship under its own
revision number (pending parent renumbering); this rev15 is the wipe
recovery ship only.

## rev14: catch-quality audit of the contract catches (analysis-only, POST-HOC) + A56 fixes

(Numbers in this section and in rev13 are the rev15 RERUN values; the
wiped originals are in the changed-numbers table above.)


No new measurement, no new runs, no compute.  Two parts.

PART 1 - the audit (catch_audit.py, committed; its totals assertion is
pinned by TestLLMActorOffline.test_catch_audit_reproduces_registered_
totals).  A deterministic replay of the COMMITTED rev13 llm-ver rows
(rows15_llm_ver.jsonl - every raw generation logged) back through the
production parser, verifier and loop semantics (actor_llm.parse_output,
StepVerifier, run_verified_loop at MAX_STEPS=25, MAX_REPAIRS=2).  The
replay reproduces the registered totals EXACTLY (182 effect_misses,
12 pre-gate blocks on the rerun rows; the rev13 rows pinned 183),
pinning the audit to the shipped rows.  EVERYTHING in part 1 is POST-HOC: none of it was pre-registered;
it audits rev13's subordinate counts and changes no registered number.
Correction: this lane's preliminary report quoted "48 of 49 single
catches adapt" - that mis-grouped chain ends; the verified chain-level
accounting below replaces it.

Step semantics (auditor question, resolved): the jsonl 'step' field is
the index into the actor's raw call log (llm_sweep.py logs EVERY call:
accepted, blocked re-asks, parse failures), NOT the budget counter.
The budget bounds ACCEPTED steps only (stepverify.py:
`while len(history) < max_steps:`; a blocked call `continue`s without
entering history - blocks are free under the registered
accepted-history accounting).  Replay closures: H00 llm-ver 29 logged
calls = 25 accepted + 4 blocked; H00 llm-ver-noexp 8 = 3 + 5.

Findings (POST-HOC):
1. All 182 catches are actor-prediction contract failures; ZERO
   spec-floor violations.  The model never broke a tool's real
   contract; it misstated its own predictions.
2. Concentration: 172/182 (94.5%) are `list` calls - the model
   predicts a directory listing containing generated files it cannot
   know (e.g. data0_1.txt).  Only 34 DISTINCT (task, tool, args)
   calls underlie all 182 catches: 74 catch chains (maximal runs of
   consecutive caught repetitions of one call), length distribution
   {1: 49, 2: 7, 3: 10, 4: 3, 5: 1, 18: 4}; 108 of the 182 catches are
   within-chain repeats caught again.
3. The feedback IS used in most situations: of the 74 chain ends, 42
   are followed by an adapted (different) call and 25 by the same
   call retried with a CORRECTED contract (executes clean) - 67/74
   (90.5%) show a behavioral response to the violation; the remaining
   7 chain ends are terminal (budget exhausted).
4. The pathology: 4 tasks (H02, H11, H17, H26) collapse into chains
   of the SAME caught `list` call repeated 18x with zero adaptation
   (4 chains = 72 catches = 40% of all catches, all 4 terminal),
   each burning the 25-step budget to exhaustion.  These tasks die by
   budget exhaustion in unproductive repeat loops - part of why rev13
   success is 0/30 even though the channel fires.
5. Contract-design observation: `list` is an unfair observation
   contract for a model that cannot know generated filenames (the
   scripted actor used EXPECT: none for readback-type calls).

Consequences (parent direction 2026-10-22 05:00): the follow-on
sweep (announced as 'rev15' in the 05:03 prereg, to be renumbered -
see the rev15 wipe-recovery section above) pre-registers two levers as separate arms plus the combined arm - (i) EXPECT:none
discipline for unpredictable observations, (ii) a repeat-guard
(identical call caught twice -> forced 'do something different'
violation), and (i+ii) combined - on the FRESH slice HELD_OUT[30:60]
(H30-H59, not used in rev13), falsifier and success bar written before
any run, free CPU only, every arm shipped even if all 0/30.

PART 2 - A56 audit fixes (rev13 first audit: VERIFIED, all counters
replayed from raw rows): (a) rev13's "FALSIFIER (parent's, verbatim)"
attribution corrected - the falsifier wording is this lane's (rev12
pattern); the parent's directive and the prereg-before-numbers
discipline stand.  (b) actor_llm.py and llm_sweep.py docstrings no
longer carry rev12-specific parameters (0.5B, HELD_OUT[:10],
max_tokens 80): they describe the mechanism and point at the run's
meta.json (rev12 rows_llm_meta.json; rev13 rows15_llm_meta.json),
which owns the pinned model, runtime, generation and harness
parameters.

Tests: 51/51 on Python 3.10.12 and 3.12.15 (TestResultsDocIntact
extended to require the rev14 heading; new offline regression test
pinning the audit replay to the registered totals).

## rev13: 1.5B probe - the pre-registered falsifier FIRES (Qwen2.5-1.5B)

Parent-directed (2026-10-21 22:43) and pre-registered (22:43): does the
contract channel fire and catch when the model finishes some tasks?
FALSIFIER (wording authored by this lane in the rev12 pattern - the
parent's directive and the prereg-before-numbers discipline stand):
effect_misses stay 0 across all finished
tasks, OR ver does not beat base in success at n>=30 tasks.

VERDICT: THE FALSIFIER FIRES on its second arm.  Success is 0/30 in ALL
THREE conditions, so ver does not beat base.  Reported as the headline:
at Qwen2.5-1.5B the mechanism shows NO success benefit at n=30.  In
the two CONTRACT arms the model is below the capability floor to
finish even one of these multi-step tasks (no verified run, with or
without expectations, reached an accepted finish; silent_fail 0
everywhere).  The base arm's 0/30 is dominated by format failure -
677 of its 750 generations failed to parse - so no capability-floor
claim is made for the base arm.  The falsifier fires on
its SECOND arm ONLY: the first arm did not fire - effect_misses did
NOT stay 0 (182 prediction-contract catches exist on the rerun
rows).

Setup: identical world/loops/grader/MAX_STEPS=25/MAX_REPAIRS=2 as the
registered measurement; Qwen2.5-1.5B-Instruct Q4_K_M (GGUF sha256
6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e,
public weights, free, CPU-only, ~1.1GB - the largest model that fits
this box's 2GB RAM; 3B does not fit), llama.cpp b11796, temp 0, seed
20261021, max_tokens 48, ctx 1024, 2 threads; n=30 int held-out tasks
(HELD_OUT[:30], ids H00-H29) x 1 seed x 3 conditions; rows checkpointed
per run (rows15_llm_*.jsonl, 90 runs, every raw generation logged;
rows15_llm_done.txt is the resume manifest).  One additional disclosed
parser leniency vs rev12: a bare '<tool> <args>' line naming a known
tool is accepted (logged leniency=no_tool_prefix) after the 1.5B dropped
the TOOL: prefix in 23/25 pilot generations; the pilot rows were cleared
and the sweep rerun from scratch before any numbers were locked.

RESULTS (counts, n=30 per condition):

  condition       success  blocked  effect_misses  error_obs  parse_fail
  llm-base        0/30     0        0              681        677
  llm-ver         0/30     12       182            0          6
  llm-ver-noexp   0/30     116      0              0          77

Provenance of these counts: success, error_obs, blocked and
parse_failures are RUN-RECORDED (the rows log raw calls, not
outcomes); the per-run outcomes behind them are preserved in the
committed rows15_llm_runlog.txt (90 per-run lines + summary, copied
from the sweep driver's stdout).  effect_misses and blocked on the
two verified arms are additionally ROW-RECOMPUTABLE from the
committed rows via catch_audit.py (totals pinned by
TestLLMActorOffline).  The 128 total pre-gate blocks quoted below
(12 + 116) is run-recorded on the same basis.  For rev12's 0.5B
numbers the equivalents are rows_llm_runlog.txt (30 runs + summary)
and recompute_rev12.py (committed; recomputes every registered rev12
aggregate from rows_llm_*.jsonl and asserts them - per-task base
error observations, ver 3 blocks + 3 parse failures, ver-noexp 32
blocks, 0 effect misses, 548 generations). (BELOW the falsifier headline; n=30, 1 seed,
no CIs, one model):
- BOTH verifier channels now provably fire on real model outputs:
  128 pre-gate blocks (12 with the contract, 116 without) and - new at
  this scale - 182 prediction-contract catches (vs 0 at 0.5B): the
  1.5B
  states concrete wrong expectations ('observation = -135' on a list
  call, wrong sums) and the contract catches every one, converting them
  to repair feedback at zero step cost, while the baseline paid 681
  error observations for the same class of behavior.
- The rev12 regularization pattern replicates: requiring the EXPECT
  line cut pre-gate blocks 116 -> 12 (the model makes fewer invalid
  calls when it must state expectations).  Behavioral observation only.
- C-family verified runs show the largest contract activity (22 misses
  on H02/H11/H17/H26): wrong-value predictions on reads/adds, caught.
- The model still cannot FINISH: verified runs end at MAX_STEPS with
  the model re-reading or repeating caught mistakes; the repairs are
  delivered (violations visible in the raw log) but a 1.5B temp-0 model
  does not reliably act on them.  This is a capability observation
  about the model, not a mechanism claim.
- Format failures concentrate in the unverified arms on this rerun:
  760 in ~2000 generations (677 base, 77 ver-noexp, 6 with the
  contract).

What would decide the question the falsifier leaves open: a model above
the finish threshold (some condition completes tasks at all).  On this
box that needs a smaller-quant or smaller-ctx 3B, or free hosted
inference with the user's keys - neither assumed here.

## rev12: REAL-MODEL validity probe (Qwen2.5-0.5B, pre-registered)

The strongest remaining attack on e11 was the scripted-actor label.
rev12 replaces the ScriptedActor with a REAL small language model and
asks the pre-registered kill question: does the mechanism catch real
model errors, or does it only catch errors it authored?

Honest label: the actor is now a real model; the world, tools, loops,
pre-gate, floor, grader, held-out tasks, MAX_STEPS=25 and MAX_REPAIRS=2
are UNCHANGED from the registered scripted measurement.  This is a
VALIDITY PROBE (counts per channel, n=10 tasks x 1 seed, no CIs), not a
new headline measurement.  Pre-registered to parent BEFORE any numbers
(message 2026-10-21 20:43 IST) and accepted with two additions, both
executed: (1) a no-expectation control (llm-ver-noexp: same model, same
verified loop, EXPECT line stripped) isolating the prediction-contract
channel from the pre-gate; (2) every raw model output logged per step
(rows_llm_*.jsonl, 548 rows) with format failures counted separately
from verifier blocks.

Runtime (all pinned in rows_llm_meta.json): Qwen2.5-0.5B-Instruct GGUF
Q4_K_M (sha256 74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db,
public weights, no API keys, free tier) via llama.cpp llama-server
build b11796 (tarball sha256 70b856d40577f1cf66120f894b2674398175efbae7d9153566872c4b3c1b3d32);
temperature 0, seed 20261021, max_tokens 48, ctx 1024, 2 threads.
The model emits one TOOL line plus (llm-ver only) one EXPECT line; the
EXPECT line is COMPILED into Step.expect ('observation = V' -> the
call's observation must equal V, mirroring the scripted add/concat
contracts; '<path> = V' -> after-state file check, mirroring the
scripted write/scale contracts; 'none' -> no contract).  Disclosed
parser leniencies: the FIRST TOOL line of a multi-line dump is taken;
JSON-style args accepted; a bare EXPECT value means 'observation =
<value>'; surrounding quotes stripped.  Format failures (no TOOL line,
missing/uncompilable EXPECT) return Step('__format_failure__'): the
verified pre-gate blocks them (unknown_tool, counted in `blocked` -
disclosed accounting), the baseline executes them into an ERROR
observation.  Harness limits (harness-only, disclosed): prompt shows
the last 6 history records; llm_sweep wraps world.execute so a
non-WorldError from a malformed call (e.g. KeyError on a missing arg -
the scripted actor never produced one) becomes a WorldError, the
real-API 400 semantics the baseline already records as an error
observation.  Loops themselves unchanged.

Tasks: HELD_OUT[:10] (ids H00-H09, families A/B/C), seed 0 paired
across the three conditions (llm-base / llm-ver / llm-ver-noexp).

RESULTS (counts; the model solved 0/10 tasks in EVERY condition, so
this measures error handling, not task success):

  condition       success  blocked  effect_misses  error_obs  parse_fail
  llm-base        0/10     0        0              106        0
  llm-ver         0/10     3        0              0          3
  llm-ver-noexp   0/10     32       0              0          0

KILL CRITERION (pre-registered): the verified conditions catch NOTHING
the baseline does not also catch - blocked == 0 AND effect_misses == 0
across all verified runs.  NOT FIRED: the pre-gate blocked 35 real
model calls at zero step cost (3 with the contract, 32 without); the
same class of malformed/invalid calls cost the baseline 106 paid error
observations (12, 16, 7, 10, 17, 5, 8, 13, 7, 11 per task).  The
mechanism transfers to a real (0.5B) actor at the pre-gate channel.

Readings per channel:
- PRE-GATE: transfers.  Every llm-ver-noexp run ended by repair-cap
  exhaustion after 3-4 blocked calls (precondition/schema), never by
  MAX_STEPS; the baseline burned 25 steps on the same tasks with 5-17
  error observations each.
- PREDICTION CONTRACT (EXPECT): UNEXERCISED as a catch - 0 effect
  misses in llm-ver, because with the contract demanded the model
  almost always predicted 'none' or safe values and made far fewer
  invalid calls (3 blocks vs 32 without the contract).  The no-expect
  control isolates this: stating expectations changed the model's call
  BEHAVIOR (fewer invalid attempts), an emergent regularization signal
  we report as behavioral observation only (n=10, no CIs, single
  model).  H09 llm-ver: 3 format failures (the only ones in 30 runs)
  blocked by the pre-gate.
- FORMATTING was NOT the dominant failure mode (parent's addition-2
  concern): 3 parse failures in 548 generations after the disclosed
  few-shot prompt; the raw log shows the dominant real failure is
  semantic looping (re-reading the same files) and invalid calls.
- SILENT failures: 0 everywhere (the model never finished, so never
  produced a wrong answer; success 0/10 is honest incapability of the
  0.5B model on multi-step tasks, not a mechanism result).

Limitations, stated plainly: one small model (0.5B), one seed, 10
tasks, no CIs; the contract channel's catch behavior is unexercised
(the scripted worlds remain the only measurement of it); results do
not speak to larger models.  A natural rev13 is a model strong enough
to finish tasks, where the contract channel would actually fire.

## rev11: the ALIAS world - structural errors and the stated ceiling

Motivated by rev10's lesson (rate faults are trainable away): do
errors that are WRONG PLANS, not noisy executions, change the
picture?  Alias tasks declare an explicit file pairing; the actor
carries a heuristic bias (P_ALIAS init 0.50, a 7th trainable logit;
one draw at plan time).  SA 'habit' bias reads x.txt/y.txt which
never exist (precondition block / error observation); SB
'lexicographic' bias reads two existing files (self-consistent
wrong plan).  All parameters, split sizes (10+10 dev / 30+30
held-out, generator seeds 7/8), the shuffled-label control and the
outcome criteria were PRE-REGISTERED to parent before any numbers
(parent messages 2026-10-21; alias_sweep.py header quotes them).
Dev-trained 7-knob StepTool policy: alias 0.50 -> 0.0875 (training
still turns the structural RATE down - disclosed; the residual is
what verification faces).

Held-out (success, n=90 per sub-family per condition; counts pinned
in test_e11.py):

| sub | base | steptool | verified | steptool+ver | base-shuf | ver-shuf |
|---|---|---|---|---|---|---|
| SA | 0.578 | 0.889 | 0.756 | 0.944 | 0.378 | 0.422 |
| SB | 0.322 | 0.844 | 0.422 | 0.856 | 0.322 | 0.422 |

Conditioned on the alias draw (reconstructed per task+seed; pinned):

| sub | draw | base | steptool | verified | steptool+ver |
|---|---|---|---|---|---|
| SA | fired | 0.400 (18/45) | 0.714 (5/7) | 0.667 (30/45) | 0.857 (6/7) |
| SA | not fired | 0.756 | 0.904 | 0.844 | 0.952 |
| SB | fired | 0.000 (0/46) | 0.000 (0/7) | 0.022 (1/46) | 0.000 (0/7) |
| SB | not fired | 0.659 | 0.916 | 0.841 | 0.928 |

Findings:

1. FOR-VERIFICATION criterion (pre-registered) MET on SA:
   steptool+ver - steptool = +0.056 [+0.011, +0.111]; conditioned on
   alias-fired runs the pre-gate recovery advantage is +0.267
   (0.667 vs 0.400): blocked off-statement reads are retried toward
   the statement at ZERO step cost (free accounting) while the
   baseline pays an error observation per attempt.  Structural plan
   errors that violate preconditions are exactly the pre-gate's
   home channel.
2. CEILING CONFIRMED (pre-registered: SB fired gaps must be ~0,
   else the rev9 channel decomposition is wrong): on SB alias-fired
   runs every condition scores 0.000-0.022 (max pairwise gap
   0.022).  The one verified success (HA44, seed 33) was TRACED:
   an ordinary wrong-path draw on the biased read landed on a
   nonexistent path, the pre-gate blocked it, and the
   statement-grounded repair retargeted the read to the DECLARED
   south.txt - the run recovered through an unrelated fault's
   repair path, NOT by detecting the alias.  A self-consistent
   wrong plan is invisible to the floor, to prediction contracts,
   and to preconditions.  The
   apparent verified-base +0.100 on SB comes ENTIRELY from
   not-fired runs (ordinary rate faults), not from catching
   aliases.  Stated, not hidden.
3. SHUFFLED-LABEL CONTROL (parent's addition) is decisive on SA:
   ver-shuf - ver = -0.333 [-0.433, -0.244], base-shuf - base =
   -0.200 [-0.289, -0.122].  Repairing toward an arbitrary
   EXISTING pair is worse than no targeted repair at all: it
   converts recoverable error signals into locked-in wrong answers.
   The SA recovery is statement-grounded, not a retry artifact.
   On SB the control is exactly 0.000 (reads succeed either way,
   no repair is triggered) - as expected.
4. Training still turns the structural RATE down (alias 0.50 ->
   0.0875 on dev), so steptool beats base on both sub-families
   (+0.311/+0.522).  rev10's lesson stands: verification's
   measured value is on the residual the policy does not fix -
   and on SA that residual benefits from the pre-gate
   (+0.056 stacked, positive CI); on SB nothing helps and we say
   so.

## rev10: StepTool replication (Yu et al. 2024) - the pre-registered criterion AGAINST the verifier fired

Nearest published baseline mechanism reimplemented in the e11 world
on equal terms (steptool_sweep.py): StepTool's step-grained reward
shaping (r_t = 0.5*SuccCalling + 0.5*Contribution/5 for t<T, r_T =
IsSolved) + policy-gradient optimization over the actor's six fault
logits (REINFORCE, exact Bernoulli score function, gamma=1,
constant-return baseline = disclosed simplification of GAE). Reward
acquisition is rule-based/world-oracle: the paper (arXiv v4,
sec 4.1.2) allows flexible reward assignment "through various
approaches, including rule-based systems, human annotations, and
advanced language models such as GPT-4" and states "the specific
reward acquisition method is not the focus of our framework and
can be adapted to different settings as needed" (verbatim, v4;
A33 confirmed and WITHDREW the earlier nit - the sentence is
absent from v3, which is why the first check missed it; no
appendix E exists in v1 (appendices A, C) or v4).  RULES-ONLY
here is OUR SUBSTITUTION for their rules+GPT-4 hybrid (annotation
prompt in their Figure 3; its GPT-4 labels are the training-time
equivalent of our oracle). One policy per world trained on that
world's dev split (20 tasks, 400 epochs x 16, lr 0.05, fixed on dev
only); held-out untouched until measurement; n=180 per condition,
paired seeds, MAX_STEPS=25.

Held-out (success, n=180; counts pinned in test_e11.py):

| world | base | final-only | steptool | verified | steptool+ver |
|---|---|---|---|---|---|
| int | 0.744 | 0.911 | 0.967 | 0.861 | 0.972 |
| text | 0.767 | 0.878 | 0.911 | 0.894 | 0.939 |
| mut | 0.578 | 0.867 | 0.939 | 0.956 | 0.989 |

Findings:

1. PRE-REGISTERED CRITERION AGAINST THE VERIFIER FIRED. Stated
   before the numbers were locked: "counts against the verifier:
   StepTool-trained >= verified on held-out (CI of
   verified-minus-steptool includes 0)." Result: int -0.106
   [-0.156, -0.061] (steptool significantly ABOVE verified),
   text -0.017 [-0.061, +0.022] (tie), mut +0.017 [-0.028, +0.056]
   (tie). On all three worlds a StepTool-trained actor matches or
   beats inference-time verification alone. THIS IS THE HEADLINE.
   The registered rev1-rev9a claims are unaffected: they compare
   verified vs UNTRAINED baselines and remain byte-exact.
2. The paper's central claim REPLICATES: step-grained beats
   final-only training on all three worlds: int +0.056
   [+0.028, +0.089], text +0.033 [+0.011, +0.061], mut +0.072
   [+0.033, +0.117].  (rev11a, A33: final-only is the paper's
   PPO (Final Reward) BASELINE, not an ablation; it is equal in
   reward structure to the paper's RQ4 "w/o Step-grained Reward"
   variant.)
3. Verification and training are COMPLEMENTARY, not substitutes:
   steptool+verified - verified is positive on all three worlds
   (int +0.111 [+0.067, +0.161], text +0.044 [+0.011, +0.083],
   mut +0.033 [+0.000, +0.072]) - verification adds on top of a
   trained actor, and it needs no training access, no reward
   labels, and no gradient. Mechanism-add vs untrained base:
   steptool +0.223/+0.144/+0.361, verified +0.117/+0.128/+0.378
   (int/text/mut).
4. Honest-label caveats: (a) in this scripted world "learning" =
   turning down the six authored fault probabilities (trained
   values printed by the sweep; e.g. int slip 0.12->0.024, mut
   bad_factor 0.10->0.005); a real LLM backbone learns tool
   selection and arguments, so this says nothing directly about
   LLM tool use. (b) The dev mean-total-reward curve is NOT a
   convergence signal here: shorter successful trajectories
   collect less shaped reward mass (the paper's per-state value
   baseline centers this; our constant baseline does not). Dev
   success is the reported convergence evidence: int 0.867->0.983,
   text 0.667->0.883, mut 0.667->0.917. (c) mut wrong_path
   trained UP to 0.133: wrong-path reads in the mut world hit no
   decoy, cost one retry step, and REINFORCE tolerated the rate;
   disclosed, not tuned away.
5. A33 clauses (from the rev9a FINAL): (a) the flaky world's
   'silent observation' property is BY CONSTRUCTION and not
   load-bearing for its numbers - the scripted baseline never
   reads non-error observations, so the +0.122 floor contribution
   does not depend on observation opacity. (b) rev9's
   falsification criteria were written AFTER a preview of the
   flaky numbers on rev7-era code (the pre-rev8 WIP commit); the
   sweep was re-run post-rev8 byte-identical before shipping, and
   the criteria were messaged before the post-rev8 numbers were
   seen, but the preview predates the pre-registration. Stated.

6. (rev11a, A33 disclosures) (a) The pre-registered design message
   named MAX_STEPS=11; the executed measurement used the registered
   MAX_STEPS=25.  The budget sweep shows budgets 18 and 25 are
   identical on every world, so the discrepancy is inert at the
   plateau; it is disclosed, not smoothed over.  (b) The design
   message named alpha=1.0 under a /5 contribution normalization;
   the executed reward is r_t = 0.5*SuccCalling + 0.5*(Con/5),
   i.e. alpha=0.5 under that normalization (both components in
   [0,1], summed 50/50).  (c) The P_LO=0.005 probability clip was
   ACTIVE for mut bad_factor, which trained to the floor; the
   reported 0.005 is the clip, not an unconstrained optimum.

## rev9: the spec effect floor's measured contribution - flaky execution world

A39's mutant showed removing the spec effect floor changes nothing
on the non-flaky corpus, and rev3's p_drop=1.0 cell shows floor-ONLY
verification equals baseline-eq exactly: the floor checks
obs/args/state SELF-CONSISTENCY, and every authored error in the
three registered worlds is an INTENT error (a slipped write's args
ARE the slipped text). rev9 gives the floor its home channel:
EXEC_FAULT_P = 0.12 makes the WORLD silently truncate a stored
write/append (last character dropped). The fault is silent in the
observation text for every condition ('wrote N chars' truthfully
describes the args); fault streams are seeded per task+seed so
conditions stay paired; the baseline receives byte-identical
observations to a no-fault run (the A39 non-reading caveat applies:
a real ReAct agent could read the file back and notice).

PRE-REGISTERED FALSIFICATION (stated to parent before the numbers
were locked): results counting against the floor would be (a)
floor-only minus baseline-eq not positive (CI includes 0) - floor
adds nothing even in its home channel; (b) floor-only matches or
beats preds-only - the actor predicates add nothing here. Neither
fired:

### Flaky held-out (int tasks, 60 x 3 seeds = 180 runs/condition)

- baseline 0.633; baseline-eq 0.639; floor-only 0.761; preds-only
  0.861; full verified 0.861
- STRICT floor-only - baseline-eq: +0.122 [+0.078, +0.172] - the
  floor's measured contribution, positive, criterion (a) does NOT
  falsify it
- preds-only - baseline-eq: +0.222 [+0.167, +0.283]
- floor-only - preds-only: -0.100 [-0.144, -0.061] - criterion (b)
  does NOT fire either: actor predicates strictly dominate the floor
  (they catch the execution faults AND the intent faults), while the
  floor alone cannot see intent
- floor effect-miss repairs 28 | predicate effect-miss repairs 49

### Flaky dev (n=60), seen first

- baseline 0.833 / eq 0.850 / floor-only 0.883 / preds-only 0.917 /
  verified 0.917; floor - eq +0.033 [0.000, +0.083] (borderline at
  dev scale; held-out confirms)

Channel decomposition, final form: INTENT faults are caught only by
actor-stated predictions (floor and schema are blind); EXECUTION
faults are caught by either the floor or a stated prediction, and
the floor is the only channel that catches them when the actor
states nothing (+0.122). On intent-only corpora the floor's
contribution is exactly 0 (measured, not assumed). Sanity tests pin:
p=0 reproduces the registered numbers and floor-stripped ==
floor-only at p=0; p=1.0 yields floor effect-misses with no
predicates; the fault channel adds zero error observations for the
baseline.

## rev8: step-accounting property and the like-for-like budget grid

A33/A39 on rev7 (PARTIAL, stricter wins): the verified loop's
pre-gate blocks cost ZERO steps (run_verified_loop budgets on
accepted history), while the baseline and schema loops pay one step
per rejection - so rev7's finding 4 was wrong as stated and the mut
+0.194-at-14 spike was an accounting artifact.

Design property, stated: a blocked call never executes, so the
free-block convention does not bill the actor for the verifier's
catch. Justification: the check replaces a failed execution the
actor would otherwise have paid for. Because the convention is
arguable, rev8 ALSO equalizes: _run_verified_paid (blocks and
effect violations consume budget) and baseline-schema free_rejects
(rejections cost nothing), and the whole budget sweep is re-derived
under both accountings (budget_sweep.py, post-hoc).

| budget | world | ver-free | ver-paid | base | base-eq | sch-free | sch-paid |
|---|---|---|---|---|---|---|---|
| 6 | int | 0.411 | 0.322 | 0.294 | 0.294 | 0.311 | 0.294 |
| 10 | int | 0.778 | 0.739 | 0.650 | 0.656 | 0.650 | 0.650 |
| 14 | int | 0.861 | 0.861 | 0.744 | 0.750 | 0.744 | 0.744 |
| 25 | int | 0.861 | 0.861 | 0.744 | 0.750 | 0.744 | 0.744 |
| 6 | text | 0.467 | 0.411 | 0.394 | 0.394 | 0.394 | 0.394 |
| 10 | text | 0.761 | 0.761 | 0.678 | 0.689 | 0.678 | 0.678 |
| 14 | text | 0.894 | 0.883 | 0.767 | 0.789 | 0.767 | 0.767 |
| 25 | text | 0.894 | 0.894 | 0.767 | 0.789 | 0.767 | 0.767 |
| 6 | mut | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | mut | 0.406 | 0.183 | 0.183 | 0.183 | 0.278 | 0.183 |
| 14 | mut | 0.956 | 0.828 | 0.539 | 0.539 | 0.844 | 0.761 |
| 18 | mut | 0.956 | 0.956 | 0.578 | 0.572 | 0.872 | 0.872 |
| 25 | mut | 0.956 | 0.956 | 0.578 | 0.572 | 0.872 | 0.872 |

(Budget 18 omitted for int/text: identical to 25, as before.)

Findings:

1. A33's mut@14 2x2 reproduces exactly: verified free 0.956 / paid
   0.828; schema free 0.844 / paid 0.761. Like-for-like residual at
   14: +0.111 both-free, +0.067 both-paid - bracketing the plateau
   +0.083. The +0.194 spike is withdrawn (rev7 finding 3 marked).
2. Paid-verified@14 (0.828) nearly ties free-schema@14 (0.844):
   part of the tight-budget mut advantage rests on the free-block
   convention. Disclosed, not hidden: at the registered budget (25)
   the convention changes NOTHING in any world (paid == free: the
   budget never binds once repairs fit).
3. All registered headlines are accounting-invariant: at budget 25
   every like-for-like comparison equals the rev5/rev6 numbers.
   (rev9a, A33 wording fix: the int/text residuals are invariant
   within +-0.011 only at budgets >=14; at 6-10 they shift by up to
   0.072 - int@6 +0.100 free vs +0.028 paid, int@10 +0.128 vs
   +0.089, text@6 +0.073 vs +0.017 - all from the free-block
   convention.)
4. F5-rng note (A33 finding 3): removing the dead bootstrap loop
   shifted the harness resample stream; the rev5 section's mut
   schema-control CI reads [+0.044, +0.128] (pre-F5 resample) while
   the current harness prints [+0.044, +0.122]. Both are valid
   95% bootstrap resamples of the same paired data; the point
   estimate (+0.083) is identical.

## rev7: budget sensitivity

Post-hoc (budget_sweep.py, not part of the registered measurement).
MAX_STEPS swept over {6, 10, 14, 18, 25} on all three held-out
splits; all four conditions share the budget per cell (n=180 per
cell). Cells are verified / baseline / baseline-eq / baseline-schema.
Run POST-rev6 (the F1 fix shifts the text column). ACCOUNTING: the
verified column uses run_verified_loop's FREE-block convention
(blocks cost no budget) while the schema column pays a step per
rejection - mixed accounting, superseded by rev8's like-for-like
grid; the table below is retained for provenance only.

| budget | int | text (post-F1) | mut |
|---|---|---|---|
| 6 | 0.411 / 0.294 / 0.294 / 0.294 | 0.467 / 0.394 / 0.394 / 0.394 | 0.000 / 0.000 / 0.000 / 0.000 |
| 10 | 0.778 / 0.650 / 0.656 / 0.650 | 0.761 / 0.678 / 0.689 / 0.678 | 0.406 / 0.183 / 0.183 / 0.183 |
| 14 | 0.861 / 0.744 / 0.750 / 0.744 | 0.894 / 0.767 / 0.789 / 0.767 | 0.956 / 0.539 / 0.539 / 0.761 |
| 18 | 0.861 / 0.744 / 0.750 / 0.744 | 0.894 / 0.767 / 0.789 / 0.767 | 0.956 / 0.578 / 0.572 / 0.872 |
| 25 | 0.861 / 0.744 / 0.750 / 0.744 | 0.894 / 0.767 / 0.789 / 0.767 | 0.956 / 0.578 / 0.572 / 0.872 |

Findings:

1. The verified condition dominates every control at every
   non-degenerate budget in every world. (Mut budget 6 is a floor
   effect: a 3-4 file plan needs 8-11 steps; disclosed, not a
   finding.)
2. The registered budget (25) sits on the plateau - results are not
   a budget artifact; nothing was tuned at 25.
3. WITHDRAWN (rev8): the mut +0.194-at-budget-14 figure compared
   verified FREE-block accounting against schema PAID-block
   accounting and is an accounting artifact. Like-for-like
   (rev8's grid): +0.111 both-free, +0.067 both-paid, bracketing
   the plateau +0.083. (rev9a wording fix, A33: the int/text
   residuals are accounting-invariant within +-0.011 at budgets
   >=14; at 6-10 the residual shifts by up to 0.072 - int@6
   +0.100 free vs +0.028 paid, int@10 +0.128 vs +0.089, text@6
   +0.073 vs +0.017 - all from the free-block convention.)
4. WRONG AS STATED (corrected in rev8): in the verified loop a
   pre-gate block costs ZERO steps (run_verified_loop budgets on
   accepted history only), while the baseline and schema loops pay
   one step per rejection. Verification is cheaper per attempt, not
   equal-cost; rev8 states this as a design property and re-derives
   the grid under both accountings.

## rev6: audit fixes (A33 FINAL PARTIAL + A39 FINAL PARTIAL)

Both auditors replicated every number byte-exact on 3.10 and 3.12
(bootstraps included), confirmed no ground-truth leak, the rev0
defect counterfactual (baseline collapses to exactly 0.444), the
baseline-eq parity, and the M6 regression mutant reproducing rev0's
0.750/0.444. Findings and fixes:

F1 MATERIAL (A33, calibrated by A39): the text-world swap channel
was detection-DEGRADED on chained concats (T1/T3): _absorb folded
the VIOLATED concat observation into the running total before the
repair was built, so repair operands came from the poisoned total
(witness TH00). A39's calibration from the shipped rows (A33's
"0/120" is too strong in aggregate): pre-fix, text runs with an
effect-miss recovered 12/23 (52%) vs int 20/22 (91%); by family
T1 5/9, T2 5/5, T3 2/9. FIX: effect-violated records are never
absorbed (excluded durably by record identity, so the poison cannot
re-enter through history after the repair). POST-FIX recovery
counts: text 19/23 (83%) - T1 9/9, T2 5/5, T3 5/9 (the T3 residual
is the uncatchable decoy channel, not this defect); int 20/22 (91%,
unchanged). Re-measured text held-out, SUPERSEDING rev2 as
disclosed above:

- verified 161/180 = 0.894 (was 0.856); baseline 0.767;
  baseline-eq 0.789 (unchanged)
- HEADLINE paired diff vs baseline-eq +0.106 [+0.061, +0.150]
  (was +0.067 [+0.033, +0.106]); vs baseline +0.128 [+0.083, +0.178]
- silent wrong answers: verified 14 (was 21) vs baseline 27
- per family (verified / baseline / baseline-eq): T1 0.967/0.750/0.817;
  T2 0.967/0.883/0.883; T3 0.750/0.667/0.667
- text dev: verified 0.900 (was 0.800) vs 0.667/0.667,
  +0.233 [+0.133, +0.333]
- int and mut held-out BYTE-IDENTICAL (0.861, 0.956): the poisoned
  channel only exists on concat. A regression test pins the fix
  (chained concat, swap always on, repairs always clean: verified
  now recovers, baseline stays silent-wrong).

F3 (A33 + A39): the rev3 "nested draws (superset)" claim is false
under both operationalizations: 11/360 held-out runs (A33), 6/360
(A39). Mechanism: dropping a predicate changes the actor's step
sequence, so the rng draw stream stops aligning across p values.
Wording corrected in the rev3 section and in noise_sweep.py.

F4 (A33): PRIOR_ART.md cited StepTool as "Ye et al. 2024"; arXiv
2410.07745's first author is Yuanqing Yu. Corrected to "Yu et al.
2024".

F5 (A33): run.py _bootstrap_diff had a dead first loop; removed.

A39 provenance fixes:
1. The stepverify pin named a commit (1c69d43) that does not exist
   at shared-models tip 97aae1f; stepverify.py reaches that repo
   only via the uncommitted patch agi-stepverify-sm.patch. The pin
   now names the patch and its file sha256 (header of this file).
2. backend/instinct_models/VENDORED.md still claimed "re-sync via
   script / do not edit here"; rev0 added stepverify.py directly.
   VENDORED.md now documents the exception and the manual re-sync
   rule until the patch lands upstream.

A39 calibration on rev5: baseline-schema at retry 0.92 gives the
identical 157/180 on mut held-out, so the +0.083 residual is
mechanism, not repair-rate.

A39 harness notes (recorded, not defects):
- Removing the actor-expect check collapses verified to exactly
  baseline-eq: the predicate channel carries the whole int/text
  headline. Removing the spec effect floor changes NOTHING on this
  corpus (floor contribution unmeasured); dropping the grader's
  answer check changes nothing (redundant here); dropping the
  out_want file check shrinks the int gap to +0.033 - the strict
  file check carries the grading.
- The scripted baseline never semantically inspects non-error
  observations: a real ReAct agent could notice some silent slips in
  the observation text. The measured gap is against a NON-READING
  baseline; it bounds, not estimates, the benefit over an LLM loop.
- Step consumption at rev1: verified 6.94 vs baseline 7.29 mean
  steps - the conditions consume UNEQUAL step budgets on average at
  the same cap (the verified loop spends fewer steps because blocked
  calls short-circuit error spirals).

## rev5: the schema control - how much of the pre-gate gain is plain input validation?

Directed question: does the rev4 pre-gate gain survive a baseline
that validates tool ARGUMENTS before executing (presence, types,
integer-text shape) - no state preconditions (path existence is not
schema), no effect predicates? A schema rejection is recorded as an
error observation, so the actor retries it like any other failure.

### HEADLINE (honest): the pre-gate gain MOSTLY vanishes against the schema control

Mut held-out: verified 0.956 vs baseline-schema 0.872; paired diff
+0.083, bootstrap 95% [+0.044, +0.128] - down from +0.383 against
baseline-eq. Roughly four-fifths of the rev4 gap is captured by
plain argument validation: the malformed factor is ill-typed input,
and any careful framework checks that before executing. The
prediction contract's REMAINING edge (+0.083, CI excludes zero) is
the channel schema cannot see: semantically wrong but well-typed
calls, caught by stated effect predictions (mis-transcribed writes)
plus path-existence pre-gating. Mechanism audit: the schema control
blocked 102 calls; verified blocked 164 (the extra 62 are mostly
missing-path reads, which schema does not check).

### Schema control in the side-effect-free worlds: zero

- int held-out: baseline-schema 0.744 == baseline 0.744 (31 calls
  blocked; the malformed add was already a loud WorldError, so
  blocking it pre-execution changes accounting, not outcomes -
  exactly rev3's gates-off equivalence)
- text held-out: baseline-schema 0.767 == baseline 0.767 (0 calls
  blocked; every text-world error is well-typed - the swapped concat
  is a schema pass). The entire text-world gap is semantic and
  survives the schema control intact: +0.089 [+0.050, +0.133]

### Dev splits with the control (for the record)

- dev: schema 0.867 == baseline 0.867 (5 blocked)
- dev-text: schema 0.667 == baseline 0.667 (0 blocked)
- dev-mut: schema 0.917 vs baseline 0.667 (29 blocked)

Revised decomposition (supersedes the rev4 wording): the mechanism's
measured value = argument-schema checking (NOT novel, ~4/5 of the
mut-world gain) + state preconditions and actor-stated effect
predictions (the residual, +0.083 mut / +0.089 text / +0.117 int
against the strongest applicable control, each CI excluding zero).
The unique, non-schema part is the prediction contract; its measured
marginal value is the residual, not the headline totals.

## rev5: budget sensitivity

Post-hoc (budget_sweep.py, not part of the registered measurement).
MAX_STEPS swept over {6, 10, 14, 18, 25} on all three held-out
splits; both conditions share the budget per cell (n=180 per cell).

| budget | int v/b/eq | text v/b/eq | mut v/b/eq |
|---|---|---|---|
| 6 | 0.411 / 0.294 / 0.294 | 0.461 / 0.394 / 0.394 | 0.000 / 0.000 / 0.000 |
| 10 | 0.778 / 0.650 / 0.656 | 0.744 / 0.678 / 0.689 | 0.406 / 0.183 / 0.183 |
| 14 | 0.861 / 0.744 / 0.750 | 0.856 / 0.767 / 0.789 | 0.956 / 0.539 / 0.539 |
| 18 | 0.861 / 0.744 / 0.750 | 0.856 / 0.767 / 0.789 | 0.956 / 0.578 / 0.572 |
| 25 | 0.861 / 0.744 / 0.750 | 0.856 / 0.767 / 0.789 | 0.956 / 0.578 / 0.572 |

Findings:

1. The gap is positive at every non-degenerate budget in every world
   (at budget 6 in the mut world nobody can finish: a 3-4 file plan
   needs 8-11 steps; +0.000 is a floor effect, disclosed).
2. The registered budget (25) sits on the plateau - results are not
   a budget artifact; nothing was tuned at 25.
3. Verification costs no steps that matter: the verified condition
   dominates even when steps are scarce (budget 6 int: 0.411 vs
   0.294), because a blocked call and a failed call cost the same
   single step, while an UNCAUGHT silent error wastes all later
   steps built on it.
4. The mut-world gap is LARGER at tight budgets (+0.417 at 14 vs
   +0.383 at 25): retries of un-corruptible steps burn the
   baseline's budget faster.

## rev4: the mutating world - where the pre-gate earns its keep

rev3 showed pre-gates add no outcome value when every gated call is
side-effect-free. Family M (60 held-out + 20 dev tasks, DM*/HM* ids)
makes the gated call destructive: scale(path, factor) multiplies a
file in place, and a MALFORMED factor corrupts the target to
'CORRUPT' BEFORE the error is observable - the baseline sees the
error but cannot undo the damage (re-scaling 'CORRUPT' fails again).
P_BAD_FACTOR = 0.10; all other rates unchanged. The actor's stated
prediction contracts the intended factor against the pre-state,
computed before the error draw (same discipline as the rev2 concat
fix).

### Mut held-out (60 tasks x 3 seeds = 180 paired runs)

- verified 172/180 = 0.956; baseline 104/180 = 0.578; baseline-eq
  103/180 = 0.572
- paired diff vs baseline-eq +0.383, bootstrap 95% [+0.317, +0.456];
  vs baseline +0.378 [+0.311, +0.450]. DECOMPOSITION (rev5, the
  correct reading of this number): about +0.300 of the +0.383 is
  plain argument-schema checking (not novel); the prediction-
  contract residual is +0.083 [+0.044, +0.128] against the schema
  control. +0.383 is NOT a mechanism-attributable figure.
- mechanism audit: 164 pre-execution blocked calls + 15 effect-miss
  repairs vs 74 baseline error observations
- silent wrong answers: 0 vs 0 (corruption is LOUD here; the cost is
  task failure, not wrong answers)

### Mut dev (20 x 3 = 60 runs), seen before the mut held-out ran

- verified 0.983 vs baseline 0.667 and baseline-eq 0.667
  (+0.317 [+0.200, +0.433])

Interpretation (as revised by rev5): when a bad call corrupts state,
GATING the call carries most of the value - but rev5's schema
control shows roughly +0.300 of the +0.383 is plain argument
validation, leaving the prediction-contract residual at +0.083
[+0.044, +0.128]. The repair probability still stops mattering
(baseline-eq 0.572 is NO BETTER than baseline 0.578: a higher retry
rate cannot un-corrupt a file). Combined with rev3: the mechanism's
value decomposes as (effect predictions: always on, linear in
completeness) + (pre-execution gates: outcome value exactly when
gated calls have side effects). Identical outputs on Python 3.10.12
and 3.12.15. rows_dev-mut.jsonl and rows_heldout-mut.jsonl carry
every run.

## rev3: verifier-noise sensitivity (sound-but-incomplete checking)

Post-hoc (noise_sweep.py, not part of the registered measurement).
Two degradation axes on the verified condition, both held-out splits:
p_drop = probability the actor fails to state an effect prediction
for a step (cells paired by task and seed; NOT strictly nested -
once a dropped predicate changes a trajectory the draw streams
desynchronize across p values; A33 measured 11/360 held-out runs
where the superset property fails; A39 operationalizes it as
6/360);
gates = the TOOLS registry with preconditions and spec effect floors
on or stripped (schema checks only).

| p_drop | int held-out (gates on) | int (gates off) | text held-out (on) | text (off) |
|---|---|---|---|---|
| 0.00 | 0.861 | 0.861 | 0.856 | 0.856 |
| 0.25 | 0.828 | 0.828 | 0.844 | 0.844 |
| 0.50 | 0.794 | 0.794 | 0.817 | 0.817 |
| 0.75 | 0.778 | 0.778 | 0.794 | 0.794 |
| 1.00 | 0.750 | 0.750 | 0.789 | 0.789 |

Reference points: int baseline 0.744 / baseline-eq 0.750; text
baseline 0.767 / baseline-eq 0.789 (n=180 each). The text column is
PRE-rev6 (A33 F1); the post-fix text grid is 0.894 / 0.883 / 0.839 /
0.800 / 0.789 at the same p_drop values - same shape, still
converging exactly to baseline-eq at p_drop=1.0. The int column is
unaffected by the F1 fix.

Findings:

1. The gap degrades gracefully and roughly linearly with predicate
   completeness; at p_drop=1.0 the verified condition converges
   EXACTLY to the equal-probability control (asserted in the harness
   and pinned by a sanity test), confirming the whole headline gap is
   carried by stated predictions, with no harness residue.
2. Gates on vs off change NOTHING in either world (columns are
   identical): every precondition-gated call here is side-effect-free
   (a missing-file read, a malformed add), so blocking it and letting
   it fail into an error observation produce identical trajectories
   and identical rng consumption. In these worlds the pre-gate's
   value is accounting, not outcomes. In a world where a bad call
   would corrupt state, pre-gating should matter - UNVERIFIED here;
   flagged as a rev4 direction.
3. Sanity: p_drop=0 reproduces the registered verified numbers
   exactly (0.861 / pre-rev6 0.856); the grid is paired by task and
   seed but NOT strictly nested (see the p_drop description).

Two wrapper defects were caught by the harness's own convergence
assertion while building rev3 and are disclosed: identity tracking of
the actor's pending step required re-pointing after predicate
stripping, and the true convergence target is baseline-eq (repair
probability survives degradation; verification does not).

## rev2: second world family (non-integer data)

Text world: files hold comma-joined word lists; a string concat tool
(concat a sep b) replaces integer add. Families T1/T2/T3 mirror A/B/C
(concat-aggregate over 3-5 files, concat chain with read-back,
concat-aggregate with same-named decoys) over separate TD*/TH*
splits, so the rev1 int-world numbers above stay byte-reproducible
(re-verified identical after the rev2 changes: dev 0.917/0.867/0.883,
held-out 0.861/0.744/0.750). Error mix: same rates, with P_BAD_ADD
replaced by P_BAD_CONCAT = 0.08 - a concat with swapped operands,
which is SILENT for the baseline (a well-formed string, wrong order)
and is caught only by the actor's stated effect prediction; the
prediction is contracted on the intended operands before the error
draw. One text-specific error channel (decoy reads in T3) remains
uncatchable, as with family C.

### Text held-out (60 tasks x 3 seeds = 180 paired runs) - SUPERSEDED by rev6 (A33 F1)

- verified 154/180 = 0.856; baseline 138/180 = 0.767; baseline-eq
  142/180 = 0.789  - SUPERSEDED (rev6: 0.894 / 0.767 / 0.789)
- HEADLINE paired diff vs baseline-eq +0.067, bootstrap 95%
  [+0.033, +0.106]; vs baseline +0.089 [+0.050, +0.133] - SUPERSEDED
  (rev6: +0.106 [+0.061, +0.150] / +0.128 [+0.083, +0.178])
- silent wrong answers: verified 21 vs baseline 27 - SUPERSEDED
  (rev6: 14 vs 27)
- per family (verified / baseline / baseline-eq): T1 0.900/0.750/0.817;
  T2 0.967/0.883/0.883; T3 0.700/0.667/0.667 - SUPERSEDED (rev6:
  T1 0.967/0.750/0.817; T2 0.967/0.883/0.883; T3 0.750/0.667/0.667)
- mechanism audit: 44 blocked calls + 26 effect-miss repairs in the
  verified condition vs 45 baseline error observations. CORRECTION
  (A33 F1): pre-rev6, 8-9 of those 26 repairs were chained-concat
  repairs that COULD NOT succeed (the violated observation had
  already poisoned the running total), so the rev2 claim that the
  effect-predicate channel "carries more weight" overstated
  recovery. Post-rev6 the 26 misses are real recoveries.

### Text dev (20 x 3 = 60 runs), seen before the text held-out ran - SUPERSEDED by rev6

- verified 0.800 vs baseline 0.667 and baseline-eq 0.667
  (+0.133 [+0.050, +0.233]) - SUPERSEDED (rev6: 0.900 vs 0.667/0.667,
  +0.233 [+0.133, +0.333])
- family T1 0.667/0.619/0.619; T2 1.000/0.762/0.762;
  T3 0.722/0.611/0.611

Interpretation: the mechanism transfers to non-integer data; with the
rev6 absorb fix the headline gap is +0.106 [+0.061, +0.150], in line
with the int world. Identical outputs on Python 3.10.12 and 3.12.15.
rows_dev-text.jsonl and rows_heldout-text.jsonl carry every run
(regenerated at rev6).
