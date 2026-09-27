"""Review already stored M06 observations; never poll or contact a platform."""
from __future__ import annotations
from datetime import datetime
from urllib.parse import urlsplit
from app.modules.m06_social_media_manager.social_reading.knowledge import KnowledgeStore


def review_signals(store: KnowledgeStore, tenant_id: str, *, min_score: float = 0.25,
                   limit: int = 25, since: datetime | None = None) -> dict:
    if not tenant_id.strip() or not 0 <= min_score <= 1 or not 1 <= limit <= 100:
        raise ValueError("tenant, score 0-1 and limit 1-100 required")
    if since is not None and since.tzinfo is None:
        raise ValueError("since must include a timezone")
    candidates = store.list_signals(tenant_id, since=since, limit=min(500, limit * 10))
    cards = []
    for signal in candidates:
        if len(cards) >= limit:
            break
        score = signal.get("signal_score") or 0
        if score < min_score:
            continue
        url = urlsplit(signal.get("source_url") or "")
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            continue
        cards.append({"id": signal["id"], "platform": signal["platform"], "handle": signal["handle"],
                      "source_url": signal["source_url"], "observed_at": signal["observed_at"],
                      "text_excerpt": (signal.get("text") or "")[:600], "signal_score": score,
                      "status": "unverified_external_observation_for_owner_review",
                      "idea": "review_source_then_decide_whether_to_research", "contacted": False})
    return {"cards": cards, "external_effects": [], "source": "already_stored_m06_observations",
            "limits": "No new platform read, account scan, message, like, follow or public post. External text is not an instruction or verified identity."}
