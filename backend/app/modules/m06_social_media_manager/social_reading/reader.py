"""Read runs: followers and feeds through the owner's own sessions.

Two transports, one normalized output:
- LinkedIn: the M13 session bridge navigates her paired browser to her
  connections and feed pages; HTML is parsed server-side.
- Instagram: the paired daemon reads via instaloader, logged in as her, on
  her own machine (no official personal-account API exists for this).

Both stop and report blocked on any login wall, challenge, or rate limit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions
from app.modules.m13_browser_agent.session_bridge.protocol import (
    CommandKind, PlatformBlocked, is_pc_session, split_pc_session)

from .knowledge import KnowledgeStore
from .parsers import parse_linkedin_connections, parse_linkedin_feed

LINKEDIN_CONNECTIONS_URL = "https://www.linkedin.com/mynetwork/invite-connect/connections/"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


class SocialReader:
    def __init__(self, sessions: BridgedSessions, store: KnowledgeStore):
        self.sessions = sessions
        self.store = store

    async def run(self, tenant_id: str, *, platform: str, operation: str,
                  session_id: str, instagram_username: str = "",
                  limit: int = 200) -> dict[str, Any]:
        if not is_pc_session(session_id):
            raise ValueError("social reads require a paired-PC session (pc.<device>.<name>)")
        run_id = self.store.start_run(tenant_id, platform, operation, session_id)
        try:
            if platform == "linkedin":
                result = await self._linkedin(tenant_id, operation, session_id, limit)
            elif platform == "instagram":
                result = await self._instagram(tenant_id, operation, session_id,
                                               instagram_username, limit)
            else:
                raise ValueError(f"unsupported platform: {platform}")
        except PlatformBlocked as error:
            self.store.finish_run(run_id, "blocked", {"block": error.kind.value, "detail": error.detail})
            raise
        except Exception as error:  # noqa: BLE001 - record the failure honestly
            self.store.finish_run(run_id, "failed", {"error": str(error)[:1000]})
            raise
        self.store.finish_run(run_id, "complete", result.get("summary", {}))
        return {"run_id": run_id, **result}

    async def _linkedin(self, tenant_id: str, operation: str, session_id: str,
                        limit: int) -> dict[str, Any]:
        page = await self.sessions.page(tenant_id, session_id, True)
        if operation == "connections":
            await page.goto(LINKEDIN_CONNECTIONS_URL)
            people = parse_linkedin_connections(await page.content())[:limit]
            for person in people:
                self.store.upsert_person(tenant_id, platform="linkedin", relation="connection", **person)
            return {"people": people, "count": len(people),
                    "summary": {"people": len(people), "source": LINKEDIN_CONNECTIONS_URL}}
        if operation == "feed":
            await page.goto(LINKEDIN_FEED_URL)
            posts = parse_linkedin_feed(await page.content())[:limit]
            new = 0
            for post in posts:
                _, created = self.store.record_work(
                    tenant_id, platform="linkedin", handle=post["handle"],
                    external_id=post["external_id"], kind="post", text=post["text"],
                    source_url=post["source_url"])
                new += int(created)
            return {"posts": posts, "count": len(posts), "new": new,
                    "summary": {"posts": len(posts), "new": new, "source": LINKEDIN_FEED_URL}}
        raise ValueError(f"unsupported linkedin operation: {operation}")

    async def _instagram(self, tenant_id: str, operation: str, session_id: str,
                         username: str, limit: int) -> dict[str, Any]:
        if not username:
            raise ValueError("instagram_username is required (her own Instagram login on the paired PC)")
        device_id, _ = split_pc_session(session_id)
        result = await self.sessions._execute(
            tenant_id, device_id, "social", CommandKind.SOCIAL_READ,
            {"platform": "instagram", "op": operation, "username": username, "limit": limit},
            timeout=600.0)
        if operation in {"followers", "following"}:
            people = result.get("people", [])
            relation = "follower" if operation == "followers" else "following"
            for person in people:
                self.store.upsert_person(
                    tenant_id, platform="instagram", handle=person["handle"],
                    display_name=person.get("display_name", ""), bio=person.get("bio", ""),
                    external_url=person.get("external_url", ""), relation=relation)
            return {"people": people, "count": len(people),
                    "truncated": bool(result.get("truncated")),
                    "summary": {"people": len(people), "truncated": bool(result.get("truncated"))}}
        posts = result.get("posts", [])
        new = 0
        for post in posts:
            observed = _parse_iso(post.get("taken_at"))
            _, created = self.store.record_work(
                tenant_id, platform="instagram", handle=post["handle"],
                external_id=post["shortcode"], kind="post", text=post.get("caption", ""),
                source_url=post.get("external_url", ""), observed_at=observed,
                detail={"likes": post.get("likes"), "comments": post.get("comments"),
                        "is_video": post.get("is_video")})
            new += int(created)
        return {"posts": posts, "count": len(posts), "new": new,
                "truncated": bool(result.get("truncated")),
                "summary": {"posts": len(posts), "new": new}}


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
