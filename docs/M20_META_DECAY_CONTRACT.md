# META-DECAY: class exponential survival and internal due queue

Row33 candidate for independent SCOPED acceptance, not general knowledge decay.
Parallel opt-in operator; legacy observed-age routes remain honest and unchanged.

Caller-bound history records supply class, source, interval start/end, and a
boolean change indicator. False denotes a right-censored interval, not a claim
that the fact remains current indefinitely. Positive duration and finite times
are required. All timestamps/horizons use one caller-consistent time unit; the
operator does not infer units or validate observations independently.

Per class the likelihood is exponential survival with constant hazard, with
noninformative right-censoring and independent intervals assumed. The prior on
hazard is Gamma(shape1, rate1) in the caller's time unit. Posterior shape is
1+observed changes, rate is1+total exposure (including right-censored intervals).
The integrated posterior predictive probability of a change by horizon h is
1-(rate/(rate+h))**shape. Numeric computation uses log1p/expm1. Rate mean and
standard deviation report parameter uncertainty; they are not a calibrated
real-world error guarantee or a frequentist interval. No status/probability is
inferred from record count alone.

Forecasts only use intervals ended by as_of. At least40 intervals and5 changes
are required per class; otherwise probability is None with sparse abstention.
Supported horizons are inclusive0..100 caller time units. No temporal window,
change-point detection, drift correction, non-exponential hazard or automatic
freshness inference is claimed. Current freshness always remains None and
source truth verification is false. IDs/sources and exposure/event counts are
returned for the training data. Synthetic exponential holdout tests compare
reliability and Brier scores against a fixed0.5 no-class-information baseline;
they do not validate arbitrary distributions.

Tracking records caller-confirmed fact IDs, classes, source and confirmation
time. evaluate(as_of) computes probability of change since confirmation, capped
at the supported100-unit horizon and explicitly reports that horizon and actual
age. Probability at least0.5 places a recommendation in the internal due queue.
Unsupported classes are listed separately, not treated as fresh. Evaluations
cannot run backward before previous evaluation/confirmation. Refresh is an
explicit caller reconfirmation, not retrieval: it updates source/time and clears
the due entry. Later evaluations can re-add it. No calendar/task, external
scheduler, retrieval or autonomous action is created.

At most2000 histories,1000/batch and1000 tracked facts. Exact duplicate histories
are idempotent/no CAS write; changed identities refuse. META-DUR persists one
atomic tenant/kind snapshot, commit-before-memory, stale writer rejection.
SQLite restart/rollback/tenant isolation is tested, not deployment/PostgreSQL.
Mounted authenticated /api/v1/api/modules/20/decay-survival routes require
explicit tenant binding; unbound503, invalid422, stale409. The queue means only
recommended refresh, never proof that a refresh completed or data is fresh.
