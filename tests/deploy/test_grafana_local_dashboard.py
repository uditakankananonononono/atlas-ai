"""Hermetic acceptance for the X05 free substitute: Grafana OSS + Prometheus in local compose.

Named gap (verbatim, not covered and not claimed): Hosted/managed Grafana and production traffic dashboards

These tests read files only: no docker, no network, no paid API, no Grafana or
Prometheus process. They validate that the override is additions-only, OSS-only,
wired to the local api /metrics endpoint, and renders the unmodified repo
dashboard.json through a provisioned datasource whose uid matches every panel.
AUTHORED, NOT RUN by the builder.
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OVERRIDE = ROOT / "deploy" / "local" / "docker-compose.grafana.yml"
BASE = ROOT / "deploy" / "local" / "docker-compose.yml"
DASHBOARD = ROOT / "deploy" / "grafana" / "dashboard.json"
MAIN = ROOT / "backend" / "app" / "main.py"
METRICS = ROOT / "backend" / "app" / "platform" / "metrics.py"
GAP = "Hosted/managed Grafana and production traffic dashboards"
IDENT = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _load():
    override = yaml.safe_load(OVERRIDE.read_text())
    base = yaml.safe_load(BASE.read_text())
    dashboard = json.loads(DASHBOARD.read_text())
    return override, base, dashboard


def _config(override, name):
    return yaml.safe_load(override["configs"][name]["content"])


def test_override_is_additive_only_and_oss_images():
    override, base, _ = _load()
    assert set(override["services"]) == {"prometheus", "grafana"}
    assert not (set(override["services"]) & set(base["services"])), "override must not redefine base services"
    assert {"migrate", "api", "worker", "postgres", "redis"} <= set(base["services"]), "base compose read as reference"
    assert override["services"]["prometheus"]["image"]=="prom/prometheus:v2.54.1@sha256:f6639335d34a77d9d9db382b92eeb7fc00934be8eae81dbc03b31cfe90411a94"
    assert override["services"]["grafana"]["image"]=="grafana/grafana-oss:11.2.2@sha256:d5133220d770aba5cb655147b619fa8770b90f41d8489a821d33b1cd34d16f89"
    text = OVERRIDE.read_text().lower()
    for forbidden in ("grafana.net", "grafana.com", "cloud.", "api_key", "apikey"):
        assert forbidden not in text, f"hosted/paid marker {forbidden!r} must not appear in the local substitute"


def test_named_gap_is_stated_verbatim():
    assert GAP in OVERRIDE.read_text(), "gap must be written into the override comments verbatim"
    assert GAP in (__doc__ or ""), "gap must be written into this module docstring verbatim"


def test_prometheus_scrapes_local_api_metrics_endpoint():
    override, base, _ = _load()
    scrape = _config(override, "prometheus-local-config")
    jobs = {job["job_name"]: job for job in scrape["scrape_configs"]}
    assert jobs["atlas-api"]["metrics_path"] == "/metrics"
    assert jobs["atlas-api"]["static_configs"][0]["targets"] == ["api:8080"]
    api_command = " ".join(str(part) for part in base["services"]["api"]["command"])
    assert "--port" in api_command and "8080" in api_command, "target port must be the base api service port"
    assert '"/metrics"' in MAIN.read_text(), "atlas app must expose the /metrics route the scrape config points at"


def test_provisioned_datasource_matches_every_dashboard_panel():
    override, _, dashboard = _load()
    datasources = _config(override, "grafana-datasources")["datasources"]
    assert len(datasources) == 1
    ds = datasources[0]
    assert ds["uid"] == "atlas-prometheus" and ds["type"] == "prometheus"
    assert ds["url"] == "http://prometheus:9090", "datasource must point at the local prometheus container"
    assert dashboard["panels"], "dashboard must have panels"
    for panel in dashboard["panels"]:
        assert panel["datasource"]["uid"] == "atlas-prometheus", f"panel {panel['title']!r} datasource uid mismatch"
        assert panel["datasource"]["type"] == "prometheus"
        assert panel["targets"][0]["expr"].strip(), f"panel {panel['title']!r} has an empty query"


def test_same_repo_dashboard_mounted_readonly_into_provider_path():
    override, _, dashboard = _load()
    provider = _config(override, "grafana-dashboards-provider")["providers"][0]
    provider_path = provider["options"]["path"]
    mounts = override["services"]["grafana"]["volumes"]
    dashboard_mounts = [m for m in mounts if isinstance(m, str) and "dashboard.json" in m]
    assert len(dashboard_mounts) == 1, "exactly one dashboard.json mount, the unmodified repo file"
    source, target, mode = dashboard_mounts[0].rsplit(":", 2)
    assert source.endswith("../grafana/dashboard.json"), "mount source must be the repo's deploy/grafana/dashboard.json"
    assert target.startswith(provider_path + "/"), "mount target must live in the provisioned dashboards path"
    assert mode == "ro", "dashboard mount must be read-only so the repo file is never mutated"
    assert dashboard["uid"] == "atlas-operations" and dashboard["title"] == "Atlas Operations"
    assert len(dashboard["panels"]) >= 3


def test_every_dashboard_metric_is_emitted_by_the_local_app():
    _, _, dashboard = _load()
    metrics_source = METRICS.read_text()
    local_tokens = ("http_server_", "atlas_")
    for panel in dashboard["panels"]:
        expr = panel["targets"][0]["expr"]
        names = {token for token in IDENT.findall(expr) if token.startswith(local_tokens)}
        assert names, f"panel {panel['title']!r} references no local app metric"
        for name in names:
            base = name
            for suffix in ("_count", "_sum", "_bucket", "_total"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
                    break
            assert f"'{base}'" in metrics_source or f'"{base}"' in metrics_source, (
                f"panel {panel['title']!r} queries {name!r} but {base!r} is not defined in app metrics"
            )
        process_names = {token for token in IDENT.findall(expr) if token.startswith("process_")}
        for name in process_names:
            assert "ProcessCollector" in metrics_source, f"panel {panel['title']!r} needs {name!r} from ProcessCollector"


def test_local_only_access_and_no_plaintext_credentials():
    override, _, _ = _load()
    grafana = override["services"]["grafana"]
    assert grafana["ports"] == ["3000:3000"]
    assert override["services"]["prometheus"]["ports"] == ["9090:9090"]
    env = grafana["environment"]
    assert env["GF_USERS_ALLOW_SIGN_UP"] == "false"
    password = str(env["GF_SECURITY_ADMIN_PASSWORD"])
    assert password.startswith("${"), "admin password must come from the environment, not a committed literal"
    assert ":-" in password, "a local default is allowed only as an env-var default"
    assert "depends_on" in override["services"]["prometheus"], "scraper must start after the api it scrapes"
    assert grafana["depends_on"], "grafana must start after prometheus"
