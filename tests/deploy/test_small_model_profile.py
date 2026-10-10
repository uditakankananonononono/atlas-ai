"""X13 acceptance authored first, NOT RUN by builder; peer owns runtime audit."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/profile_small_local_model.py"
PROFILE = ROOT / "deploy/local/ollama-small.env"
ARTIFACT = ROOT / "deploy/local/docker-compose.ollama-small.yml"
BASE_FILES = [ROOT / path for path in (
    "deploy/local/docker-compose.yml", "deploy/local/ollama-32gb.env",
    "ollama-32gb.env", "tests/test_missing_production_capabilities.py",
)]


def load_generator():
    spec = importlib.util.spec_from_file_location("x13_profile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_matches_static_artifact_and_does_not_edit_base():
    before = {path: path.read_bytes() for path in BASE_FILES}
    module = load_generator()
    rendered = module.render_profile(module.read_profile(PROFILE))
    assert rendered.encode("utf-8") == ARTIFACT.read_bytes()
    document = yaml.safe_load(rendered)
    services = document["services"]
    ollama = services["ollama-small"]
    assert ollama["image"] == "ollama/ollama:latest@sha256:b86366bb528bbf7f1424435d165028497a5b69bf6ddb4fa5a87102e2b79f44fb"
    assert "ports" not in ollama
    assert ollama["environment"] == {"OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1"}
    assert ollama["volumes"] == ["atlas-small-ollama:/root/.ollama"]
    expected = module.read_profile(PROFILE)
    for service in ("api", "worker", "migrate"):
        assert services[service]["environment"] == expected
        assert services[service]["depends_on"] == {"ollama-small": {"condition": "service_started"}}
    assert services["worker"]["command"] == [
        "celery", "-A", "app.workers.celery_app:celery_app", "worker", "--concurrency=1", "--loglevel=INFO",
    ]
    assert expected["ATLAS_OLLAMA_MODEL"] == "llama3.1:8b"
    assert expected["ATLAS_OLLAMA_URL"] == "http://ollama-small:11434"
    assert expected["ATLAS_EMBEDDING_PROVIDER"] == "ollama"
    assert expected["ATLAS_ALLOW_PAID"] == "false"
    assert {path: path.read_bytes() for path in BASE_FILES} == before


def test_cli_writes_only_new_explicit_path_and_refuses_overwrite(tmp_path):
    output = tmp_path / "new-override.yml"
    before = {path: path.read_bytes() for path in BASE_FILES}
    args = [sys.executable, str(SCRIPT), "--profile", str(PROFILE), "--output", str(output)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=10,
                            env={"PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == ARTIFACT.read_bytes()
    duplicate = subprocess.run(args, capture_output=True, text=True, timeout=10,
                               env={"PYTHONDONTWRITEBYTECODE": "1"})
    assert duplicate.returncode != 0
    assert output.read_bytes() == ARTIFACT.read_bytes()
    assert {path: path.read_bytes() for path in BASE_FILES} == before
    assert "generated override" in result.stdout
    assert "tested" not in result.stdout.lower()


@pytest.mark.parametrize("replacement", [
    "ATLAS_OLLAMA_MODEL=llama3.1:70b", "ATLAS_OLLAMA_URL=https://cloud.invalid",
    "ATLAS_AI_CONCURRENCY=8", "ATLAS_ALLOW_PAID=true",
])
def test_invalid_profile_denies_before_output(tmp_path, replacement):
    module = load_generator()
    key = replacement.split("=", 1)[0]
    lines = PROFILE.read_text().splitlines()
    changed = "\n".join(replacement if line.startswith(key + "=") else line for line in lines) + "\n"
    path = tmp_path / "bad.env"
    path.write_text(changed)
    with pytest.raises(ValueError):
        module.render_profile(module.read_profile(path))


def test_duplicate_unknown_and_missing_settings_rejected(tmp_path):
    module = load_generator()
    original = PROFILE.read_text()
    variants = [original + "ATLAS_AI_CONCURRENCY=1\n", original + "UNKNOWN=anything\n",
                "\n".join(line for line in original.splitlines() if not line.startswith("ATLAS_OLLAMA_MODEL="))]
    for text in variants:
        path = tmp_path / "invalid.env"
        path.write_text(text)
        with pytest.raises(ValueError):
            module.read_profile(path)


def test_override_merges_without_replacing_existing_dependencies():
    # Compose merges service environment and dependency maps by key. Check the
    # additive declarations against the real base, not an invented compose stub.
    base = yaml.safe_load(BASE_FILES[0].read_text())
    override = yaml.safe_load(ARTIFACT.read_text())
    assert set(override["services"]) == {"api", "worker", "migrate", "ollama-small"}
    for name in ("api", "worker", "migrate"):
        merged_env = {**base["services"][name]["environment"], **override["services"][name]["environment"]}
        assert merged_env["ATLAS_ENV"] == "production"
        assert "ATLAS_DATABASE_URL" in merged_env and "ATLAS_TOKEN_KEY" in merged_env
        merged_dependencies = {**base["services"][name]["depends_on"], **override["services"][name]["depends_on"]}
        assert {"postgres", "redis", "ollama-small"} <= set(merged_dependencies)
    assert "migrate" in base["services"]["api"]["depends_on"]
    assert "migrate" in base["services"]["worker"]["depends_on"]


@pytest.mark.parametrize("change", [
    {"ATLAS_OLLAMA_MODEL": "llama3.1:70b"}, {"ATLAS_AI_CONCURRENCY": "8"},
    {"ATLAS_OLLAMA_URL": "https://external.invalid"}, {"ATLAS_ALLOW_PAID": "true"},
    {"UNKNOWN": "anything"},
])
def test_direct_render_altered_dict_refused(change):
    module = load_generator()
    altered = dict(module.SETTINGS)
    altered.update(change)
    with pytest.raises(ValueError):
        module.render_profile(altered)


def test_direct_render_missing_key_refused():
    module = load_generator()
    altered = dict(module.SETTINGS)
    del altered["ATLAS_OLLAMA_MODEL"]
    with pytest.raises(ValueError):
        module.render_profile(altered)


def test_header_carries_all_three_gaps():
    header = ARTIFACT.read_text().split("services:", 1)[0]
    assert "32GB-class model capacity/quality gap: the smaller model is not equivalent to the 32-GB profile." in header
    assert "Owner-hardware-unverified: the profile has never run on the owner's actual hardware." in header
    assert "Local-first applies ONLY where the override is applied; the default chain may still use HF_TOKEN. NO globally-local-only claim." in header
