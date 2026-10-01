# October 1 bounded remediation

This patch adds actual numerical work to three previously worksheet-only feature paths. It is not full implementation of the 2,006-feature scope or a production deployment.

Install numeric extras with `pip install -e '.[executed_methods]'`.

- Row 823 metacognition: supply aligned `predictions` and binary `outcomes`, plus the existing objective/source. Computes Brier score, calibration bins, expected calibration error, observed accuracy, surprise indices and bounded confidence suggestions using the existing core CalibrationEngine. Data-less requests remain explicitly worksheet-only. Outcomes are caller-supplied, not independently verified. This batch path does not persist state or change live strategy; the separate GCW runtime owns durable claims. Authentication/tenant isolation of the existing route is not redesigned in this patch.
- Row 138 tuning: supply `X`, `y`, `search_space={"alpha":[0,1,10]}`, `budget` covering every candidate, optional `inner_cv` and `X_predict`. Fits a StandardScaler/Ridge pipeline inside each KFold split, selects by validation MSE and returns trial/fold scores, fitted coefficients/scaling and predictions. Supports IID numeric regression only, with caps. No arbitrary estimators, grouped/time series CV, checkpoint persistence or AutoML claim. Without data, the route returns an explicit plan-only status.
- Row 181 ARIMA: supply ordered `values`, `execute_fit=true`, `order=[p,d,q]`, optional `horizon`, `backtest_steps` and `alpha`. Fits nonseasonal ARIMA, fails closed on nonconvergence/nonfinite output, returns forecast/intervals/parameters and expanding-past-only backtests. No automatic stationarity decision, seasonal modeling, missing-data imputation or coverage guarantee. Without explicit execution, the route remains plan-only.

Local evidence: all 77 feature-mapped test files plus new regressions passed (3,900 tests). This was Python 3.12.14 with installed numeric extras, not the entire Atlas suite or a live provider test. Test cases distinguish actual outputs from flags, verify outcome-sensitive calibration, deterministic model selection/prediction, valid intervals, past-only backtests and malformed input rejection.

The first-pass audit overlay remains a historical baseline, not a current shipped-completion claim. These three locally repaired rows must be re-audited separately after review/application; they are not automatically promoted to deeply implemented or live accepted.
