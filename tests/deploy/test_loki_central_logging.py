"""Authored-not-run: hermetic config tests, not container acceptance evidence."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def configurations():
    compose = yaml.safe_load((ROOT / "deploy/local/docker-compose.loki.yml").read_text())
    promtail = yaml.safe_load((ROOT / "deploy/loki/promtail-local.yaml").read_text())
    base = yaml.safe_load((ROOT / "deploy/local/docker-compose.yml").read_text())
    return compose, promtail, base


def test_additive_override_activates_both_bootstrap_startup_paths():
    compose, _, base = configurations()
    for name in ("api", "worker"):
        assert name in base["services"]
        assert compose["services"][name]["command"] == ["python", "-m", "app.platform.logging_bootstrap", name]
        assert "environment" not in compose["services"][name]
        assert "build" not in compose["services"][name]
        driver = compose["services"][name]["logging"]
        assert driver["driver"] == "json-file"
        assert driver["options"] == {"max-size": "10m", "max-file": "3"}
    assert set(compose["services"]) == {"api", "worker", "loki", "promtail"}


def test_local_loki_storage_schema_retention_and_loopback_only_exposure():
    compose, _, _ = configurations()
    loki = compose["services"]["loki"]
    assert loki["image"] == "grafana/loki:3.5.0"
    assert loki["ports"] == ["127.0.0.1:3100:3100"]
    assert "atlas-loki:/loki" in loki["volumes"]
    config = yaml.safe_load(compose["configs"]["atlas-loki-local"]["content"])
    assert config["auth_enabled"] is False
    assert config["common"]["replication_factor"] == 1
    assert config["common"]["ring"]["kvstore"]["store"] == "inmemory"
    assert config["common"]["storage"]["filesystem"]["chunks_directory"] == "/loki/chunks"
    schema, = config["schema_config"]["configs"]
    assert schema == {"from": "2024-01-01", "store": "tsdb", "object_store": "filesystem",
                      "schema": "v13", "index": {"prefix": "index_", "period": "24h"}}
    assert config["limits_config"]["retention_period"] == "72h"
    assert config["compactor"]["retention_enabled"] is True
    assert config["compactor"]["delete_request_store"] == "filesystem"
    assert "googlecloud" not in config


def test_promtail_reads_only_explicit_app_container_log_directories_no_socket():
    compose, promtail, _ = configurations()
    collector = compose["services"]["promtail"]
    assert collector["image"] == "grafana/promtail:3.5.0"
    mounts = collector["volumes"]
    assert "${ATLAS_API_DOCKER_LOG_DIR:?set API container log directory}:/logs/api:ro" in mounts
    assert "${ATLAS_WORKER_DOCKER_LOG_DIR:?set worker container log directory}:/logs/worker:ro" in mounts
    assert not any("docker.sock" in mount for mount in mounts)
    assert "atlas-promtail-positions:/positions" in mounts
    assert promtail["positions"]["filename"] == "/positions/positions.yaml"
    assert promtail["clients"][0]["url"] == "http://loki:3100/loki/api/v1/push"
    assert set(collector["depends_on"]) == {"loki"}
    assert "ports" not in collector


def test_pipeline_unwraps_docker_then_parses_but_never_rewrites_schema_line():
    _, config, _ = configurations()
    jobs = config["scrape_configs"]
    assert {j["job_name"] for j in jobs} == {"atlas-api-json", "atlas-worker-json"}
    for job in jobs:
        static, = job["static_configs"]
        assert static["targets"] == ["localhost"]
        kind = static["labels"]["component"]
        assert kind in {"api", "worker"}
        assert static["labels"]["__path__"] == f"/logs/{kind}/*-json.log"
        stages = job["pipeline_stages"]
        assert stages == [{"docker": {}}, {"json": {"expressions": {
            "severity": "severity", "logger": "logger", "service": "service"}}},
            {"labels": {"severity": None, "service": None}}]
        assert not any("output" in stage or "drop" in stage for stage in stages)
        assert all("trace_id" not in stage.get("labels", {}) for stage in stages)
        assert static["labels"]["job"] == "atlas-local-json"


def test_gaps_and_manual_binding_requirements_are_explicit():
    source = (ROOT / "backend/app/platform/logging_bootstrap.py").read_text()
    assert "Google Cloud Logging sink, GCP alerting, log-based metrics. The bootstrap wires JSON logging at startup; it does NOT change existing services' default config, and no log pipeline is added to the collector." in source
    text = (ROOT / "deploy/local/docker-compose.loki.yml").read_text()
    assert "ATLAS_API_DOCKER_LOG_DIR" in text and "ATLAS_WORKER_DOCKER_LOG_DIR" in text
    assert "Compose 2.23.1" in text
    assert "container recreation" in text
