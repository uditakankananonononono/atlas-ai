"""Tests for the official platform adapters.

Every HTTP call runs through httpx.MockTransport; no network. Covers the
publish success paths per platform, fail-closed credential handling, the
error taxonomy (401/403, 429, 5xx, malformed JSON), and metrics
normalization against each platform's real response shapes.
"""

from __future__ import annotations

import httpx
import pytest

from app.modules.m06_social_media_manager.adapters import (
    AdapterAuthError,
    AdapterError,
    AdapterRateLimitError,
    AdapterResponseError,
    LinkedInAdapter,
    MetaGraphAdapter,
    PlatformCredentials,
    PublishRequest,
    TikTokContentPostingAdapter,
    XApiV2Adapter,
    build_adapter,
)


def make_request(**overrides) -> PublishRequest:
    base = dict(platform="instagram", text="Launch day!", format="image", media_urls=("https://cdn.example.com/a.jpg",))
    base.update(overrides)
    return PublishRequest(**base)


# -- Meta Graph API -----------------------------------------------------------


@pytest.mark.anyio
async def test_meta_single_image_publish_creates_container_then_publishes():
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.read() and __import__("json").loads(request.read())))
        url = str(request.url)
        if url.endswith("/media"):
            return httpx.Response(200, json={"id": "container-1"})
        if url.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "post-9"})
        return httpx.Response(404, json={})

    adapter = MetaGraphAdapter(
        access_token="meta-token", ig_user_id="1784", transport=httpx.MockTransport(handler)
    )
    result = await adapter.publish(make_request())
    assert result.external_id == "post-9"
    assert result.platform == "instagram"
    # Container payload carries the caption + image URL; publish only gets the creation id.
    assert calls[0][2]["caption"] == "Launch day!"
    assert calls[0][2]["image_url"] == "https://cdn.example.com/a.jpg"
    assert calls[1][2] == {"creation_id": "container-1"}
    # Token travels as a header only.
    assert all("meta-token" not in str(call[2]) for call in calls)


@pytest.mark.anyio
async def test_meta_carousel_publishes_children_then_parent():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        bodies.append(json.loads(request.read()))
        return httpx.Response(200, json={"id": f"id-{len(bodies)}"})

    adapter = MetaGraphAdapter(
        access_token="meta-token", ig_user_id="1784", transport=httpx.MockTransport(handler)
    )
    request = make_request(
        format="carousel",
        media_urls=("https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg", "https://cdn.example.com/3.jpg"),
    )
    await adapter.publish(request)
    assert bodies[0]["is_carousel_item"] is True
    assert bodies[1]["is_carousel_item"] is True
    assert bodies[2]["is_carousel_item"] is True
    assert bodies[3]["media_type"] == "CAROUSEL"
    assert bodies[3]["children"] == "id-1,id-2,id-3"
    assert bodies[4] == {"creation_id": "id-4"}


@pytest.mark.anyio
async def test_meta_missing_credentials_fails_closed():
    adapter = MetaGraphAdapter(access_token=None, ig_user_id=None)
    with pytest.raises(AdapterAuthError):
        await adapter.publish(make_request())
    with pytest.raises(AdapterAuthError):
        await adapter.fetch_metrics(7)


@pytest.mark.anyio
async def test_meta_metrics_normalize_real_insights_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "impressions", "values": [{"value": 300}, {"value": 400}]},
                    {"name": "reach", "values": [{"value": 250}]},
                    {"name": "likes", "values": [{"value": 40}]},
                    {"name": "comments", "values": [{"value": 5}]},
                    {"name": "shares", "values": [{"value": 3}]},
                    {"name": "saved", "values": [{"value": 2}]},
                ]
            },
        )

    adapter = MetaGraphAdapter(
        access_token="t", ig_user_id="u", transport=httpx.MockTransport(handler)
    )
    raw = await adapter.fetch_metrics(7)
    metrics = adapter.normalize_metrics(raw)
    assert metrics.impressions == 700
    assert metrics.reach == 250
    assert metrics.engagement == 50


# -- X API v2 ------------------------------------------------------------------


@pytest.mark.anyio
async def test_x_thread_posts_chunks_in_reply_order():
    posted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        posted.append(json.loads(request.read()))
        return httpx.Response(200, json={"data": {"id": f"tweet-{len(posted)}"}})

    adapter = XApiV2Adapter(bearer_token="x-token", transport=httpx.MockTransport(handler))
    request = make_request(platform="twitter", format="thread", text="", thread_chunks=("one 1/3", "two 2/3", "three 3/3"))
    result = await adapter.publish(request)
    assert [p["text"] for p in posted] == ["one 1/3", "two 2/3", "three 3/3"]
    assert "reply" not in posted[0]
    assert posted[1]["reply"] == {"in_reply_to_tweet_id": "tweet-1"}
    assert posted[2]["reply"] == {"in_reply_to_tweet_id": "tweet-2"}
    assert result.external_id == "tweet-1"
    assert result.url == "https://twitter.com/i/web/status/tweet-1"


@pytest.mark.anyio
async def test_x_metrics_normalize_public_metrics():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"public_metrics": {"followers_count": 1234, "like_count": 10, "retweet_count": 3, "reply_count": 2}}},
        )

    adapter = XApiV2Adapter(bearer_token="x-token", transport=httpx.MockTransport(handler))
    metrics = adapter.normalize_metrics(await adapter.fetch_metrics(7))
    assert metrics.follower_count == 1234
    assert metrics.engagement == 15


@pytest.mark.anyio
async def test_x_missing_token_fails_closed():
    adapter = XApiV2Adapter(bearer_token=None)
    with pytest.raises(AdapterAuthError):
        await adapter.publish(make_request(platform="twitter", format="single", text="hi"))


# -- LinkedIn --------------------------------------------------------------------


@pytest.mark.anyio
async def test_linkedin_publish_builds_organization_ugc_post():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["body"] = json.loads(request.read())
        seen["protocol"] = request.headers.get("x-restli-protocol-version")
        return httpx.Response(200, json={"id": "urn:li:share:777"})

    adapter = LinkedInAdapter(
        access_token="li-token", organization_id="42", transport=httpx.MockTransport(handler)
    )
    result = await adapter.publish(make_request(platform="linkedin", format="article_post", text="Post", link="https://blog.example.com/x"))
    assert result.external_id == "urn:li:share:777"
    body = seen["body"]
    assert body["author"] == "urn:li:organization:42"
    content = body["specificContent"]["com.linkedin.ugc.ShareContent"]
    assert content["shareCommentary"]["text"] == "Post"
    assert content["shareMediaCategory"] == "ARTICLE"
    assert content["media"][0]["originalUrl"] == "https://blog.example.com/x"
    assert seen["protocol"] == "2.0.0"


@pytest.mark.anyio
async def test_linkedin_metrics_normalize_share_statistics():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"elements": [{"totalShareStatistics": {"impressionCount": 900, "likeCount": 20, "commentCount": 4, "shareCount": 6, "clickCount": 30}}]},
        )

    adapter = LinkedInAdapter(
        access_token="li-token", organization_id="42", transport=httpx.MockTransport(handler)
    )
    metrics = adapter.normalize_metrics(await adapter.fetch_metrics(7))
    assert metrics.impressions == 900
    assert metrics.engagement == 60


# -- TikTok Content Posting API ----------------------------------------------------


@pytest.mark.anyio
async def test_tiktok_publish_uses_inbox_draft_flow():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"data": {"publish_id": "v_inbox_123"}})

    adapter = TikTokContentPostingAdapter(access_token="tt-token", transport=httpx.MockTransport(handler))
    result = await adapter.publish(
        make_request(platform="tiktok", format="video_script_60s", media_urls=("https://cdn.example.com/v.mp4",))
    )
    # The inbox flow is used and the result is marked draft-only: the human
    # finishes the post inside the TikTok app.
    assert seen["url"].endswith("/v2/post/publish/inbox/video/upload/")
    assert seen["body"]["source_info"] == {"source": "PULL_FROM_URL", "video_url": "https://cdn.example.com/v.mp4"}
    assert result.draft_only is True
    assert result.external_id == "v_inbox_123"


@pytest.mark.anyio
async def test_tiktok_publish_without_video_url_fails():
    adapter = TikTokContentPostingAdapter(access_token="tt-token")
    with pytest.raises(AdapterResponseError):
        await adapter.publish(make_request(platform="tiktok", format="video_script_60s", media_urls=()))


@pytest.mark.anyio
async def test_tiktok_metrics_normalize_video_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"videos": [{"like_count": 10, "comment_count": 2, "share_count": 1, "view_count": 500}]}},
        )

    adapter = TikTokContentPostingAdapter(access_token="t", transport=httpx.MockTransport(handler))
    metrics = adapter.normalize_metrics(await adapter.fetch_metrics(7))
    assert metrics.impressions == 500
    assert metrics.engagement == 13


# -- error taxonomy -----------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("status,error", [(401, AdapterAuthError), (403, AdapterAuthError), (500, AdapterResponseError)])
async def test_http_errors_map_to_taxonomy(status, error):
    adapter = XApiV2Adapter(
        bearer_token="t", transport=httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    )
    with pytest.raises(error):
        await adapter.fetch_metrics(7)


@pytest.mark.anyio
async def test_rate_limit_carries_retry_after():
    adapter = XApiV2Adapter(
        bearer_token="t",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, json={}, headers={"retry-after": "120"})
        ),
    )
    with pytest.raises(AdapterRateLimitError) as excinfo:
        await adapter.fetch_metrics(7)
    assert excinfo.value.retry_after_seconds == 120.0
    assert excinfo.value.platform == "x"


@pytest.mark.anyio
async def test_non_json_body_is_a_response_error():
    adapter = XApiV2Adapter(
        bearer_token="t", transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>oops</html>"))
    )
    with pytest.raises(AdapterResponseError):
        await adapter.fetch_metrics(7)


# -- registry ------------------------------------------------------------------------


def test_build_adapter_constructs_each_platform():
    credentials = PlatformCredentials(
        meta_access_token="m", meta_ig_user_id="ig", x_bearer_token="x",
        linkedin_access_token="l", linkedin_org_id="o", tiktok_access_token="t",
    )
    assert isinstance(build_adapter("instagram", credentials), MetaGraphAdapter)
    assert isinstance(build_adapter("twitter", credentials), XApiV2Adapter)
    assert isinstance(build_adapter("linkedin", credentials), LinkedInAdapter)
    assert isinstance(build_adapter("tiktok", credentials), TikTokContentPostingAdapter)
    with pytest.raises(AdapterError):
        build_adapter("myspace", credentials)
