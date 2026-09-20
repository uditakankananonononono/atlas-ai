"""Per-row tests for the rows 400-426 marketing analyses and plans.

One mounted-endpoint test per ledger row, plus honesty/safety tests:
deterministic sample-size math, no fabricated keyword metrics, no invented
outreach targets, compliance-gated copy, draft-only editorial calendars, and
provider failure handling. All network and LLM calls are mocked.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from statistics import NormalDist

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m06_social_media_manager.marketing import ARTIFACT_SPECS, MarketingArtifact
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.routes import get_analytics, get_scheduler, get_service, router
from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
GENERIC_SLUGS = [s for s in ARTIFACT_SPECS if s not in ("copywriting", "editorial-calendar")]


def generic_sections(prompt: str) -> dict:
    """Build a JSON reply shaped to whatever keys the prompt demanded."""
    keys = re.findall(r'"([a-z_]+)"', prompt.split("ONLY a JSON object with keys:")[-1].split(".")[0])
    sections: dict = {}
    for key in keys:
        if key == "keywords":
            sections[key] = [{"term": "beta testing tools", "intent": "commercial", "volume": 99999}]
        elif key in ("targets", "candidates"):
            sections[key] = [{"name": "Invented Prospect", "angle": "pitch"}]
        else:
            sections[key] = f"draft {key}"
    return sections


def make_client(generate=None):
    repository = MemorySocialRepository()

    async def default_generate(prompt, provider, model=None):
        if "ONLY a JSON object with keys:" in prompt:
            return "fake-model", json.dumps(generic_sections(prompt))
        return "fake-model", '{"twitter": {"format": "thread", "copy": "Thread copy"}}'

    service = Service(
        approval_store=None, generate=generate or default_generate,
        metrics_client=None, repository=repository,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), repository


def post(client: TestClient, path: str, payload: dict) -> object:
    return client.post(f"/api/v1/social-media-manager{path}", json=payload)


GENERIC_INPUT = {"business": "Acme Robotics", "product": "Kit-1", "audience": "STEM educators",
                 "goals": ["waitlist signups"], "facts": {"users": "400 schools"}}


# -- row 400: sample size ----------------------------------------------------

def test_row_400_sample_size_exact_math():
    client, _ = make_client()
    response = post(client, "/marketing/sample-size",
                    {"baseline_rate": 0.1, "minimum_detectable_effect": 0.02})
    assert response.status_code == 200
    body = response.json()
    assert body["row"] == 400 and body["kind"] == "sample-size"
    assert body["status"] == "draft" and body["provenance"] == "computed"
    normal = NormalDist()
    z = normal.inv_cdf(0.975) + normal.inv_cdf(0.8)
    expected = math.ceil(z * z * (0.1 * 0.9 + 0.12 * 0.88) / 0.02**2)
    assert body["sections"]["per_variant"] == expected
    assert body["sections"]["total"] == expected * 2


def test_row_400_sample_size_rejects_impossible_mde():
    client, _ = make_client()
    response = post(client, "/marketing/sample-size",
                    {"baseline_rate": 0.99, "minimum_detectable_effect": 0.5})
    assert response.status_code == 422


# -- rows 401-426 generic drafts ---------------------------------------------

@pytest.mark.parametrize("slug", GENERIC_SLUGS, ids=GENERIC_SLUGS)
def test_row_generic_artifact_endpoint(slug):
    client, repository = make_client()
    response = post(client, f"/marketing/{slug}", GENERIC_INPUT)
    assert response.status_code == 200
    body = response.json()
    spec = ARTIFACT_SPECS[slug]
    assert body["row"] == spec.row and body["kind"] == slug and body["title"] == spec.title
    assert body["status"] == "draft"
    for key in spec.section_keys:
        assert key in body["sections"], f"{slug}: missing section {key}"
    stored = repository.get_artifact(body["id"])
    assert stored is not None and stored.kind == slug


# -- row 407: copywriting through the compliance gate ------------------------

def test_row_407_copywriting_success_with_findings():
    client, _ = make_client()
    response = post(client, "/marketing/copywriting",
                    {"brief": "Announce the Kit-1 launch", "platform": "twitter"})
    assert response.status_code == 200
    body = response.json()
    assert body["artifact"]["row"] == 407 and body["artifact"]["status"] == "draft"
    assert body["artifact"]["sections"]["copy"]
    assert all(f["severity"] != "error" for f in body["findings"])


def test_row_407_copywriting_sponsored_without_disclosure_is_422_and_unstored():
    async def generate(prompt, provider, model=None):
        return "m", json.dumps({"copy": "Big brand collab, no disclosure", "headline_options": [], "call_to_action": "buy"})

    client, repository = make_client(generate)
    response = post(client, "/marketing/copywriting",
                    {"brief": "Brand collab", "platform": "instagram", "sponsored": True})
    assert response.status_code == 422
    codes = [i["code"] for i in response.json()["detail"]]
    assert "missing_disclosure" in codes
    assert repository.list_artifacts("copywriting") == []


# -- row 409: editorial calendar stays draft-only ----------------------------

def test_row_409_editorial_calendar_drafts_only():
    async def generate(prompt, provider, model=None):
        return "m", json.dumps({
            "entries": [
                {"date": "2026-10-01", "title": "Launch teaser", "theme": "launch",
                 "platform": "instagram", "format": "carousel", "summary": "tease"},
                {"date": "not-a-date", "title": "broken"},
                {"date": "2026-10-03", "title": "Devlog", "theme": "build",
                 "platform": "twitter", "format": "thread", "summary": "progress"},
            ],
            "themes": ["launch", "build"],
        })

    client, repository = make_client(generate)
    response = post(client, "/marketing/editorial-calendar",
                    {"business": "Acme Robotics", "themes": ["launch", "build"],
                     "start_date": "2026-10-01", "weeks": 1, "posts_per_week": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["row"] == 409
    entries = body["sections"]["entries"]
    assert len(entries) == 2  # malformed date dropped
    assert all(e["status"] == "draft" for e in entries)
    assert "scheduling_note" in body["sections"]
    assert repository.list_schedules() == []  # nothing entered the scheduler


def test_row_409_editorial_calendar_rejects_bad_start_date():
    client, _ = make_client()
    response = post(client, "/marketing/editorial-calendar",
                    {"business": "Acme", "themes": ["x"], "start_date": "October 1"})
    assert response.status_code == 422


# -- honesty guards ------------------------------------------------------------

def test_keyword_research_strips_unprovided_volumes():
    client, _ = make_client()
    response = post(client, "/marketing/keyword-research", GENERIC_INPUT)
    keyword = response.json()["sections"]["keywords"][0]
    assert keyword["volume"] is None  # LLM-claimed 99999 stripped: not caller-provided


def test_keyword_research_keeps_caller_provided_volumes():
    client, _ = make_client()
    payload = dict(GENERIC_INPUT, provided_metrics={"beta testing tools": {"volume": 1200}})
    response = post(client, "/marketing/keyword-research", payload)
    assert response.json()["sections"]["keywords"][0]["volume"] == 1200


def test_link_building_without_prospects_names_nobody():
    client, _ = make_client()
    response = post(client, "/marketing/link-building", GENERIC_INPUT)
    sections = response.json()["sections"]
    assert sections["targets"] == []
    assert "never invents" in sections["targets_note"]


def test_link_building_targets_limited_to_provided_prospects():
    async def generate(prompt, provider, model=None):
        return "m", json.dumps({"targets": [
            {"name": "Invented Prospect", "angle": "x"},
            {"name": "STEM Blog Weekly", "angle": "guest post"},
        ], "angles": [], "outreach_drafts": []})

    client, _ = make_client(generate)
    payload = dict(GENERIC_INPUT, contacts=["STEM Blog Weekly"])
    response = post(client, "/marketing/link-building", payload)
    targets = response.json()["sections"]["targets"]
    assert [t["name"] for t in targets] == ["STEM Blog Weekly"]


# -- failure paths --------------------------------------------------------------

def test_malformed_llm_reply_is_502():
    async def generate(prompt, provider, model=None):
        return "m", "no json here at all"

    client, _ = make_client(generate)
    response = post(client, "/marketing/segmentation", GENERIC_INPUT)
    assert response.status_code == 502


def test_provider_failure_is_503():
    from app.core.providers import ProviderError

    async def generate(prompt, provider, model=None):
        raise ProviderError("no key configured")

    client, _ = make_client(generate)
    response = post(client, "/marketing/segmentation", GENERIC_INPUT)
    assert response.status_code == 503


def test_artifact_listing_filters_by_kind():
    client, _ = make_client()
    post(client, "/marketing/segmentation", GENERIC_INPUT)
    post(client, "/marketing/targeting", GENERIC_INPUT)
    listed = client.get("/api/v1/social-media-manager/marketing/artifacts?kind=targeting").json()
    assert len(listed) == 1 and listed[0]["kind"] == "targeting"
    assert len(client.get("/api/v1/social-media-manager/marketing/artifacts").json()) == 2


def test_sql_repository_artifact_round_trip_is_tenant_scoped(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'m6.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    repo_a, repo_b = SqlSocialRepository("a", sessions), SqlSocialRepository("b", sessions)
    artifact = MarketingArtifact(id="mkt-1", row=401, kind="segmentation", title="Segmentation Analysis",
                                 sections={"segments": []}, inputs={"business": "Acme"}, created_at=NOW)
    repo_a.save_artifact(artifact)
    loaded = repo_a.get_artifact("mkt-1")
    assert loaded.title == "Segmentation Analysis" and loaded.created_at == NOW
    assert [a.kind for a in repo_a.list_artifacts()] == ["segmentation"]
    assert repo_b.get_artifact("mkt-1") is None and repo_b.list_artifacts() == []
