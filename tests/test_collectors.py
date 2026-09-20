import asyncio, json
import httpx
import pytest
from app.collectors.registry import COLLECTORS, build_collector
from app.collectors.social import YouTubeDataCollector
from app.collectors.channels import DiscordBotCollector

EXPECTED={"apify_instagram","bright_data_instagram","apollo_people","hunter_domain","gmail_newsletters","discord_invited_bot","x_api","youtube_data_api","public_instagram","public_scholarship_sites"}

def test_registry_has_only_approved_connector_names():
    assert EXPECTED <= COLLECTORS.keys()
    with pytest.raises(ValueError): build_collector("instagram_login_scraper")

def test_connector_config_is_free_first_and_paid_connectors_disabled():
    config=json.load(open("config/collection_connectors.json"))
    assert all((not row["enabled"]) or row["key"] == "scholarship-public-sites" for row in config["connectors"])
    assert config["policy"]["login_driven_scraping"] is False
    assert config["policy"]["ban_evasion"] is False
    assert next(row for row in config["connectors"] if row["key"] == "instagram-seeds-free")["cost"] == "free"

def test_youtube_normalizes_official_api_results(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY","test")
    def handler(request):
        assert request.url.host == "www.googleapis.com"
        return httpx.Response(200,json={"items":[{"id":{"videoId":"abc"},"snippet":{"title":"Winner advice"}}],"nextPageToken":"n"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await YouTubeDataCollector(client).collect({"query":"competition winner tips"})
    batch=asyncio.run(run())
    assert batch.cursor == "n" and batch.items[0].canonical_url.endswith("abc")

def test_discord_uses_bot_authorization(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN","test")
    def handler(request):
        assert request.headers["Authorization"] == "Bot test"
        return httpx.Response(200,json=[{"id":"9","content":"new opportunity"}])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await DiscordBotCollector(client).collect({"guild_id":"1","channel_ids":["2"]})
    batch=asyncio.run(run())
    assert batch.items[0].payload["provider"] == "discord_invited_bot"
