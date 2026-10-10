"""Source-occurrence contract for free-tier secret NAMES (no values). Text matching only; the exact
8-space `sync: false` string is an intentional, accepted tripwire against reformatting."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW_NAMES = {"ATLAS_TOKEN_KEY", "ATLAS_API_KEY_ENCRYPTION_KEY"}


def _compose_required_names():
    compose = (ROOT / "docker-compose.prod.yml").read_text()
    block = compose.split("x-atlas-env:", 1)[1].split("x-worker:", 1)[0]
    return set(re.findall(r"^\s+(ATLAS_[A-Z_]+):\s*\$\{[A-Z_]+:\?", block, re.M))


def test_compose_requires_the_expected_atlas_secret_names():
    assert NEW_NAMES <= _compose_required_names()


def test_render_declares_every_compose_required_name_as_unsynced_secret():
    render = (ROOT / "render.yaml").read_text()
    for name in _compose_required_names():
        assert f"- key: {name}\n        sync: false" in render, name


def test_free_tier_example_lists_names_and_new_secrets_have_no_value():
    example = (ROOT / ".env.free-tier.example").read_text()
    for name in _compose_required_names():
        assert re.search(rf"^{name}=", example, re.M), name
    for name in NEW_NAMES:
        assert re.search(rf"^{name}=$", example, re.M), name


def test_free_tier_doc_names_the_new_secrets():
    docs = (ROOT / "docs/deployment/FREE_TIER.md").read_text()
    for name in NEW_NAMES:
        assert name in docs, name
