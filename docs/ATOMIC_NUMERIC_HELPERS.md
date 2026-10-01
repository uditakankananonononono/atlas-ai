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

## Input-size and CPU policy

Both exact helpers accept at most **256 values per array**: `buyer_values`
for `selling_optimization`, and each of `input` and `response` for
`system_delay`. A longer array raises ValueError at `run` and returns HTTP
422 with a string `detail` such as `input supports at most 256 values` at
the mounted API. Checks run before numeric conversion or Fraction allocation;
lag's cap applies even when `max_lag` is zero. There is no truncation,
resampling, or configurable caller override. This deliberately rejects
previously accepted oversized requests, while leaving accepted results,
exact comparisons, rounding, and tie rules unchanged.

Reserve candidates are scanned once after sorting exact values; the first
occurrence of each threshold has demand equal to its remaining suffix length.
This is O(n log n) comparisons, rather than a demand scan for every threshold.
Lag still uses O(n * (max_lag + 1)) exact products, at most 32,896 products
for 256 samples and all 256 lags. The cap is conservative because fractions
at widely separated binary scales cost more than small integers.

Regression tests compare maximum-size results to independent Fraction
oracles and bound each helper call to 5 seconds on the test runner (including
all lags). This is a regression threshold, not a latency SLA or proof of
worst-case wall time on every deployment. Request parsing/body size, huge
integer token parsing, concurrency, rate limits and unrelated algorithms
require separate resource controls.

## Limits

These are decision-support calculations, not automatic bids or effects.
Reserve revenue is an empirical bound that can overfit, not a promise of
future auction revenue. Exact rational arithmetic costs more CPU and memory
than float arithmetic; the fixed sample cap bounds these two helpers but
does not add a request quota or deployment-wide performance guarantee. Unrelated algorithms have not been redesigned for
numerical conditioning. The shared result guard rejects nonfinite results,
and arithmetic/domain failures are converted to ValueError / HTTP 422.
