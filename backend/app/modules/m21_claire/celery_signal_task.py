"""Celery entrypoint for scheduled public-feed polling in Atlas.

Import/autodiscover this task from the Atlas Celery app and configure Beat only after
reviewing CLAIRE_PUBLIC_FEEDS_JSON. No external action besides bounded public GETs occurs.
"""
from __future__ import annotations
import json
import os
from celery import shared_task
from .scheduled_signal_cycle import run_feed_cycle


@shared_task(name="atlas.claire.public_signal_cycle", acks_late=True)
def claire_public_signal_cycle() -> dict:
    raw=os.getenv("CLAIRE_PUBLIC_FEEDS_JSON","[]")
    try: feeds=json.loads(raw)
    except json.JSONDecodeError as exc: raise RuntimeError("CLAIRE_PUBLIC_FEEDS_JSON must be valid JSON") from exc
    if not isinstance(feeds,list) or any(not isinstance(url,str) for url in feeds):
        raise RuntimeError("CLAIRE_PUBLIC_FEEDS_JSON must be a JSON array of HTTPS URLs")
    if not feeds: return {"status":"no_feeds_configured","feeds_attempted":0}
    tenant=os.getenv("CLAIRE_SIGNAL_TENANT_ID","").strip()
    if not tenant: raise RuntimeError("CLAIRE_SIGNAL_TENANT_ID is required for tenant-scoped feed polling")
    db_path=os.getenv("CLAIRE_RESEARCH_DB",os.getenv("CLAIRE_DISCOVERY_DB","./data/claire_research.sqlite3"))
    result=run_feed_cycle(tenant_id=tenant,feed_urls=feeds,workspace_path=db_path,max_feeds=3)
    result["status"]="completed"
    return result
