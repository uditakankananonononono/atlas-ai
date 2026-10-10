#!/usr/bin/env python3
"""Additive Ollama 8B profile generator; no model/hardware acceptance claim.

- 32GB-class model capacity/quality gap: the smaller model is not equivalent to the 32-GB profile.
- Owner-hardware-unverified: the profile has never run on the owner's actual hardware.
- Local-first applies ONLY where the override is applied; the default chain may still use HF_TOKEN. NO globally-local-only claim.

Builder did NOT execute this generator. The checked-in override was authored
statically; equality unverified until main-side run.
Nothing lands before independent audit and separate local runtime acceptance.

Apply with existing deploy/local/docker-compose.yml and the additive override,
using Docker Compose -f base -f override. Existing required secret references
are untouched; this script never reads process environment or credentials.
Ollama uses the existing providers.generate(..., provider='ollama') /api/chat and
OllamaBGEEmbeddingProvider /api/embed path. Select ollama explicitly; this profile
is not a global routing/fallback policy. No hosted endpoint is added.

Image and model weights must be available to the local runtime. No automatic
pull, download, startup or model inference occurs in this generator. The registry-resolved
ollama/ollama:latest@sha256:b86366bb528bbf7f1424435d165028497a5b69bf6ddb4fa5a87102e2b79f44fb index digest pins content, not runtime compatibility or model availability. Model
loading, memory fit, latency and quality on the owner's hardware are unverified.
Concurrency=1 bounds the Celery worker, not every API inference across processes.
The local base Compose only is targeted, not docker-compose.prod.yml.

Usage: python scripts/profile_small_local_model.py --profile
 deploy/local/ollama-small.env --output /new/path/override.yml
Writes only a new output file (exclusive creation); never overwrites base files.
"""
import argparse
from pathlib import Path

SETTINGS = {
    "ATLAS_EMBEDDING_PROVIDER": "ollama",
    "ATLAS_OLLAMA_MODEL": "llama3.1:8b",
    "ATLAS_OLLAMA_EMBEDDING_MODEL": "bge-m3",
    "ATLAS_OLLAMA_URL": "http://ollama-small:11434",
    "ATLAS_AI_CONCURRENCY": "1",
    "ATLAS_COLLECTOR_CONCURRENCY": "1",
    "ATLAS_BROWSER_CONCURRENCY": "1",
    "ATLAS_ALLOW_PAID": "false",
}


def read_profile(path):
    """Parse only the finite, non-secret settings for this specific profile."""
    raw = Path(path).read_text(encoding="utf-8")
    if len(raw) > 8192:
        raise ValueError("profile exceeds bound")
    settings = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in SETTINGS or key in settings:
            raise ValueError("unknown, duplicate or malformed profile key")
        if value != SETTINGS[key]:
            raise ValueError("unsupported profile value")
        settings[key] = value
    if settings != SETTINGS:
        raise ValueError("missing profile settings")
    return settings


def render_profile(settings):
    """Produce YAML for a fixed supported local profile, with actual forwarding."""
    if settings != SETTINGS:
        raise ValueError("only the supported bounded local profile is accepted")
    lines = ["# X13 additive local profile; statically authored counterpart, builder did not run generator.",
             "# 32GB-class model capacity/quality gap: the smaller model is not equivalent to the 32-GB profile.",
             "# Owner-hardware-unverified: the profile has never run on the owner's actual hardware.",
             "# Local-first applies ONLY where the override is applied; the default chain may still use HF_TOKEN. NO globally-local-only claim.",
             "services:", "  ollama-small:", "    image: ollama/ollama:latest@sha256:b86366bb528bbf7f1424435d165028497a5b69bf6ddb4fa5a87102e2b79f44fb",
             "    restart: unless-stopped", "    environment:",
             '      OLLAMA_NUM_PARALLEL: "1"', '      OLLAMA_MAX_LOADED_MODELS: "1"',
             "    volumes:", "      - atlas-small-ollama:/root/.ollama"]
    for service in ("api", "worker", "migrate"):
        lines.extend([f"  {service}:", "    environment:"])
        for key in SETTINGS:
            # Values are finite validated literals, never arbitrary YAML input.
            lines.append(f'      {key}: "{settings[key]}"')
        lines.extend(["    depends_on:", "      ollama-small:", "        condition: service_started"])
        if service == "worker":
            lines.extend(["    command:", "      - celery", "      - -A",
                          "      - app.workers.celery_app:celery_app", "      - worker",
                          "      - --concurrency=1", "      - --loglevel=INFO"])
    lines.extend(["volumes:", "  atlas-small-ollama: {}"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate an additive local Ollama override; no runtime verification")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rendered = render_profile(read_profile(args.profile))
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(rendered)
    print("generated override; not runtime-verified")


if __name__ == "__main__":
    main()
