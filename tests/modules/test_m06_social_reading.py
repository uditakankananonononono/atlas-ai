"""Social reading layer: parsers, knowledge store, reader runs, idea harvest."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m06_social_media_manager.social_reading.idea_feed import (
    harvest_signals, score_signal)
from app.modules.m06_social_media_manager.social_reading.knowledge import KnowledgeStore
from app.modules.m06_social_media_manager.social_reading.parsers import (
    parse_linkedin_connections, parse_linkedin_feed)
from app.modules.m06_social_media_manager.social_reading.reader import SocialReader
from app.modules.m13_browser_agent.session_bridge.protocol import (
    BlockKind, CommandKind, PlatformBlocked)
from app.modules.m19_idea_incubator.ledger import LedgerService
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository

CONNECTIONS_HTML = """
<html><body>
<ul>
  <li class="mn-connection-card">
    <a class="mn-connection-card__link" href="/in/priya-builds/">
      <span class="mn-connection-card__name">Priya Sharma</span>
      <span class="mn-connection-card__occupation">Founder, robotics startup</span>
    </a>
  </li>
  <li class="mn-connection-card">
    <a class="mn-connection-card__link" href="/in/arjun-labs?miniProfileUrn=x">
      <span class="mn-connection-card__name">Arjun Mehta</span>
      <span class="mn-connection-card__occupation">PhD, ML systems</span>
    </a>
  </li>
</ul>
</body></html>
"""

FEED_HTML = """
<html><body>
<div class="feed-shared-update-v2" data-urn="urn:li:activity:111">
  <span class="update-components-actor__name">Priya Sharma</span>
  <div class="update-components-text">We just launched our first prototype robot arm.</div>
  <a href="/posts/priya_arm">post</a>
</div>
<div class="feed-shared-update-v2" data-urn="urn:li:activity:222">
  <span class="update-components-actor__name">Arjun Mehta</span>
  <div class="update-components-text">Happy birthday to my sister!</div>
</div>
</body></html>
"""


def test_parse_linkedin_connections():
    people = parse_linkedin_connections(CONNECTIONS_HTML)
    assert len(people) == 2
    assert people[0]["handle"] == "priya-builds"
    assert people[0]["display_name"] == "Priya Sharma"
    assert people[0]["bio"] == "Founder, robotics startup"
    assert people[0]["external_url"] == "https://www.linkedin.com/in/priya-builds/"
    assert people[1]["handle"] == "arjun-labs"


def test_parse_linkedin_feed():
    posts = parse_linkedin_feed(FEED_HTML)
    assert len(posts) == 2
    assert posts[0]["external_id"] == "urn:li:activity:111"
    assert "launched" in posts[0]["text"]
    assert posts[0]["source_url"] == "https://www.linkedin.com/posts/priya_arm"


def test_parsers_degrade_gracefully_on_unknown_markup():
    assert parse_linkedin_connections("<html><body>nothing here</body></html>") == []
    assert parse_linkedin_feed("<html><body>nothing here</body></html>") == []


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'social.db'}")
    Base.metadata.create_all(engine)
    return KnowledgeStore(sessionmaker(bind=engine, expire_on_commit=False))


def test_knowledge_dedupes_people_and_work(store):
    store.upsert_person("t", platform="instagram", handle="priya", display_name="Priya")
    store.upsert_person("t", platform="instagram", handle="priya", bio="robotics founder")
    people = store.list_people("t")
    assert len(people) == 1
    assert people[0]["display_name"] == "Priya"
    assert people[0]["bio"] == "robotics founder"  # second read enriched, not duplicated

    _, created = store.record_work("t", platform="instagram", handle="priya",
                                   external_id="abc123", text="launched a thing",
                                   source_url="https://www.instagram.com/p/abc123/")
    assert created
    _, created = store.record_work("t", platform="instagram", handle="priya",
                                   external_id="abc123", text="launched a thing",
                                   source_url="https://www.instagram.com/p/abc123/")
    assert not created  # idempotent re-read

    dossier = store.get_person("t", "instagram", "priya")
    assert len(dossier["works"]) == 1
    assert store.get_person("t", "instagram", "nobody") is None
    # tenant isolation
    assert store.list_people("other-tenant") == []


class FakePage:
    def __init__(self, html_by_url):
        self.html_by_url = html_by_url
        self.url = "about:blank"

    async def goto(self, url, wait_until="domcontentloaded"):
        self.url = url

    async def content(self):
        return self.html_by_url[self.url]


class FakeSessions:
    """BridgedSessions-shaped fake: LinkedIn via pages, Instagram via _execute."""

    def __init__(self, html_by_url=None, social_result=None, blocked=None):
        self.page_html = html_by_url or {}
        self.social_result = social_result
        self.blocked = blocked

    async def page(self, tenant_id, session_id, persistent=False):
        if self.blocked:
            raise self.blocked
        return FakePage(self.page_html)

    async def _execute(self, tenant_id, device_id, local, kind, args, timeout=60.0):
        if self.blocked:
            raise self.blocked
        assert kind is CommandKind.SOCIAL_READ
        return self.social_result


@pytest.mark.asyncio
async def test_linkedin_read_run(store):
    reader = SocialReader(FakeSessions({
        "https://www.linkedin.com/mynetwork/invite-connect/connections/": CONNECTIONS_HTML,
        "https://www.linkedin.com/feed/": FEED_HTML,
    }), store)
    result = await reader.run("t", platform="linkedin", operation="connections",
                              session_id="pc.dev1.main")
    assert result["count"] == 2
    assert {p["handle"] for p in store.list_people("t", platform="linkedin")} == {"priya-builds", "arjun-labs"}
    result = await reader.run("t", platform="linkedin", operation="feed",
                              session_id="pc.dev1.main")
    assert result["count"] == 2 and result["new"] == 2
    result = await reader.run("t", platform="linkedin", operation="feed",
                              session_id="pc.dev1.main")
    assert result["new"] == 0  # re-read is idempotent
    runs = store.list_runs("t")
    assert [r["state"] for r in runs] == ["complete", "complete", "complete"]


@pytest.mark.asyncio
async def test_instagram_followers_via_daemon(store):
    social_result = {"platform": "instagram", "op": "followers", "account": "udita",
                     "people": [{"handle": "priya", "display_name": "Priya", "bio": "founder",
                                 "external_url": "https://www.instagram.com/priya/"}],
                     "count": 1, "truncated": False}
    reader = SocialReader(FakeSessions(social_result=social_result), store)
    result = await reader.run("t", platform="instagram", operation="followers",
                              session_id="pc.dev1.main", instagram_username="udita")
    assert result["count"] == 1
    people = store.list_people("t", platform="instagram")
    assert people[0]["handle"] == "priya" and people[0]["relation"] == "follower"


@pytest.mark.asyncio
async def test_blocked_run_is_recorded_and_raised(store):
    blocked = PlatformBlocked(BlockKind.RATE_LIMIT, "Instagram throttled the read")
    reader = SocialReader(FakeSessions(blocked=blocked), store)
    with pytest.raises(PlatformBlocked) as caught:
        await reader.run("t", platform="instagram", operation="followers",
                         session_id="pc.dev1.main", instagram_username="udita")
    assert caught.value.kind is BlockKind.RATE_LIMIT
    runs = store.list_runs("t")
    assert runs[0]["state"] == "blocked"
    assert runs[0]["detail"]["block"] == "rate_limit"


def test_score_signal():
    assert score_signal("We launched our prototype and filed a patent!") >= 0.5
    assert score_signal("Happy birthday!") == 0.0
    assert score_signal("") == 0.0


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'ideas.db'}")
    Base.metadata.create_all(engine)
    return LedgerService(SqlIdeaRepository("t", sessionmaker(bind=engine, expire_on_commit=False)),
                         "tester")


def test_harvest_signals_into_ideas(store, ledger):
    store.record_work("t", platform="linkedin", handle="Priya Sharma",
                      external_id="urn:li:activity:111",
                      text="We just launched our first prototype robot arm.",
                      source_url="https://www.linkedin.com/posts/priya_arm",
                      observed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
                      signal_score=score_signal("We just launched our first prototype robot arm."))
    store.record_work("t", platform="linkedin", handle="Arjun Mehta",
                      external_id="urn:li:activity:222", text="Happy birthday to my sister!",
                      source_url="", signal_score=0.0)

    result = harvest_signals(store, ledger, "t", min_score=0.25)
    assert result["created_count"] == 1
    idea = ledger.dossier(result["created"][0]["idea_id"]).idea
    assert "Priya Sharma" in idea.title or "linkedin" in idea.tags
    assert idea.metadata["source_url"] == "https://www.linkedin.com/posts/priya_arm"
    assert idea.stage.value == "captured"

    # Harvesting again creates nothing: the signal is already linked.
    result = harvest_signals(store, ledger, "t", min_score=0.25)
    assert result["created_count"] == 0
