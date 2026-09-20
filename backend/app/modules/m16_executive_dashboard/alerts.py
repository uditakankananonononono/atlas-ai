"""KPI alert rules: pure threshold evaluation.

Rules are evaluated when the service projects (POST /project). A triggered
rule appends one `alert` event per rule per cooldown window (default one
hour; deterministic event id from the window bucket), so repeated projection
inside the window is idempotent and the alerts feed is never spammed.
"""
from __future__ import annotations
from .schemas import AlertComparator,AlertRuleOut,KPI
def triggered(rule:AlertRuleOut,kpi:KPI)->bool:
    c=rule.comparator
    if c==AlertComparator.GT:return kpi.value>rule.threshold
    if c==AlertComparator.GTE:return kpi.value>=rule.threshold
    if c==AlertComparator.LT:return kpi.value<rule.threshold
    return kpi.value<=rule.threshold
def evaluate(rules:list[AlertRuleOut],kpis:list[KPI])->list[tuple[AlertRuleOut,KPI]]:
    by_id={k.id:k for k in kpis}
    return [(r,by_id[r.kpi_id]) for r in rules if r.kpi_id in by_id and triggered(r,by_id[r.kpi_id])]
def alert_message(rule:AlertRuleOut,kpi:KPI)->str:
    if rule.message:return rule.message
    return f"{kpi.label} is {kpi.value:g} {kpi.unit} ({rule.comparator.value} {rule.threshold:g})"
def cooldown_bucket(rule:AlertRuleOut,moment)->int:
    """Whole-cooldown bucket index for a moment; one alert per rule per bucket."""
    return int(moment.timestamp()//3600//rule.cooldown_hours)
