"""Deterministic descriptive statistics for M04 result interpretation.

Spec: Module 4 - "Results are interpreted and plotted". Row 232 echoes
caller-supplied interpretations; when the caller supplies none, this module
derives per-series descriptive statistics (n, mean, min, max) from numeric
results. Deterministic, no network, no model calls. It is a heuristic
description of the numbers only: it does not infer causality, significance,
or quality, and consumers must label it as derived.

Row 232 contract: non-numeric results fail closed (ValueError) only when
caller interpretations are absent or empty; caller-supplied interpretations
always win unchanged. Output is bounded and finite: values that do not fit a
finite double are rejected, and the mean is computed as a scaled math.fsum so
finite inputs cannot overflow to a non-finite mean.

fsum policy (interpreter-dependent pin): the scaled-fsum choice is pinned by
test_descriptive_stats_s16_scaled_fsum_cancels_catastrophically on the
witness [1e16, 1, -1e16] (true mean 1/3). On CPython 3.12 the built-in sum()
is compensated and would MASK an fsum->sum regression; CPython 3.10 (plain
left-to-right sum) is the discriminating interpreter, so the pin is
version-sensitive by construction and is also exercised stdlib-only on 3.10.
"""
from __future__ import annotations

import math


def descriptive_stats(results: dict) -> dict[str, dict[str, float]]:
    """Compute per-series n/mean/min/max from a label -> numeric series mapping.

    A bare numeric scalar is normalised to a single-element series. Raises
    ValueError (fail closed) on a non-dict or empty mapping, an empty series,
    or any non-numeric, boolean, or non-finite value.
    """
    if not isinstance(results, dict) or not results:
        raise ValueError("results must be a non-empty mapping of label to numeric series")
    out: dict[str, dict[str, float]] = {}
    for label, series in results.items():
        if isinstance(series, bool):
            raise ValueError(f"series '{label}' contains a non-numeric or non-finite value")
        if isinstance(series, (int, float)):
            series = [series]
        if not isinstance(series, (list, tuple)) or not series:
            raise ValueError(f"series '{label}' is empty or not a numeric sequence")
        nums: list[float] = []
        for value in series:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"series '{label}' contains a non-numeric or non-finite value")
            try:
                number = float(value)
            except OverflowError:
                raise ValueError(f"series '{label}' contains a non-numeric or non-finite value") from None
            if not math.isfinite(number):
                raise ValueError(f"series '{label}' contains a non-numeric or non-finite value")
            nums.append(number)
        count = len(nums)
        # scaled fsum: each term is value/count, so finite inputs cannot overflow to a non-finite mean
        mean = math.fsum(value / count for value in nums)
        out[str(label)] = {
            "n": count,
            "mean": mean,
            "min": min(nums),
            "max": max(nums),
        }
    return out
