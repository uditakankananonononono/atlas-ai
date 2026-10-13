"""One bounded public-feed polling cycle; schedule externally with Celery Beat/cron."""
from __future__ import annotations
import json
from dataclasses import asdict
from typing import Sequence, Any
import urllib.parse
from .source_connectors import fetch_public_feed, parse_feed, analyze_signals
from .research_workspace import ResearchWorkspaceStore
from app.runtime.guardrails.enforcer import GuardrailEnforcer


def run_feed_cycle(*, tenant_id:str, feed_urls:Sequence[str], workspace_path:str="./data/claire_research.sqlite3", max_feeds:int=3, enforcer=None, declarations:dict[str,Any] | None=None) -> dict[str,Any]:
    """Fetch at most three configured public HTTPS feeds, store provenance, report errors.

    Configure feeds from a reviewed settings list, not a model-generated URL. A single
    cycle is bounded and returns; a scheduler must invoke it periodically for recurrence.
    This function never logs in to social platforms or posts/reaches out to anyone.
    """
    if not tenant_id.strip(): raise ValueError("tenant_id required")
    if not 1<=max_feeds<=3: raise ValueError("max_feeds must be in [1,3]")
    urls=list(dict.fromkeys(str(u).strip() for u in feed_urls if str(u).strip()))[:max_feeds]
    def safe_url(value: str) -> str:
        p=urllib.parse.urlsplit(value)
        return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,"",""))
    store=ResearchWorkspaceStore(workspace_path); fetched=[]; failures=[]
    gate=enforcer if enforcer is not None else GuardrailEnforcer()
    for url in urls:
        try:
            data,final_url=fetch_public_feed(url, enforcer=gate, declarations=declarations)
            parsed=parse_feed(data,final_url)
            signals=[asdict(s) for s in parsed]
            stored=store.add_signals(tenant_id,signals) if signals else {"new":0,"duplicates":0}
            fetched.append({"feed_url":safe_url(url),"final_url":safe_url(final_url),"parsed":len(signals),"stored":stored})
        except Exception as exc:
            # Do not put response bodies, credentials, or potentially sensitive raw errors in logs.
            failures.append({"feed_url":safe_url(url),"error_type":type(exc).__name__})
    all_signals=store.list_signals(tenant_id,limit=5000)
    return {"feeds_attempted":len(urls),"feeds_succeeded":len(fetched),"feeds_failed":len(failures),
            "fetched":fetched,"failures":failures,"analysis":analyze_signals(all_signals),
            "schedule":"single cycle only; configure an external scheduler for recurring runs",
            "outbound_actions":"public feed reads only; each DNS/HTTPS hop requires outbound-gate admission"}
