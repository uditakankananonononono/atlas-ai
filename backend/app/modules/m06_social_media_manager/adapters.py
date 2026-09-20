"""Official platform API adapters for the Social Media Manager.

Compliance boundary: every adapter talks to an official, documented platform
API only - Meta Graph API (Instagram business accounts), X API v2, the
LinkedIn API, and TikTok's Content Posting API. No unofficial wrappers, no
scraping, no self-bots, no session hijacking. TikTok publishing uses the
inbox/upload flow, which delivers the video as an editable draft inside the
creator's own app; a human still makes the final post there.

Structure: each adapter separates a pure payload-building layer (no network,
fully unit-testable offline) from the HTTP execution layer (injected httpx
transport, mocked in tests). Tokens are constructor-injected per tenant and
are never logged, returned, or embedded in results.

Publishing is an irreversible external effect. Nothing in this module calls
``publish*`` except the approval-gated execution gate in ``scheduler.py``;
routes, drafting, and analytics never publish.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

# -- error taxonomy ----------------------------------------------------------


class AdapterError(RuntimeError):
    """Base error for official platform adapter failures."""


class AdapterAuthError(AdapterError):
    """Missing or rejected platform credentials. Fail closed, always."""


class AdapterRateLimitError(AdapterError):
    """The platform throttled the call; carries the retry hint when known."""

    def __init__(self, platform: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(f"{platform} rate limited the request")
        self.platform = platform
        self.retry_after_seconds = retry_after_seconds


class AdapterResponseError(AdapterError):
    """Any other non-2xx platform response or malformed payload."""


# -- value objects -----------------------------------------------------------


@dataclass(frozen=True)
class PlatformCredentials:
    """Per-tenant official-API credentials. ``None`` means not connected."""

    meta_access_token: str | None = None
    meta_ig_user_id: str | None = None
    x_bearer_token: str | None = None
    linkedin_access_token: str | None = None
    linkedin_org_id: str | None = None
    tiktok_access_token: str | None = None


@dataclass(frozen=True)
class PublishRequest:
    """One post to publish through an official API after human approval."""

    platform: str
    text: str
    format: str
    link: str | None = None
    media_urls: tuple[str, ...] = ()
    alt_texts: tuple[str, ...] = ()
    thread_chunks: tuple[str, ...] = ()  # X/Twitter threads only


@dataclass(frozen=True)
class PublishResult:
    """The platform's own record of the post it accepted."""

    platform: str
    external_id: str
    url: str | None = None
    draft_only: bool = False  # TikTok inbox flow: lands as an in-app draft


@dataclass(frozen=True)
class NormalizedMetrics:
    """Cross-platform view of one platform's engagement pull."""

    platform: str
    impressions: int = 0
    reach: int = 0
    engagement: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    follower_count: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


def _check_response(platform: str, response: httpx.Response) -> dict[str, Any]:
    """Map one HTTP response onto the error taxonomy; return parsed JSON."""
    if response.status_code in (401, 403):
        raise AdapterAuthError(f"{platform} rejected the injected credentials ({response.status_code})")
    if response.status_code == 429:
        retry = response.headers.get("retry-after")
        raise AdapterRateLimitError(platform, float(retry) if retry else None)
    if response.is_error:
        raise AdapterResponseError(f"{platform} request failed ({response.status_code})")
    try:
        body = response.json()
    except ValueError as error:
        raise AdapterResponseError(f"{platform} returned a non-JSON body") from error
    if not isinstance(body, dict):
        raise AdapterResponseError(f"{platform} returned an unexpected payload shape")
    return body


class _HttpLayer:
    """Shared injected-transport HTTP plumbing. No state, no credentials."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 30.0) -> None:
        self._transport = transport
        self._timeout = timeout

    async def _send(
        self,
        method: str,
        url: str,
        *,
        platform: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.request(method, url, headers=headers, params=params, json=json_body)
        except httpx.HTTPError as error:
            raise AdapterError(f"{platform} transport failure: {error.__class__.__name__}") from error
        return _check_response(platform, response)


# -- Meta Graph API (Instagram business accounts) ----------------------------


class MetaGraphAdapter(_HttpLayer):
    """Instagram publishing + insights over the official Meta Graph API."""

    BASE = "https://graph.facebook.com/v21.0"

    def __init__(
        self,
        *,
        access_token: str | None,
        ig_user_id: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(transport=transport, timeout=timeout)
        self._access_token = access_token
        self._ig_user_id = ig_user_id

    def _require_credentials(self) -> tuple[str, str]:
        if not self._access_token or not self._ig_user_id:
            raise AdapterAuthError("Meta Graph API token and IG user id are not configured")
        return self._access_token, self._ig_user_id

    # Pure payload builders -------------------------------------------------

    def build_single_container_payload(self, request: PublishRequest) -> dict[str, Any]:
        """IG container for a single image/video post."""
        payload: dict[str, Any] = {"caption": request.text}
        if request.format.startswith("video"):
            payload["media_type"] = "REELS"
            payload["video_url"] = request.media_urls[0] if request.media_urls else ""
        else:
            payload["image_url"] = request.media_urls[0] if request.media_urls else ""
        return payload

    def build_carousel_payloads(self, request: PublishRequest) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Child containers + the parent CAROUSEL container for a slide post."""
        children = [{"image_url": url, "is_carousel_item": True} for url in request.media_urls]
        parent: dict[str, Any] = {
            "media_type": "CAROUSEL",
            "caption": request.text,
            "children": [],  # filled with child container ids after each child POST
        }
        return children, parent

    # Network execution -----------------------------------------------------

    async def publish(self, request: PublishRequest) -> PublishResult:
        token, ig_user_id = self._require_credentials()
        headers = {"Authorization": f"Bearer {token}"}
        if request.format == "carousel" and len(request.media_urls) > 1:
            children, parent = self.build_carousel_payloads(request)
            child_ids = []
            for child in children:
                body = await self._send(
                    "POST", f"{self.BASE}/{ig_user_id}/media", platform="meta", headers=headers, json_body=child
                )
                child_ids.append(str(body["id"]))
            parent["children"] = ",".join(child_ids)
            container = await self._send(
                "POST", f"{self.BASE}/{ig_user_id}/media", platform="meta", headers=headers, json_body=parent
            )
        else:
            container = await self._send(
                "POST",
                f"{self.BASE}/{ig_user_id}/media",
                platform="meta",
                headers=headers,
                json_body=self.build_single_container_payload(request),
            )
        published = await self._send(
            "POST",
            f"{self.BASE}/{ig_user_id}/media_publish",
            platform="meta",
            headers=headers,
            json_body={"creation_id": container["id"]},
        )
        return PublishResult(platform="instagram", external_id=str(published["id"]))

    async def fetch_metrics(self, since_days: int) -> dict[str, Any]:
        token, ig_user_id = self._require_credentials()
        return await self._send(
            "GET",
            f"{self.BASE}/{ig_user_id}/insights",
            platform="meta",
            headers={"Authorization": f"Bearer {token}"},
            params={"metric": "impressions,reach,likes,comments,shares,saved", "period": "day"},
        )

    @staticmethod
    def normalize_metrics(raw: dict[str, Any]) -> NormalizedMetrics:
        totals: dict[str, int] = {}
        for entry in raw.get("data", []):
            name = entry.get("name")
            values = entry.get("values") or []
            totals[name] = sum(int(v.get("value", 0)) for v in values)
        return NormalizedMetrics(
            platform="instagram",
            impressions=totals.get("impressions", 0),
            reach=totals.get("reach", 0),
            likes=totals.get("likes", 0),
            comments=totals.get("comments", 0),
            shares=totals.get("shares", 0) + totals.get("saved", 0),
            engagement=totals.get("likes", 0) + totals.get("comments", 0) + totals.get("shares", 0) + totals.get("saved", 0),
            detail={"source": "meta-graph-api", "metrics": sorted(totals)},
        )


# -- X API v2 -----------------------------------------------------------------


class XApiV2Adapter(_HttpLayer):
    """Posting + account metrics over the official X API v2."""

    BASE = "https://api.twitter.com/2"

    def __init__(
        self,
        *,
        bearer_token: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(transport=transport, timeout=timeout)
        self._bearer_token = bearer_token

    def _require_credentials(self) -> str:
        if not self._bearer_token:
            raise AdapterAuthError("X API v2 bearer token is not configured")
        return self._bearer_token

    @staticmethod
    def build_tweet_payload(text: str, in_reply_to: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": text}
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        return payload

    async def publish(self, request: PublishRequest) -> PublishResult:
        token = self._require_credentials()
        headers = {"Authorization": f"Bearer {token}"}
        chunks = list(request.thread_chunks) if request.thread_chunks else [request.text]
        first_id: str | None = None
        previous_id: str | None = None
        for chunk in chunks:
            body = await self._send(
                "POST",
                f"{self.BASE}/tweets",
                platform="x",
                headers=headers,
                json_body=self.build_tweet_payload(chunk, previous_id),
            )
            tweet_id = str(body["data"]["id"])
            previous_id = tweet_id
            if first_id is None:
                first_id = tweet_id
        return PublishResult(
            platform="twitter",
            external_id=str(first_id),
            url=f"https://twitter.com/i/web/status/{first_id}",
        )

    async def fetch_metrics(self, since_days: int) -> dict[str, Any]:
        token = self._require_credentials()
        return await self._send(
            "GET",
            f"{self.BASE}/users/me",
            platform="x",
            headers={"Authorization": f"Bearer {token}"},
            params={"user.fields": "public_metrics"},
        )

    @staticmethod
    def normalize_metrics(raw: dict[str, Any]) -> NormalizedMetrics:
        metrics = (raw.get("data") or {}).get("public_metrics") or {}
        return NormalizedMetrics(
            platform="twitter",
            follower_count=int(metrics.get("followers_count", 0)),
            engagement=int(metrics.get("like_count", 0))
            + int(metrics.get("retweet_count", 0))
            + int(metrics.get("reply_count", 0)),
            likes=int(metrics.get("like_count", 0)),
            shares=int(metrics.get("retweet_count", 0)),
            comments=int(metrics.get("reply_count", 0)),
            detail={"source": "x-api-v2", "metrics": sorted(metrics)},
        )


# -- LinkedIn API --------------------------------------------------------------


class LinkedInAdapter(_HttpLayer):
    """Organization posting + share statistics over the official LinkedIn API."""

    BASE = "https://api.linkedin.com/v2"

    def __init__(
        self,
        *,
        access_token: str | None,
        organization_id: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(transport=transport, timeout=timeout)
        self._access_token = access_token
        self._organization_id = organization_id

    def _require_credentials(self) -> tuple[str, str]:
        if not self._access_token or not self._organization_id:
            raise AdapterAuthError("LinkedIn API token and organization id are not configured")
        return self._access_token, self._organization_id

    def build_ugc_post_payload(self, request: PublishRequest) -> dict[str, Any]:
        _, organization_id = self._require_credentials()
        return {
            "author": f"urn:li:organization:{organization_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": request.text},
                    "shareMediaCategory": "ARTICLE" if request.link else "NONE",
                    **({"media": [{"status": "READY", "originalUrl": request.link}]} if request.link else {}),
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

    async def publish(self, request: PublishRequest) -> PublishResult:
        token, _ = self._require_credentials()
        body = await self._send(
            "POST",
            f"{self.BASE}/ugcPosts",
            platform="linkedin",
            headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
            json_body=self.build_ugc_post_payload(request),
        )
        return PublishResult(platform="linkedin", external_id=str(body.get("id", "")))

    async def fetch_metrics(self, since_days: int) -> dict[str, Any]:
        token, organization_id = self._require_credentials()
        return await self._send(
            "GET",
            f"{self.BASE}/organizationalEntityShareStatistics",
            platform="linkedin",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": "organizationalEntity", "organizationalEntity": f"urn:li:organization:{organization_id}"},
        )

    @staticmethod
    def normalize_metrics(raw: dict[str, Any]) -> NormalizedMetrics:
        elements = raw.get("elements") or []
        stats = (elements[0] if elements else {}).get("totalShareStatistics") or {}
        return NormalizedMetrics(
            platform="linkedin",
            impressions=int(stats.get("impressionCount", 0)),
            likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            shares=int(stats.get("shareCount", 0)),
            engagement=int(stats.get("likeCount", 0))
            + int(stats.get("commentCount", 0))
            + int(stats.get("shareCount", 0))
            + int(stats.get("clickCount", 0)),
            detail={"source": "linkedin-api", "metrics": sorted(stats)},
        )


# -- TikTok Content Posting API -------------------------------------------------


class TikTokContentPostingAdapter(_HttpLayer):
    """TikTok's official Content Posting API, inbox (draft) flow only.

    The inbox flow delivers the video as a DRAFT inside the creator's own
    TikTok app; the human finishes editing and posts it there. That keeps
    final publication in human hands even after Atlas-level approval, which
    is the compliant shape for this platform. Direct-post scopes are not
    used.
    """

    BASE = "https://open.tiktokapis.com/v2"

    def __init__(
        self,
        *,
        access_token: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(transport=transport, timeout=timeout)
        self._access_token = access_token

    def _require_credentials(self) -> str:
        if not self._access_token:
            raise AdapterAuthError("TikTok Content Posting API token is not configured")
        return self._access_token

    @staticmethod
    def build_inbox_upload_payload(video_url: str) -> dict[str, Any]:
        return {
            "post_info": {},
            "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
        }

    async def publish(self, request: PublishRequest) -> PublishResult:
        token = self._require_credentials()
        if not request.media_urls:
            raise AdapterResponseError("tiktok inbox upload needs a video URL to pull from")
        body = await self._send(
            "POST",
            f"{self.BASE}/post/publish/inbox/video/upload/",
            platform="tiktok",
            headers={"Authorization": f"Bearer {token}"},
            json_body=self.build_inbox_upload_payload(request.media_urls[0]),
        )
        publish_id = str((body.get("data") or {}).get("publish_id", ""))
        return PublishResult(platform="tiktok", external_id=publish_id, draft_only=True)

    async def fetch_metrics(self, since_days: int) -> dict[str, Any]:
        token = self._require_credentials()
        return await self._send(
            "POST",
            f"{self.BASE}/video/list/",
            platform="tiktok",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "id,like_count,comment_count,share_count,view_count"},
            json_body={"max_count": 20},
        )

    @staticmethod
    def normalize_metrics(raw: dict[str, Any]) -> NormalizedMetrics:
        videos = (raw.get("data") or {}).get("videos") or []
        likes = sum(int(v.get("like_count", 0)) for v in videos)
        comments = sum(int(v.get("comment_count", 0)) for v in videos)
        shares = sum(int(v.get("share_count", 0)) for v in videos)
        views = sum(int(v.get("view_count", 0)) for v in videos)
        return NormalizedMetrics(
            platform="tiktok",
            impressions=views,
            likes=likes,
            comments=comments,
            shares=shares,
            engagement=likes + comments + shares,
            detail={"source": "tiktok-content-posting-api", "video_count": len(videos)},
        )


# -- registry ------------------------------------------------------------------

ADAPTER_TYPES: dict[str, type] = {
    "instagram": MetaGraphAdapter,
    "twitter": XApiV2Adapter,
    "tiktok": TikTokContentPostingAdapter,
    "linkedin": LinkedInAdapter,
}


def build_adapter(
    platform: str,
    credentials: PlatformCredentials,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 30.0,
) -> MetaGraphAdapter | XApiV2Adapter | LinkedInAdapter | TikTokContentPostingAdapter:
    """Construct the official adapter for one platform from tenant credentials."""
    if platform == "instagram":
        return MetaGraphAdapter(
            access_token=credentials.meta_access_token,
            ig_user_id=credentials.meta_ig_user_id,
            transport=transport,
            timeout=timeout,
        )
    if platform == "twitter":
        return XApiV2Adapter(bearer_token=credentials.x_bearer_token, transport=transport, timeout=timeout)
    if platform == "linkedin":
        return LinkedInAdapter(
            access_token=credentials.linkedin_access_token,
            organization_id=credentials.linkedin_org_id,
            transport=transport,
            timeout=timeout,
        )
    if platform == "tiktok":
        return TikTokContentPostingAdapter(
            access_token=credentials.tiktok_access_token, transport=transport, timeout=timeout
        )
    raise AdapterError(f"no official adapter is wired for {platform}")
