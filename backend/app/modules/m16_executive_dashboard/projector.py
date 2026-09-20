"""Snapshot projector: folds the durable event stream into the materialized
snapshot so the overview, timeline and KPI cards reflect what modules have
actually reported. Projection is idempotent (events fold by sequence) and
runs transactionally against the stored snapshot version.
"""
from __future__ import annotations
from datetime import datetime
from .schemas import Event,TimelineItem
TIMELINE_UPSERT_TOPIC="timeline.upsert"
ALERT_TOPIC="alert"
def apply_event(data:dict,event:Event)->dict:
    """Fold one event into snapshot data; returns the updated data dict."""
    data=dict(data)
    metrics=dict(data.get("metrics",{}))
    metrics[f"topic:{event.topic}"]=metrics.get(f"topic:{event.topic}",0)+1
    module_id=event.payload.get("module_id")
    if isinstance(module_id,int) and not isinstance(module_id,bool):
        metrics[f"module:{module_id}:events"]=metrics.get(f"module:{module_id}:events",0)+1
        metrics[f"module:{module_id}:topic:{event.topic}"]=metrics.get(f"module:{module_id}:topic:{event.topic}",0)+1
    data["metrics"]=metrics
    freshness=dict(data.get("freshness",{}))
    seen=event.occurred_at.isoformat()
    key=f"{event.aggregate_type}/{event.aggregate_id}"
    if freshness.get(key,"")<seen:freshness[key]=seen
    data["freshness"]=freshness
    if event.topic==TIMELINE_UPSERT_TOPIC:
        try:item=TimelineItem(**event.payload["item"])
        except Exception:return data
        timeline=[t for t in data.get("timeline",[]) if t.get("id")!=item.id]
        timeline.append(item.model_dump(mode="json"))
        timeline.sort(key=lambda t:t["start"])
        data["timeline"]=timeline
    if event.topic==ALERT_TOPIC:
        alerts=list(data.get("alerts",[]))
        alerts.append({"event_id":event.id,"sequence":event.sequence,"occurred_at":seen,"severity":event.payload.get("severity","info"),"message":str(event.payload.get("message",""))[:500],"module_id":module_id})
        data["alerts"]=alerts[-200:]
    return data
def fold(data:dict,events)->tuple[dict,int]:
    last=0
    for event in events:
        data=apply_event(data,event);last=max(last,event.sequence)
    return data,last
