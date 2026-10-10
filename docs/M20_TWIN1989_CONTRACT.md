# TWIN1989-A: stateful scalar linear digital twin

Targets row1989 Digital Twins only for bounded SCOPED acceptance. Adds actual
observed-state assimilation and predict/update, not residual-only supplied arrays.
No live sensor/physical deployment/arbitrary-system fidelity claim.1992/1993
optimization remain separate; no other row closes automatically.

Explicit tenant-bound TwinRegistry owns scalar models. Integrator binds each
registry before production/OIDC routes under `/api/v1/api/modules/20/digital-twins`
can create/read/assimilate/forecast. Unbound/mismatched authenticated tenant503,
unknown model404, malformed input422. Bound tenant stores have separate state;
no lazy cross-tenant default. This unit is in-memory only: process restart loses
all twins; no SQL persistence/restart durability claim, no automatic deployment.

Model parameters: state x, nonnegative variance P, timestamp, transition A,
control gain B, nonnegative process-noise rate Q, positive measurement variance R.
One supplied observation per update: xpred=A*x+B*u, Ppred=A^2*P+Q*dt;
innovation=z-xpred; K=Ppred/(Ppred+R); xnew=xpred+K*innovation;
Pnew=(1-K)^2*Ppred+K^2*R (Joseph scalar form). A is a per-transition coefficient,
NOT time-exponentiated or learned dynamics. Q is per-time-unit noise; B*u is a
supplied per-update input, not integrated over dt. Times use arbitrary caller
units consistently, must strictly increase. No model fitting/parameter discovery.
Forecast computes predicted state/variance without publishing it or consuming
timestamp; later observation can assimilate that time. Histories retain actual
observation/control/prediction/innovation/gain/posterior and timestamps.

All values finite exact nonboolean numbers, noise/variance signs checked.
Nonfinite/overflow and stale timestamps refuse before state publish. Registry
lock serializes complete updates; same-time concurrent observations cannot both
commit. Read results deep-copy state. At most128 models,1000 observations/model;
no eviction or unbounded retention. Supplied observations are not authenticated
physical readings; source_truth_verified alwaysfalse, uncertainty is conditional
on supplied model/noise assumptions, not verified confidence about the world.
Formal state receipts are not hidden chain-of-thought.

Independent scalar-filter tests verify each prediction/update and nondefault
A/B/Q/R/time gaps, zero uncertainty, forecasts leave committed state unchanged,
invalid/overflow rollback, strict-time race and tenant routes. No model/provider,
spend/external I/O or money. Ledger unchanged until independent acceptance.
Residual: live sensor synchronization, deployed physical fidelity, learned or
multivariate/nonlinear dynamics and persistent restart recovery not implemented.
