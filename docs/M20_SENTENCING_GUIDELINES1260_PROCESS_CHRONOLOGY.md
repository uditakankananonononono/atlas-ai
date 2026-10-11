# Row 1260 process chronology (builder's record)

Historical EQ labels below are builder reports. The final section withdraws
the M1260-04/M1260-05 count-guard arguments. Aggregate M1260-12 is reported
as independently proved by the reviewer; this chronology is not that proof.

Every entry below is grounded in a named log or git object. Times are IST
(UTC+5:30) from the runtime clock; shas are as seen by this builder's own
commands.

## Order of work (actual)

1. Builder source base: public main a294723b7a8f7bbe6067804ee4d7d325e1a8bde9. Mechanism verified by
   `git show`: legal_support_1260_1309.py _SPECS row at line 17,
   analyze_legal_feature at line 96, status
   "supplied_legal_review_template_only", named_capability_executed=False.
   All three new routes confirmed absent on main.
2. Test-first RED: tests written before the module existed; collection error,
   exit 2 (logs/row1260/red.log).
3. Runtime built, then the contract.
4. Three local commits were made on branch feat/m20-sentencing-guidelines1260:
   - 74209d71 test(m20): specify row1260 sentencing guidelines mapping (red)
   - 25b59fa6 feat(m20): row1260 module
   - 40b40bf4 docs(m20): row1260 contract
5. GREEN 20 passed (receipt key fix: caller's "provenance" string echoed as
   provenance_label; the hash block keeps "provenance").
6. Mutation battery round 1 (spec1260.json, 24 ops): 13 ASSERT + control +
   10 survivors (logs/battery1260/, per-mutant logs + classification).
7. Six test pins added for the dispositioned survivors (exact-type subclass
   inputs, asymmetric separation counts, jurisdiction 128/129, source_ref
   256/257, hash present-keys). An attempted heredoc applying them failed
   with SyntaxError; nothing was applied by that attempt (the file was
   unchanged, verified by a green run of the still-20 tests). Re-applied by a
   different method (python replace + cat >> heredoc).
8. GREEN 24 passed. Battery round 2 (logs/row1260/battery_final.log):
   20 ASSERT + control + 3 survivors (M1260-04, M1260-05, M1260-12).
9. Package delivered as 5 attachments including row1260_evidence.tar.gz.

## The 3 local commits and patch-only

The patch-only instruction (no git commit, push, rebase, amend or reset) took effect AFTER the commits already existed. Each of the following is named
here as a patch violation - a commit that should never have been made:
- 74209d71 test(m20): specify row1260 sentencing guidelines mapping (red) - PATCH VIOLATION
- 25b59fa6 feat(m20): row1260 module - PATCH VIOLATION
- 40b40bf4 docs(m20): row1260 contract - PATCH VIOLATION
They were KEPT, not erased, per the same instruction, and disclosed in the
delivery message. All work after that point is uncommitted:
`git status --short` shows only ` M tests/modules/test_m20_sentencing_guidelines1260.py`
(modified), and docs/M20_SENTENCING_GUIDELINES1260_PROCESS_CHRONOLOGY.md as a
new untracked file.

## Wrong-directory log (earns NO credit)

During round-2 packaging, `python3 row_mutate.py spec1260.json` was invoked
from the worktree directory where row_mutate.py does not exist. The resulting
logs/row1260/battery_final.log at that moment contained only the shell error
("can't open file ... No such file or directory") and an evidence tar was
built from it. This run earns NO credit and is not evidence of anything. The
error was caught (grep counts were 0), the battery was rerun from the correct
directory, and the tar was rebuilt with the real log. The delivered
row1260_evidence.tar.gz contains the real round-2 log; the slip was disclosed
in the delivery message.

## RED status of the 6 post-probe pins

The 6 pins added after battery round 1 (2 exact-type subclass assertions in
test_list_shape_and_exact_types; 4 in TestBatteryResiduals:
test_separation_counts_asymmetric, test_jurisdiction_128_129,
test_source_ref_256_257, test_hash_present_keys) had NO dedicated RED run:
they pin behavior the module already had, so they were green on arrival
against the unmutated module. Their killing evidence is battery round 2
(logs/row1260/battery_final.log): M1260-01/03/09/16/21/22/23 moved from
survive (round 1) to ASSERT (round 2) against exactly these pins. This is
stated plainly instead of claimed as test-first RED.

## Cf repair (validation-policy compliance, 2026-10-11 ~22:00 IST)

- Targeted RED first: TestUnicodePolicyCf (5 tests) added;
  logs/row1260/red_cf.log shows 4 failed, 25 passed on the pre-repair module
  (U+00AD, U+2060 and the full-Cf probe were accepted; the Zs-accepted and
  Cs-residual pins already passed).
- Module repair: _unicode_check now refuses categories Cc/Cf/Zl/Zp in full
  (unicodedata.category), replacing the listed-Cf ranges; _LISTED_CF removed;
  messages and docstrings updated; no Cs refusal added.
- Contract updated: raw-cap-first wording, full-Cf wording, new "Known
  residuals" section disclosing the Cs surrogate residual.
- A test-side slip in the new Cs pin (expected 1 assertion, default payload
  already carries one) was fixed to expect 2; the failing intermediate state
  is part of the record (1 failed, 28 passed run at ~22:00:58).
- GREEN: 29 passed (logs/row1260/green_cf.log).
- Battery re-anchored (M1260-10/11 search strings updated to the new guard
  line) and rerun as a NEW run, not a relabel: logs/row1260/battery_cf.log,
  per-mutant logs in logs/battery1260_cf/. Result: 20 ASSERT + control
  M1260-00 survive + 3 EQ survivors (M1260-04, M1260-05, M1260-12), same
  dispositions as round 2.

## Ledger reconciliation (24 vs 23)

The battery has 24 operations, M1260-00 through M1260-23. Every operation is
classified in the raw logs: 20 ASSERT (killed) + 4 survive = 24. The 4
survivors are M1260-00 (the control, which survives BY DESIGN), M1260-04 and
M1260-05 (pigeonhole-EQ), and M1260-12 (unreachable-EQ). The "23" came from
my own delivery sentence "20 killed + 3 survive", which omitted the control;
my earlier phrase "21 ops killed" was a miscount. The raw logs
(logs/row1260/battery_final.log, battery_cf.log, battery_strict.log) are the
record.

## Strict-str and as_of repair (2026-10-11 ~22:06 IST)

- Targeted RED first: TestStrictStrAndAsOfOrder (2 tests);
  logs/row1260/red_strict.log shows 2 failed, 29 passed on the pre-repair
  module (str subclasses accepted; overlong as_of refused as invalid_input by
  the regex instead of resource_limit by the raw cap).
- Module repair: every string check is now exact type (type(x) is str); no
  isinstance remains in the module (grep count 0). as_of takes its raw
  10-character cap (resource_limit) BEFORE the ISO regex (invalid_input).
  Docstring validation-order wording updated.
- GREEN: 31 passed (logs/row1260/green_strict.log).
- Battery re-anchored (M1260-14/15 search strings updated to the new source)
  and rerun as a NEW run: logs/row1260/battery_strict.log, per-mutant logs in
  logs/battery1260_strict/. Result: 20 ASSERT + control + the same 3 EQ
  survivors; M1260-09/15/16 are now killed by the new strict-str/as_of/Cf
  pins.

## Basis/keys repair (2026-10-11 ~22:12 IST)

- Targeted RED first: TestBasisAndKeyTypes (4 tests);
  logs/row1260/red_basis.log shows 3 failed, 32 passed on the pre-repair
  module (basis str subclass accepted; overlong basis refused by membership
  as invalid_input instead of by the raw cap; str-subclass keys accepted at
  both levels). The set()-spy test passed pre-repair: the module never hashed
  caller keys.
- Module repair: basis is exact str with a raw 12-char cap (resource_limit)
  BEFORE membership (invalid_input); keys at root and item levels must be
  exact str - a str-subclass key is refused (invalid_input) even when it
  carries an allowed name. Count-first ordering, full Cf, as_of 10-char raw
  cap and strict text are unchanged.
- Test-side adjustment, disclosed: the runtime set() spy became unobservable
  once subclass keys are refused at the door (a Spy(str) key can no longer
  reach the key loop). The pin was rewritten as a static source scan
  (module source contains no "set(" call, grep count 0) plus the
  subclass-key refusal pin. The intermediate run "1 failed, 34 passed" is
  part of the record.
- GREEN: 35 passed (logs/row1260/green_basis.log).
- Battery: M1260-13's anchor still matched (count 1); logdir rotated and the
  battery rerun as a NEW run: logs/row1260/battery_basis.log, per-mutant
  logs in logs/battery1260_basis/. Result: 20 ASSERT + control M1260-00
  survive + the same 3 EQ survivors (M1260-04/05 pigeonhole, M1260-12
  unreachable); M1260-13 is now killed by test_basis_raw_cap_before_membership.

## Final-gate pins and WITHDRAWN equivalence claims (2026-10-11 ~22:21 IST)

- My earlier disposition of M1260-04 and M1260-05 as "pigeonhole-EQ" was
  FALSE under the strict key domain and is WITHDRAWN: with the count cap
  removed, an over-cap dict carrying an int key reaches the exact-str key
  check and is refused as invalid_input, while the capped module refuses it
  generically as unknown_key - an observable difference. The correct order is
  count guard BEFORE key type. The correction lives here; the original
  (wrong) statements in the rounds above are kept as the record.
- The only equivalence that stands is the aggregate guard (M1260-12):
  validated maximum 3 x 64 x (256 + 256) + 64 + 128 + 10 + 256 = 98,762 <
  200,000, basis strings not charged to the aggregate. No pin needed; the
  auditor independently proved this one.
- Seven TEST-ONLY pins added (TestReviewPins); runtime unchanged
  (module sha256 before and after: 10bd4d7c...d588a8). The pins: root and
  item over-cap dicts with an int key hit the count guard (unknown_key)
  before key-type invalid_input; under-cap unknown top key hits the
  allowlist; exact canonical SHA goldens for baseline, each optional-field
  membership flip (value vs absent, present-None vs absent), list contents,
  present-empty vs absent; sort_keys=True exact golden vs sort_keys=False.
  Golden values were source-grounded: computed from the verified-correct
  runtime, then frozen as literals.
- Test-side slip, disclosed: the first version of the membership-flip pin
  indexed GOLDENS with a wrong derived key ("juris_one_none"), causing a
  KeyError and an intermediate "1 failed, 41 passed" run; fixed by naming
  the golden keys explicitly.
- GREEN: 42 passed (logs/row1260/green_gate.log).
- Targeted review-probe killing evidence (adapted AST probe, NOT run blind; line numbers
  verified against this source first): logs/row1260/gate_kills.log shows all
  7 modes (rootcap, itemcap, unknown, optfalse, optflip, listflip,
  sortfalse) killed by the new pins, exit=1 each.
- Own battery rerun (M1260-13 anchor verified, logdir rotated):
  logs/row1260/battery_gate.log - 22 ASSERT + control M1260-00 survive +
  exactly 1 survivor, the proven-EQ aggregate M1260-12. M1260-04/05 now die
  on the over-cap guard-ordering pins.
- The auditor's fresh 76-mutant gate is the auditor's own target; nothing
  here claims to satisfy it, and no closure is claimed.
