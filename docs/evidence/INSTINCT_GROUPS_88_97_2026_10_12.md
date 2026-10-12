# Instinct doc groups 88-97: execution delta

Base: `4163f497f38420a7f755501034549fc9e2e4a4b0`.
Source: private source locator withheld
Group numbering comes from the supplied 142-group request audit, not an independent completion count.

All ten broad groups remain **PARTIAL**. This patch adds executable capabilities,
not evidence for broad superiority, human psychology replication or autonomous businesses.
No live messages, account creation, model download or external product claims were made.

| Group | Executable delta | Remaining literal acceptance gap |
|---|---|---|
| 88 | Dependency-ready scheduling without layer barriers, bounded retry/reviewer failure handling, executed same-case comparison harness | No Cellcog/Strawberry/YC-tool adapter or evaluated superiority; trusted callables, not a sandbox |
| 89 | Whole-token emotion/motive evidence with sentence-bounded negation and exact spans | Lexicon cues are not human psychology or intelligence replication |
| 90 | Brand analysis retains per-source quotes/spans and affiliate mentions instead of mixing facts | No autonomous Pinterest/brand research, affiliate enrollment or business outcome |
| 91 | Actual local Diffusers pipeline call, local-only weights, output PNG labels/hashes, overwrite refusal | No model weights supplied or actual inference/visual quality/pixel review demonstrated |
| 92 | Existing OfflineWhisper adapter wired to timestamped reasoning-cue analysis | ASR wiring tested with synthetic backend; no actual weights/audio inference or learned human thought/music understanding |
| 93 | Owner-note extractive adaptation with platform length bounds and review-only status | Only three platform draft formats; no category-wide coverage, accounts or publication |
| 94 | Blueprint worker graph now executes registered offline handlers with dependency propagation | No company formation, external operations or thousands of industry workflows |
| 95 | Actual learned nearest-centroid model, heldout prediction, majority baseline and model artifact | Small supplied numeric datasets only; no sector-best tool, deep training or scientific breakthrough |
| 96 | Reconcile dated completion evidence, reject impossible prerequisite completion, remove completed work and expose ready steps | Caller artifacts not independently verified; no owner's current personal results demonstrated |
| 97 | Draft-to-exact-M00 descriptor, unchanged review snapshot requirement, durable single-send claims, Gmail API transport and account-profile check | No live approved destination/send demonstrated; host must bind sender token and trusted state probes; no manuscript attachments |

## Commands and evidence

From repository root:

```sh
python -m pytest --noconftest tests/troop tests/apply \
  tests/modules/test_instinct_88_97_execution.py tests/modules/test_c32* \
  tests/modules/test_c33* tests/modules/test_c36_blueprint* \
  tests/modules/test_c37_breakthroughs_s64.py \
  tests/modules/test_m23_polymath_roadmap.py \
  tests/modules/test_c30_m00_integration.py -q
```

Tests use actual registered Python actions and actual M00/SQLite decisions and
consumption. Gmail HTTP, image pipeline and ASR tests use explicit synthetic
fixtures. They validate mechanics only, not live inference or delivery.
`--noconftest` avoids unrelated whole-application fixtures; the listed integration
tests construct their own actual approval services. Full repository suite not run.

## Production integration boundaries

- `TroopRunner` and `evaluate` accept trusted registered implementations only.
  No timeout or isolation can safely kill arbitrary Python thread code.
- `LocalProductImages` needs optional `images` dependencies and an absolute local
  Diffusers directory. It refuses remote model IDs and disables remote code. Host
  controls weights/license and device. Every actual output still needs pixel review.
- `AudioReasoning` needs the existing `asr` optional dependencies and configured
  local Whisper model. Its cue tags are deterministic, not learned reasoning.
- `PitchExecution` is library wiring, not a newly mounted web route. The host must
  authenticate the owner and trusted sender, provide a actual approval service,
  and register account/destination state probes before review. Client approval
  dicts and an `approved_by='owner'` string do not authorize a send here.
- Pitch execution uses M10 outreach and the exact sender, recipients, body and
  immediate delivery setting. No future scheduling or attachments are supported.
  A timeout leaves a durable `started` or `dispatching` receipt. It must be reconciled against the
  provider, not retried. Provider acceptance is not proof of delivery.

Final targeted regression: **1,257 passed**, no skips, in 8.71 seconds.
`git diff --check` passed. Offline selfcheck executed actual worker actions and
trained a centroid model: 1.0 heldout accuracy versus 0.5 training-majority
baseline on the tiny synthetic split, not a sector benchmark. Results are in
`INSTINCT_GROUPS_88_97_OFFLINE_RESULTS.json`. Run it with:

```sh
python scripts/instinct_88_97_selfcheck.py --output-dir /absolute/new/output-dir
```

## Patch 5: sender approval-store enforcement

GmailPitchSender construction now requires its host's PitchExecution approval
store. The sender takes the complete descriptor and approval ID, independently
reads the exact durable M00 consumption record, checks the current review state
and expiry, and atomically changes the matching unused execution claim from
`started` to `dispatching` before accessing credentials or HTTP. A flag or
fabricated local send claim alone does not pass. Missing store, missing M00
consumption, mismatched payload, absent execution claim and transport replay
are all tested refusals. This is a trusted-host process boundary, not protection
against arbitrary code that already controls the token, database or Python
runtime. Sender account-profile checks remain an additional guard.

Host wiring: create PitchExecution with its durable DB, actual M00 service and
trusted registry, then bind GmailPitchSender with `approval_store=executor` and
assign `executor.sender`. No unauthenticated constructor creates an approval.

HTTP acceptance tests now run through the approval flow. Additional negative
tests deliberately attempt direct calls to confirm they fail before transport.
