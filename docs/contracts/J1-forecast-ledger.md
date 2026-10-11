# J1 early integration contract

Core planned path: app.modules.m20_general_cognitive_worker.j1_forecast.
Single scorer for S2.3: score_predictions(predictions, resolutions, *, bins=10,
calibrated=True) -> dict. Predictions are dictionaries with prediction_id,
claim, probability (finite numeric [0,1], bool forbidden), horizon, source,
made_at. Times are timezone-aware ISO timestamps, normalized to UTC. Horizon
is the explicit deadline strictly after made_at. Resolution dictionaries have
prediction_id, outcome (bool only), resolved_at (at or after horizon).

ForecastLedger(path, *, tenant_id, policy_guard=None)
append_prediction(*, claim, probability, horizon, source, made_at) -> prediction dict
resolve(prediction_id, *, outcome, resolved_at) -> resolution dict
report(*, calibrated=True, bins=10) -> score report

calibrated=True requires at least one prediction and one outcome per prediction;
unresolved or empty logs raise INTEL_REFUSED_UNSCORED. False returns partial
scores labelled descriptive, not calibrated. Missing/empty horizon raises
INTEL_REFUSED_NOHORIZON. No claim of future predictive skill.

Brier = mean((p - y)^2), lower is better. Sharpness = mean((p - 0.5)^2).
Equal-width reliability bins contain count, mean probability and observed rate;
empty bins have null means. p=1 is in final bin. Coverage is computed. Bin cap
1..100. Source content is metadata only; no feed fetch or trade execution.

Ledger: append-only prediction and resolution events. Existing events never
changed; exactly one resolution per prediction, replay does not duplicate it.
Tenant-specific file bound on creation; other tenant reads refused. Reload and
verify on every action. Integrity is a hash chain detecting accidental edits,
not a signature against an adversary able to rewrite the entire file.

Canonical policy interface imported from app.modules.c30.policy on base520985aa.
Result-schema alignment DEFERRED pending a deliberately defined shared schema.
F1 lambda-eval receipts are internal program evaluation, not forecast records.

## Source pin and design provenance

Owner wording supplied by main for the design source pin:
"a lot of strategies will come out, trends, the next best thing, predictions etc, ideas, etc."

Horizon, Brier, calibration refusal rules and this interface are build-program
design decisions under that line, not verbatim owner wording. This unit grants
no external communication, spending or trading permission. No market feeds.

## U03 integration decisions (pinned before handoff)

1. ACCEPT confidence -> probability, predicted_at -> made_at, horizon_days ->
absolute horizon = made_at + timedelta(days=horizon_days). U03 converts positive
finite numeric days (not bool); J1 validates the absolute timezone-aware deadline.
2. termT/thresholdN remain a U03 side-map prediction_id -> (term,N). Describe the
proposition clearly in claim. No extra metadata fields in J1 prediction schema.
3. append_prediction assigns full64-hex SHA256 of canonical normalized
{claim,probability,horizon,source,made_at}. Normalized UTC dates, float probability,
sorted keys, compact separators, ensure_ascii=False. Identical replay is idempotent.
Old term@asof@days IDs remain U03 side-map keys. These hashes are not source proof.
4. J1 is the single scorer. Import score_predictions and ForecastLedger from
app.modules.m20_general_cognitive_worker.j1_forecast. U03 drops local Brier,
hit-rate and calibration bins; keeps its resolver and collection logic only.
5. NO_COLLECTED_POSTS_IN_HORIZON / UNRESOLVED_TOO_EARLY create NO resolution,
never a false outcome. Missing outcome refuses calibrated=True; False is partial.
6. MIN_CALIBRATION_SAMPLE=20. scored_n printed in all reports. Under20,
calibration_label=insufficient_sample and small_sample_caveat says fewer than20
scored predictions, no calibration claim. Scores remain descriptive. At20+,
label=descriptive_reliability_only, never a positive calibration certificate.
The calibrated argument means request a complete scored cohort, not a claim the
forecaster is calibrated. No status says calibrated at any sample size.
7. J1 data/scoring/ledger boundary uses INTEL_REFUSED_*. U03 keeps TREND_*.
Canonical policy.classify rejects with its POLICY_* codes; effect route uses
check(action,'INTEL') and INTEL_* refusal mapping.
8. U03 resolver evidence window is (made_at,horizon], deadline-inclusive.
J1 accepts resolved_at >= horizon; it does not inspect posts or infer outcomes.
9. Incomplete collection is U03's limit. J1 does not claim to repair it; provided
outcomes, truthful dates and collection completeness remain unverified.

## Actual implementation and LIMITS

Stdlib core `j1_forecast.py` imports the shared c30.policy. All scorer invocations
classify an offline analyze descriptor, ledger init/append/resolve classify record,
report classifies read. Module20 is the registered host; c37 is the route family.
Canonical classifier is default; policy_guard injection is trusted host test
configuration only, never accepted from HTTP input. No policy mutation here.

MAX_PREDICTIONS=10000, MAX_EVENTS=20001 (header + predictions + resolutions),
MAX_BYTES=16000000, MAX_TEXT=4096. Bins int1..100, no bool. Timestamps max64
characters, timezone required. Timestamp normalization uses UTC. Collection
caps apply before scoring; JSONL byte/event caps apply before reading or append.
The supplied scorer is stateless and accepts exact prediction/resolution fields.
Sharpness is computed over resolved rows only, same cohort as Brier. Reliability
bin intervals [i/B,(i+1)/B), final interval includes1. Empty bins null, not zero.

No outcome may resolve before its deadline. Supplied times/outcomes still are not
independently verified. A caller may supply fictitious historical data; this is
math over their data, not authentic execution or proof of predictive skill.

File path comes from trusted host config, not API. Parent directories must be
trusted. Final-component symlinks/nonregular files refused; POSIX flock coordinates
cooperating processes. Every operation reloads and validates integrity/tenant.
A crash during append can leave an incomplete final line: fail closed, no silent
repair. Human admin restoration is needed. Hash chain detects alterations against
existing hashes, not whole-file adversarial rewrite, deletion or suffix truncation.
No signed external head/checkpoint or outcome authenticity proof. Deleting the
entire file permits new initialization; host backups/access controls are required.
Ledger fsyncs append data, but does not fsync the parent directory on first create.
Not portable to Windows: POSIX fcntl and O_NOFOLLOW required.

Optional router j1_forecast_routes.router mounts exact /api/v1/c37/forecast routes.
POST run action=predict with prediction fields (no prediction_id), or action=resolve
with resolution fields. GET report calibrated=True default, bins=10. Exact request
schema, unknown/effect actions refuse. Authenticated tenant selects a prebound
ForecastLedger. Host binds via bind_forecast_ledger; at most128 tenants. No main.py
edits. Host must impose HTTP pre-parse byte cap/rate limits and configure durable
private paths. No caller file paths, tenant overrides, external calls or trades.

## Evidence and remaining gates

Tests-first failure recorded on missing implementation. Frozen8 cohort gives
Brier0.143125, sharpness0.118125 and four-bin counts[2,1,2,3], with insufficient
sample warning. These measure scoring correctness, not prediction performance.
31 selected single-guard/calculation mutants killed by behavior tests, finite
battery only. Real file append/reload, thread contention, policy refusal, malformed
JSON, hash alteration, sequence mutation and tenant separation tested offline.

External validator PENDING, independent landing gate PENDING, full Atlas regression
suite PENDING. Local runner Python3.10.12 (declared Atlas version3.12 unverified).
Result-schema alignment DEFERRED by main: no deliberately defined shared schema
exists. F1 internal program-evaluation receipts cannot consume forecast ledgers.
Core dictionaries remain native J1 records, not a claim of F1 compliance. No external provider opinion fabricated.
