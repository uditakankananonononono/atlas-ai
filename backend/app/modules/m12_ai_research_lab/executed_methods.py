"""Bounded local model search and nonseasonal ARIMA, with measured outputs.

No dynamic estimator imports, executable code, external calls or model downloads.
Caller-supplied datasets are not automatically verified or persisted.
"""
from __future__ import annotations
import math
import warnings


def _integer(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _numbers(values, name):
    if not isinstance(values, list) or not values or any(isinstance(x, bool) for x in values):
        raise ValueError(f"{name} must be a nonempty numeric list")
    try:
        result = [float(x) for x in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numbers") from exc
    if not all(math.isfinite(x) for x in result):
        raise ValueError(f"{name} must contain finite values")
    return result


def tune_ridge(payload):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import KFold, GridSearchCV
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    x = payload.get("X")
    if not isinstance(x, list) or not 6 <= len(x) <= 5000:
        raise ValueError("X requires 6-5000 training rows")
    x = [_numbers(row, "X row") for row in x]
    if len({len(row) for row in x}) != 1 or len(x[0]) > 100:
        raise ValueError("X requires aligned rows with at most 100 features")
    y = _numbers(payload.get("y"), "y")
    if len(y) != len(x):
        raise ValueError("X and y must align")
    if payload.get("estimator", "ridge") != "ridge":
        raise ValueError("only the bounded ridge regression estimator is supported")
    space = payload.get("search_space")
    if not isinstance(space, dict) or set(space) != {"alpha"}:
        raise ValueError("ridge search_space supports only alpha")
    alphas = _numbers(space["alpha"], "alpha")
    if len(alphas) > 20 or len(set(alphas)) != len(alphas) or any(a < 0 for a in alphas):
        raise ValueError("alpha needs 1-20 distinct nonnegative candidates")
    budget = _integer(payload.get("budget", len(alphas)), "budget", 1, 20)
    if budget < len(alphas):
        raise ValueError("budget must cover every candidate; no silent truncation")
    folds = _integer(payload.get("inner_cv", 3), "inner_cv", 2, min(10, len(x) // 2))
    seed = _integer(payload.get("seed", 42), "seed", 0, 2**31-1)
    if payload.get("primary_metric", "neg_mean_squared_error") != "neg_mean_squared_error":
        raise ValueError("this implementation supports neg_mean_squared_error only")
    if payload.get("time_ordered") or payload.get("groups"):
        raise ValueError("grouped/time-ordered data requires a dedicated split strategy")
    pipeline = Pipeline([("scale", StandardScaler()), ("ridge", Ridge())])
    cv = KFold(n_splits=folds, shuffle=True, random_state=seed)
    search = GridSearchCV(pipeline, {"ridge__alpha": alphas}, scoring="neg_mean_squared_error",
                          cv=cv, refit=True, n_jobs=1, error_score="raise", return_train_score=True)
    search.fit(np.array(x), np.array(y))
    trials = [{"alpha": float(params["ridge__alpha"]),
               "validation_mse": float(-search.cv_results_["mean_test_score"][i]),
               "validation_score_std": float(search.cv_results_["std_test_score"][i]),
               "fold_validation_mse": [float(-search.cv_results_[f"split{k}_test_score"][i]) for k in range(folds)]}
              for i, params in enumerate(search.cv_results_["params"])]
    fitted = search.best_estimator_
    result = {"execution_status": "executed", "estimator": "standardized_ridge_regression",
              "selection_metric": "validation_mse", "best_parameters": {"alpha": search.best_params_["ridge__alpha"]},
              "best_validation_mse": -float(search.best_score_), "trials": trials, "folds": folds,
              "seed": seed, "training_rows": len(x), "no_test_optimization": True,
              "fitted_model": {"coefficients": fitted.named_steps["ridge"].coef_.tolist(),
                               "intercept": float(fitted.named_steps["ridge"].intercept_),
                               "feature_mean": fitted.named_steps["scale"].mean_.tolist(),
                               "feature_scale": fitted.named_steps["scale"].scale_.tolist()},
              "limits": ["Independent IID numeric regression only; not a general AutoML trainer.",
                         "Caller must keep external test data untouched until model selection is frozen.",
                         "No checkpoint persistence or production promotion is performed."]}
    if "X_predict" in payload:
        predict = [_numbers(row, "prediction row") for row in payload["X_predict"]]
        if not predict or len(predict) > 5000 or any(len(row) != len(x[0]) for row in predict):
            raise ValueError("X_predict must align with training features and contain 1-5000 rows")
        result["predictions"] = fitted.predict(np.array(predict)).tolist()
    return result


def fit_arima(payload):
    import numpy as np
    from statsmodels.tsa.arima.model import ARIMA
    values = _numbers(payload.get("values"), "values")
    if not 12 <= len(values) <= 5000:
        raise ValueError("ARIMA fitting needs 12-5000 ordered observations")
    order = payload.get("order", [1, 0, 0])
    if not isinstance(order, list) or len(order) != 3:
        raise ValueError("order must be [p,d,q]")
    p, d, q = [_integer(v, "ARIMA order", 0, 2 if i == 1 else 5) for i, v in enumerate(order)]
    if len(values) < 3 * (p + q + d + 1):
        raise ValueError("series too short for requested order")
    if payload.get("seasonal_order"):
        raise ValueError("seasonal ARIMA is not supported by this nonseasonal implementation")
    horizon = _integer(payload.get("horizon", 3), "horizon", 1, 30)
    backtest = _integer(payload.get("backtest_steps", 3), "backtest_steps", 1, min(10, len(values)-8))
    alpha = float(payload.get("alpha", .05))
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    captured = []
    def fit(series):
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter("always")
            model = ARIMA(np.array(series), order=(p,d,q)).fit(method_kwargs={"maxiter": 200})
        captured.extend(str(w.message) for w in ws)
        if not model.mle_retvals.get("converged", False):
            raise ValueError("ARIMA optimizer did not converge; no forecast accepted")
        if not np.isfinite(model.params).all():
            raise ValueError("ARIMA produced nonfinite parameters")
        return model
    records = []
    for index in range(len(values)-backtest, len(values)):
        if index < 3*(p+q+d+1):
            raise ValueError("backtest leaves too few observations for order")
        prediction = float(fit(values[:index]).forecast(1)[0])
        records.append({"training_end_index": index-1, "target_index": index,
                        "observed": values[index], "predicted": prediction, "error": values[index]-prediction})
    model = fit(values)
    forecast = model.get_forecast(horizon)
    means = np.asarray(forecast.predicted_mean)
    intervals = np.asarray(forecast.conf_int(alpha=alpha))
    if not np.isfinite(means).all() or not np.isfinite(intervals).all():
        raise ValueError("ARIMA produced nonfinite forecast")
    return {"execution_status": "executed", "order": [p,d,q], "horizon": horizon,
            "forecast": means.tolist(), "intervals": intervals.tolist(), "confidence_level": 1-alpha,
            "parameters": dict(zip(model.param_names, map(float, model.params))),
            "aic": float(model.aic), "bic": float(model.bic),
            "residual_mean": float(np.mean(model.resid)),
            "rolling_origin_backtest": records,
            "backtest_mae": sum(abs(x["error"]) for x in records)/len(records),
            "warnings": sorted(set(captured)),
            "residual_checks": ["residuals exposed; independent diagnostics still required"],
            "limits": ["Equally spaced univariate nonseasonal observations supplied by caller.",
                       "Intervals assume the fitted model and do not guarantee coverage.",
                       "No automatic stationarity decision, causal claim or deployment."]}
