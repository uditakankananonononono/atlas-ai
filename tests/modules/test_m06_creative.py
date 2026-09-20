"""Per-row tests for the rows 281-305 creative-discipline specifications.

One mounted-endpoint test per ledger row, plus boundary tests: imitation
redaction, asset-prompt engine filtering, the never-rendered disclaimer, and
provider failure handling. All LLM calls are mocked; nothing renders.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m06_social_media_manager.creative import CREATIVE_SPECS, RENDER_DISCLAIMER
from app.modules.m06_social_media_manager.models import AUDIO_ENGINE, IMAGE_ENGINE
from app.modules.m06_social_media_manager.routes import get_service, router
from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service

SLUGS = sorted(CREATIVE_SPECS, key=lambda s: CREATIVE_SPECS[s].row)
CREATIVE_INPUT = {"business": "Acme Robotics", "subject": "Kit-1 launch teaser",
                  "goals": ["wishlist signups"], "facts": {"audience": "STEM educators"}}


def generic_sections(prompt: str) -> dict:
    keys = re.findall(r'"([a-z_]+)"', prompt.split("ONLY a JSON object with keys:")[-1].split(".")[0])
    sections: dict = {}
    for key in keys:
        if key == "asset_prompts":
            sections[key] = [
                {"kind": "image", "engine": IMAGE_ENGINE, "prompt": "robot kit on a desk"},
                {"kind": "image", "engine": "midjourney", "prompt": "third-party engine"},
                {"kind": "audio", "engine": AUDIO_ENGINE, "prompt": "soft synth stinger"},
            ]
        else:
            sections[key] = f"draft {key}"
    return sections


def make_client(generate=None):
    repository = MemorySocialRepository()

    async def default_generate(prompt, provider, model=None):
        return "fake-model", json.dumps(generic_sections(prompt))

    service = Service(approval_store=None, generate=generate or default_generate,
                      metrics_client=None, repository=repository)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), repository


@pytest.mark.parametrize("slug", SLUGS, ids=SLUGS)
def test_row_creative_spec_endpoint(slug):
    client, repository = make_client()
    response = client.post(f"/api/v1/social-media-manager/creative/{slug}", json=CREATIVE_INPUT)
    assert response.status_code == 200
    body = response.json()
    spec = CREATIVE_SPECS[slug]
    assert body["row"] == spec.row and body["kind"] == slug and body["title"] == spec.title
    assert body["status"] == "draft"
    for key in spec.section_keys:
        assert key in body["sections"], f"{slug}: missing section {key}"
    # Never-rendered boundary, machine-readable on every artifact.
    assert body["sections"]["_deliverable"] == "specification"
    assert body["sections"]["_disclaimer"] == RENDER_DISCLAIMER
    stored = repository.get_artifact(body["id"])
    assert stored is not None and stored.kind == slug


def test_asset_prompts_limited_to_self_hosted_engines():
    client, _ = make_client()
    response = client.post("/api/v1/social-media-manager/creative/3d-modeling", json=CREATIVE_INPUT)
    prompts = response.json()["sections"]["asset_prompts"]
    engines = {p["engine"] for p in prompts}
    assert engines == {IMAGE_ENGINE, AUDIO_ENGINE}  # midjourney prompt dropped
    assert all(p["kind"] in ("image", "audio") for p in prompts)


def test_style_imitation_is_redacted_and_recorded():
    async def generate(prompt, provider, model=None):
        return "m", json.dumps({
            "palette": [{"hex": "#3366ff", "role": "primary"}],
            "rationale": "Cold and corporate, in the style of Mark Rothko meets IBM",
            "accessibility": "check contrast",
            "usage": "social headers",
        })

    client, _ = make_client(generate)
    response = client.post("/api/v1/social-media-manager/creative/color-theory", json=CREATIVE_INPUT)
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert "Rothko" not in sections["rationale"]
    assert "IBM" not in sections["rationale"]
    assert "original treatment" in sections["rationale"]
    assert sections["originality_notes"]  # redaction recorded on the artifact


def test_clean_output_has_no_originality_notes():
    client, _ = make_client()
    response = client.post("/api/v1/social-media-manager/creative/typography", json=CREATIVE_INPUT)
    assert "originality_notes" not in response.json()["sections"]


def test_malformed_llm_reply_is_502():
    async def generate(prompt, provider, model=None):
        return "m", "not json"

    client, _ = make_client(generate)
    assert client.post("/api/v1/social-media-manager/creative/logo-design", json=CREATIVE_INPUT).status_code == 502


def test_provider_failure_is_503():
    from app.core.providers import ProviderError

    async def generate(prompt, provider, model=None):
        raise ProviderError("no key configured")

    client, _ = make_client(generate)
    assert client.post("/api/v1/social-media-manager/creative/logo-design", json=CREATIVE_INPUT).status_code == 503


def test_creative_artifacts_visible_in_shared_listing():
    client, _ = make_client()
    client.post("/api/v1/social-media-manager/creative/ui-ux-design", json=CREATIVE_INPUT)
    listed = client.get("/api/v1/social-media-manager/marketing/artifacts?kind=ui-ux-design").json()
    assert len(listed) == 1 and listed[0]["row"] == 287
