# Atomic numeric helpers (rows 93 and 107)

POST `/api/v1/api/modules/20/atomic-concepts-93-115/analyze` accepts a
`method` and a `data` object. Results remain JSON floats. Invalid domains or
numeric results outside the supported float range return HTTP 422 with a
string `detail`, rather than Infinity, NaN or HTTP 500.

## Reserve revenue

`selling_optimization` takes a nonempty `buyer_values` array of nonnegative,
finite numbers. It maximizes `reserve * count(value >= reserve)` over observed
valuation thresholds. Equal exact revenues choose the **lowest reserve**.
For `[10,20,30,40]`, the revenues are `[40,60,60,40]`, so the answer is 20,
not 40. Duplicates count as separate buyers.

Revenue comparisons use exact rational values of the supplied numbers.
Floats mean their represented binary values, not an assumed decimal value;
integers retain their exact value during comparison. Individual integers
larger in magnitude than the largest finite float are rejected before float
conversion. Outputs are rounded to floats only after selecting the winner.
If the winning revenue cannot be represented as a finite float, the request
returns 422. In particular `[6e307,1e308,1e308,1e308]` has a winning reserve
of `1e308` and revenue around `3e308`, so it returns 422, not a wrong reserve.

## Lag score

`system_delay` takes nonempty aligned `input` and `response` arrays and an
optional integer `max_lag` from 0 through sample length minus 1 (default).
Bools, coerced strings/floats, negative lags and lags with no overlap are
rejected. Each score is the raw mean product of overlapping pairs:
`sum(input[t] * response[t+lag]) / (length-lag)`. This is **not Pearson
correlation**: it neither centers the series nor divides by variance.
Constant and zero series are valid; zero variance is not a lag-score error.
Regression helpers still reject zero predictor variance.

The earliest lag wins equal exact scores. Exact rational sums avoid overflow,
underflow and cancellation in intermediate products without clipping,
normalizing or changing the objective. If any final lag score overflows a
float or a nonzero score rounds all the way to zero, the request returns 422.
Other representable subnormal outputs use ordinary float rounding. For
example `[1e308]` paired with `[1e308]` returns 422. `[0,0]` paired with a
constant series returns zero scores and lag 0.

## Limits

These are decision-support calculations, not automatic bids or effects.
Reserve revenue is an empirical bound that can overfit, not a promise of
future auction revenue. Exact rational arithmetic costs more CPU and memory
than float arithmetic; this change adds no sample-size cap, request quota or
performance guarantee. Unrelated algorithms have not been redesigned for
numerical conditioning. The shared result guard rejects nonfinite results,
and arithmetic/domain failures are converted to ValueError / HTTP 422.
