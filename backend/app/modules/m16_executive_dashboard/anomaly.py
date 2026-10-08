"""Baseline-relative KPI anomaly check (robust z-score on the KPI's own recorded history).

Alert rules need a hand-picked threshold. This checks a KPI's current value against what that KPI
has actually done: median and MAD (median absolute deviation) of its recorded points, robust z =
0.6745 * (value - median) / MAD. It is a heuristic and says so in every result: no seasonality, no
trend model, no claim about cause. Too little history returns "insufficient_history", never a guess.
"""
from __future__ import annotations
from datetime import datetime
from math import isfinite
from statistics import median
from pydantic import BaseModel
MIN_POINTS=8
Z_LIMIT=3.5   # Iglewicz-Hoaglin rule of thumb for modified z-scores
LIMITS=["heuristic: robust z-score on this KPI's recorded history only",
        "no seasonality or trend model: a weekly pattern can look anomalous",
        "history is whatever POST /project recorded; irregular recording intervals are not corrected",
        "flags a deviation, does not explain it"]
class AnomalyVerdict(BaseModel):
    kpi_id:str;window_hours:int;status:str;value:float|None;reason:str|None=None;points_used:int;min_points:int=MIN_POINTS;z_limit:float=Z_LIMIT
    baseline_median:float|None=None;baseline_mad:float|None=None;robust_z:float|None=None;direction:str|None=None
    oldest_point:datetime|None=None;newest_point:datetime|None=None;method:str="median/MAD robust z-score (heuristic)";limits:list[str]=LIMITS
def detect(kpi_id:str,window_hours:int,value:float,points:list[tuple[datetime,float]],min_points:int=MIN_POINTS,z_limit:float=Z_LIMIT)->AnomalyVerdict:
    """Score supplied history; window_hours identifies the KPI aggregation bucket.

    This function does not select or time-filter points. The service/repository
    selects matching aggregation buckets and excludes the last five minutes.
    window_hours is NOT a lookback cutoff or seasonality model.
    """
    bad_hist=sum(1 for p in points if p[1] is None or not isfinite(float(p[1])))
    cur_ok=value is not None and isfinite(float(value))
    base=dict(kpi_id=kpi_id,window_hours=window_hours,value=float(value) if cur_ok else None,points_used=len(points),min_points=min_points,z_limit=z_limit)
    # controlled refusal: NaN/Infinity must never become a normal/anomalous verdict or reach the JSON response
    if not cur_ok:return AnomalyVerdict(status="invalid_data",reason="current KPI value is not a finite number",**base)
    if bad_hist:return AnomalyVerdict(status="invalid_data",reason=f"{bad_hist} of {len(points)} history points are not finite numbers",**base)
    if points:base.update(oldest_point=min(p[0] for p in points),newest_point=max(p[0] for p in points))
    if len(points)<min_points:return AnomalyVerdict(status="insufficient_history",**base)
    vals=[float(p[1]) for p in points];med=median(vals);mad=median(abs(v-med) for v in vals)
    base.update(baseline_median=med,baseline_mad=mad)
    if not (isfinite(med) and isfinite(mad) and isfinite(value-med)):return AnomalyVerdict(status="invalid_data",reason="values too large for a finite robust z-score",**{**base,"baseline_median":None,"baseline_mad":None})
    if mad==0:
        # Zero median absolute deviation: z is undefined, even if outliers exist.
        # Report a changed baseline without inventing a score.
        if value==med:return AnomalyVerdict(status="normal",direction=None,**base)
        return AnomalyVerdict(status="flat_baseline_changed",direction="above" if value>med else "below",**base)
    z=0.6745*(value-med)/mad
    if not isfinite(z):return AnomalyVerdict(status="invalid_data",reason="robust z-score is not finite",**base)
    return AnomalyVerdict(status="anomalous" if abs(z)>z_limit else "normal",robust_z=round(z,3),direction=None if z==0 else ("above" if z>0 else "below"),**base)
