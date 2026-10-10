"""AUTHORED FIRST, NOT RUN. Hermetic tests for deploy/local/acceptance/compose_acceptance.py (X11).

The script is loaded by file path under a unique module name because the repository root also has
an unrelated compose_acceptance.py. Everything here uses fakes: no docker, no network, no sleeping.
Only git-tracked repo files (the compose file, the runbook, the script) and tmp_path are read.
These tests prove the script's decision logic. They do not prove a real docker host behaves as the
fakes assume; that is the stated gap of the substitute.
"""
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy/local/acceptance/compose_acceptance.py"
COMPOSE = REPO / "deploy/local/docker-compose.yml"
RUNBOOK = REPO / "docs/deployment/LOCAL_ACCEPTANCE_RUNBOOK.md"
GAP = "NOT_VERIFIED: OIDC login, persistence, TLS-proxy-LAN, backups, perf-load, task execution, other hosts, image provenance"
PROJECT = "atlas-acceptance"

SENTINELS = {
    "POSTGRES_PASSWORD": "pgSENTINELvalue-1111",
    "REDIS_PASSWORD": "redisSENTINELvalue-2222",
    "ATLAS_TOKEN_KEY": "tokenSENTINELvalue-3333",
    "ATLAS_API_KEY_ENCRYPTION_KEY": "enckeySENTINELvalue-4444",
    "ATLAS_OIDC_ISSUER": "https://issuer.example.test",
    "ATLAS_OIDC_AUDIENCE": "atlas-audience",
}
SECRET_VALUES = [v for k, v in SENTINELS.items() if k in (
    "POSTGRES_PASSWORD", "REDIS_PASSWORD", "ATLAS_TOKEN_KEY", "ATLAS_API_KEY_ENCRYPTION_KEY")]


def load():
    spec = importlib.util.spec_from_file_location("atlas_local_compose_acceptance", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ca():
    return load()


# ---------------------------------------------------------------- fakes

class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def ndjson(rows):
    return "\n".join(json.dumps(r) for r in rows) + "\n"


def healthy_rows():
    return [
        {"Service": "migrate", "State": "exited", "ExitCode": 0, "Health": ""},
        {"Service": "api", "State": "running", "ExitCode": 0, "Health": "healthy"},
        {"Service": "worker", "State": "running", "ExitCode": 0, "Health": ""},
        {"Service": "postgres", "State": "running", "ExitCode": 0, "Health": "healthy"},
        {"Service": "redis", "State": "running", "ExitCode": 0, "Health": "healthy"},
    ]


class FakeDocker:
    """Scripted docker. Every call is recorded; unknown commands fail the test loudly."""

    def __init__(self, ca, **over):
        self.ca = ca
        self.calls = []
        ok = lambda out="", err="": ca.CommandResult(0, out, err)  # noqa: E731
        self.resp = {
            "docker_version": ok("Docker version 27.0.0"),
            "compose_version": ok("Docker Compose version v2.29.0"),
            "config": ok(""),
            "ps_q": ok(""),
            "volume_q": ok(""),
            "up": ok("started"),
            "ps_json": ok(ndjson(healthy_rows())),
            "exec": ok("-> celery@worker: OK\n        pong\n"),
            "volume_names": ok(f"{PROJECT}_atlas-postgres\n{PROJECT}_atlas-redis\n"),
            "restart": ok(""),
            "logs": ok("log line"),
            "down": ok(""),
        }
        self.resp.update(over)

    @staticmethod
    def key(argv):
        if argv[:2] == ["docker", "--version"]:
            return "docker_version"
        if argv[:3] == ["docker", "compose", "version"]:
            return "compose_version"
        if argv[:3] == ["docker", "volume", "ls"]:
            return "volume_names" if "--format" in argv else "volume_q"
        if argv[:2] == ["docker", "compose"] and "--env-file" in argv:
            sub = argv[argv.index("--env-file") + 2:]
            if sub[0] == "ps":
                return "ps_q" if "-q" in sub else "ps_json"
            return sub[0]
        raise AssertionError(f"unexpected docker invocation: {argv}")

    def __call__(self, argv, timeout):
        assert isinstance(argv, list) and all(isinstance(a, str) for a in argv)
        self.calls.append(list(argv))
        value = self.resp[self.key(argv)]
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            return value(argv)
        if isinstance(value, list):  # sequence: pop front, repeat last
            item = value.pop(0) if len(value) > 1 else value[0]
            return item
        return value

    def keys(self):
        return [self.key(c) for c in self.calls]


class FakeHttp:
    def __init__(self, routes=None):
        self.routes = {
            "/health": [(200, '{"status":"ok"}')],
            "/ready": [(200, json.dumps({"status": "ready", "environment": "production",
                                         "checks": {"database": True, "redis": True, "migrations": True}}))],
            "/api/v1/product-orchestrator/goals/acceptance-probe": [(401, '{"detail":"OIDC bearer token required"}')],
        }
        if routes:
            self.routes.update(routes)
        self.calls = []

    def __call__(self, url, timeout):
        assert url.startswith("http://127.0.0.1:8000"), url
        path = url[len("http://127.0.0.1:8000"):]
        self.calls.append(path)
        seq = self.routes[path]
        return seq.pop(0) if len(seq) > 1 else seq[0]


def make_repo(tmp_path, env=None, env_text=None):
    repo = tmp_path / "repo"
    (repo / "deploy/local").mkdir(parents=True, exist_ok=True)
    (repo / "deploy/local/docker-compose.yml").write_text(COMPOSE.read_text())
    values = dict(SENTINELS if env is None else env)
    text = env_text if env_text is not None else "".join(f"{k}={v}\n" for k, v in values.items())
    (repo / "deploy/local/.env").write_text(text)
    return repo


def build(ca, tmp_path, docker=None, http=None, port_busy=False, keep=False, env=None, env_text=None, **kw):
    repo = make_repo(tmp_path, env=env, env_text=env_text)
    clock = FakeClock()
    docker = docker or FakeDocker(ca)
    http = http or FakeHttp()
    acc = ca.Acceptance(
        repo_root=repo, env_file=repo / "deploy/local/.env", runner=docker, http_get=http,
        port_in_use=lambda port: port_busy, sleep=clock.sleep, monotonic=clock.monotonic,
        keep=keep, log=lambda line: logs.append(line), **kw)
    logs = []
    acc._test_logs = logs
    return acc, docker, http, clock


def statuses(report):
    return {c.name: c.status for c in report.checks}


# ---------------------------------------------------------------- script facts and drift guards

def test_gap_statement_is_verbatim_in_module_docstring_and_constant(ca):
    doc = ast.get_docstring(ast.parse(SCRIPT.read_text()))
    assert GAP in doc
    assert ca.GAP_STATEMENT == GAP


def test_script_uses_only_the_standard_library():
    allowed = {"__future__", "argparse", "dataclasses", "json", "os", "pathlib", "re", "socket",
               "subprocess", "sys", "time", "typing", "urllib", "collections"}
    tree = ast.parse(SCRIPT.read_text())
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            seen |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            seen.add((node.module or "").split(".")[0])
    assert seen <= allowed, sorted(seen - allowed)


def test_required_env_matches_the_variables_the_compose_file_demands(ca):
    demanded = set(re.findall(r"\$\{([A-Z0-9_]+):\?", COMPOSE.read_text()))
    assert demanded, "compose file no longer has required variables; update the script"
    assert set(ca.REQUIRED_ENV) == demanded


def test_compose_facts_the_script_depends_on(ca):
    text = COMPOSE.read_text()
    assert re.search(rf'ports:\s*\["{ca.HOST_PORT}:8080"\]', text)
    services = re.findall(r"^  ([a-z]+):\s*$", text.split("services:", 1)[1].split("\nvolumes:", 1)[0], re.M)
    assert set(services) == set(ca.EXPECTED_SERVICES)
    assert "/ready" in text  # the api healthcheck the script's /ready check mirrors
    name = re.search(r"^name:\s*(\S+)", text, re.M).group(1)
    assert ca.PROJECT_NAME != name, "teardown project must differ from the compose file's own project"
    assert ca.PROJECT_NAME == PROJECT


# ---------------------------------------------------------------- pure helpers

def test_parse_env_file_handles_comments_quotes_export_and_equals_in_values(ca):
    text = "# c\n\nA=1\nexport B='two words'\nC=\"q\"\nD=x=y==\nE=\n  F = 6 \nnot a line\n"
    assert ca.parse_env_file(text) == {"A": "1", "B": "two words", "C": "q", "D": "x=y==", "E": "", "F": "6"}


def test_parse_env_file_never_interpolates(ca):
    assert ca.parse_env_file("A=$HOME\nB=${A}\n") == {"A": "$HOME", "B": "${A}"}


def test_validate_env_accepts_complete_env(ca):
    assert ca.validate_env(dict(SENTINELS)) == []


@pytest.mark.parametrize("key", sorted(SENTINELS))
def test_validate_env_rejects_missing_and_empty_each_required_key(ca, key):
    missing = {k: v for k, v in SENTINELS.items() if k != key}
    empty = {**SENTINELS, key: "  "}
    for env in (missing, empty):
        problems = ca.validate_env(env)
        assert problems and any(key in p for p in problems)


def test_validate_env_rejects_placeholders_without_echoing_values(ca):
    env = {**SENTINELS, "ATLAS_TOKEN_KEY": "CHANGE_ME_32_BYTE_RANDOM_SECRET"}
    problems = ca.validate_env(env)
    assert any("ATLAS_TOKEN_KEY" in p and "placeholder" in p.lower() for p in problems)
    assert not any("CHANGE_ME_32" in p for p in problems)


@pytest.mark.parametrize("key", ["POSTGRES_PASSWORD", "REDIS_PASSWORD"])
@pytest.mark.parametrize("bad", ["a@b", "a:b", "a/b", "a?b", "a#b", "a%b", "a b"])
def test_validate_env_rejects_url_unsafe_passwords_because_compose_puts_them_in_urls(ca, key, bad):
    problems = ca.validate_env({**SENTINELS, key: "xxxx" + bad + "yyyy"})
    assert any(key in p and "url" in p.lower() for p in problems)
    assert not any(bad in p for p in problems)


def test_parse_compose_ps_accepts_json_array_and_ndjson_and_empty(ca):
    rows = healthy_rows()
    assert ca.parse_compose_ps(json.dumps(rows)) == rows
    assert ca.parse_compose_ps(ndjson(rows)) == rows
    assert ca.parse_compose_ps("") == [] and ca.parse_compose_ps("\n  \n") == []


@pytest.mark.parametrize("garbage", ["not json", '{"a":1', "[1,2", '"str"', "42"])
def test_parse_compose_ps_rejects_garbage(ca, garbage):
    with pytest.raises(ValueError):
        ca.parse_compose_ps(garbage)


def test_evaluate_services_accepts_the_healthy_stack(ca):
    ok, problems = ca.evaluate_services(healthy_rows())
    assert ok is True and problems == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda r: r[1].update(Health="starting"), "api"),
    (lambda r: r[1].update(Health="unhealthy"), "api"),
    (lambda r: r[1].update(State="restarting"), "api"),
    (lambda r: r[0].update(ExitCode=1), "migrate"),
    (lambda r: r[0].update(State="running"), "migrate"),
    (lambda r: r[2].update(State="exited"), "worker"),
    (lambda r: r[2].update(State="restarting"), "worker"),
    (lambda r: r[3].update(Health=""), "postgres"),
    (lambda r: r[4].update(Health="unhealthy"), "redis"),
    (lambda r: r.pop(2), "worker"),
    (lambda r: r.pop(0), "migrate"),
])
def test_evaluate_services_rejects_each_broken_service(ca, mutate, needle):
    rows = healthy_rows()
    mutate(rows)
    ok, problems = ca.evaluate_services(rows)
    assert ok is False and any(needle in p for p in problems)


def test_evaluate_services_never_passes_an_empty_list(ca):
    assert ca.evaluate_services([])[0] is False


def test_redact_replaces_every_secret_occurrence_longest_first(ca):
    out = ca.redact("a pgSECRETlong b pgSECRET c", ["pgSECRET", "pgSECRETlong"])
    assert "pgSECRET" not in out and out.count("[REDACTED]") == 2


def test_redact_ignores_empty_and_tiny_values_instead_of_destroying_text(ca):
    assert ca.redact("hello world", ["", "a", "xy"]) == "hello world"


def test_secret_values_picks_secret_looking_keys_only(ca):
    env = {"POSTGRES_PASSWORD": "pppp1111", "ATLAS_TOKEN_KEY": "kkkk2222", "ATLAS_OIDC_AUDIENCE": "audience-x",
           "SOME_SECRET": "ssss3333", "OTHER": "ooooo"}
    assert set(ca.secret_values(env)) == {"pppp1111", "kkkk2222", "ssss3333"}


# ---------------------------------------------------------------- full runs with fakes

def test_happy_path_passes_every_check_and_tears_down_last(ca, tmp_path):
    acc, docker, http, clock = build(ca, tmp_path)
    report = acc.run()
    assert report.passed is True and report.exit_code == 0
    st = statuses(report)
    assert set(st.values()) == {"PASS"}
    for name in ("preconditions.docker", "preconditions.compose", "preconditions.env_file",
                 "preconditions.port_free", "compose.config", "preconditions.clean_project", "compose.up",
                 "services.state", "http.health", "http.ready", "http.auth_enforced", "worker.ping",
                 "volumes.exist", "restart.api_ready", "cleanup"):
        assert name in st, name
    keys = docker.keys()
    assert keys[-1] == "down" and keys.count("down") == 1 and keys.count("up") == 1
    assert keys.index("config") < keys.index("up") < keys.index("exec") < keys.index("restart") < keys.index("down")
    assert clock.sleeps == []  # healthy first poll: no waiting


def test_every_docker_call_is_scoped_to_the_acceptance_project_and_never_destructive_elsewhere(ca, tmp_path):
    acc, docker, http, clock = build(ca, tmp_path)
    acc.run()
    allowed_volume = {"ls"}
    for argv in docker.calls:
        assert argv[0] == "docker"
        if argv[1] == "compose" and argv[2] != "version":
            assert argv[2:4] == ["-p", PROJECT]
            assert argv[4] == "-f" and argv[5].endswith("deploy/local/docker-compose.yml")
            assert argv[6] == "--env-file"
        elif argv[1] == "volume":
            assert argv[2] in allowed_volume
            assert f"label=com.docker.compose.project={PROJECT}" in argv
        else:
            assert argv[1] in ("--version", "compose")
        assert not {"prune", "system", "rm", "--rmi", "kill", "stop"} & set(argv)
    down = [c for c in docker.calls if "down" in c[7:]][0]
    assert down[-3:] == ["down", "-v", "--remove-orphans"]


def test_secrets_never_reach_argv_logs_or_report_even_when_docker_output_contains_them(ca, tmp_path):
    leaky = ca.CommandResult(1, "db url postgresql://atlas:" + SENTINELS["POSTGRES_PASSWORD"] + "@x",
                             "token " + SENTINELS["ATLAS_TOKEN_KEY"])
    docker = FakeDocker(ca, up=leaky, logs=ca.CommandResult(0, " ".join(SECRET_VALUES), ""))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert report.passed is False
    blob = json.dumps(report.to_dict()) + "\n".join(acc._test_logs) + json.dumps(docker.calls)
    for secret in SECRET_VALUES:
        assert secret not in blob
    assert "[REDACTED]" in blob


def test_up_failure_fails_skips_the_rest_and_still_cleans_up_once(ca, tmp_path):
    docker = FakeDocker(ca, up=ca.CommandResult(1, "", "build failed"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    st = statuses(report)
    assert st["compose.up"] == "FAIL" and report.exit_code == 1
    for name in ("services.state", "http.health", "http.ready", "http.auth_enforced", "worker.ping",
                 "volumes.exist", "restart.api_ready"):
        assert st[name] == "SKIPPED", name
    assert docker.keys().count("down") == 1 and st["cleanup"] == "PASS"
    assert http.calls == []
    assert report.diagnostics  # compose logs were captured for the operator


def test_services_never_healthy_times_out_by_clock_not_by_real_sleep(ca, tmp_path):
    rows = healthy_rows()
    rows[1]["Health"] = "starting"
    docker = FakeDocker(ca, ps_json=ca.CommandResult(0, ndjson(rows), ""))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker, up_timeout=60, poll_interval=5)
    report = acc.run()
    assert statuses(report)["services.state"] == "FAIL"
    polls = docker.keys().count("ps_json")
    assert 2 <= polls <= 14
    assert clock.now >= 60 and all(s == 5 for s in clock.sleeps)
    assert statuses(report)["http.health"] == "SKIPPED" and http.calls == []
    assert docker.keys().count("down") == 1


def test_services_become_healthy_after_waiting_is_a_pass(ca, tmp_path):
    starting = healthy_rows()
    starting[1]["Health"] = "starting"
    docker = FakeDocker(ca, ps_json=[ca.CommandResult(0, ndjson(starting), ""),
                                     ca.CommandResult(0, ndjson(starting), ""),
                                     ca.CommandResult(0, ndjson(healthy_rows()), "")])
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert report.passed and len(clock.sleeps) == 2


def test_migrate_failure_is_reported_and_blocks_http_checks(ca, tmp_path):
    rows = healthy_rows()
    rows[0]["ExitCode"] = 1
    docker = FakeDocker(ca, ps_json=ca.CommandResult(0, ndjson(rows), ""))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker, up_timeout=10, poll_interval=5)
    report = acc.run()
    assert statuses(report)["services.state"] == "FAIL"
    assert "migrate" in next(c for c in report.checks if c.name == "services.state").detail
    assert http.calls == []


def test_health_must_be_200_with_status_ok(ca, tmp_path):
    for status, body in ((200, '{"status":"degraded"}'), (200, "ok"), (500, '{"status":"ok"}'), (None, "connection failed")):
        acc, docker, http, clock = build(ca, tmp_path, http=FakeHttp({"/health": [(status, body)]}))
        report = acc.run()
        assert statuses(report)["http.health"] == "FAIL", (status, body)
        assert report.exit_code == 1


def test_ready_503_names_the_failing_checks(ca, tmp_path):
    body = json.dumps({"detail": {"status": "not_ready", "checks": {"database": True, "redis": True, "migrations": False}}})
    acc, docker, http, clock = build(ca, tmp_path, http=FakeHttp({"/ready": [(503, body)]}), ready_timeout=20, poll_interval=5)
    report = acc.run()
    check = next(c for c in report.checks if c.name == "http.ready")
    assert check.status == "FAIL" and "migrations" in check.detail
    assert "database" not in check.detail.replace("checks", "")  # only failing names are listed
    assert docker.keys().count("down") == 1


@pytest.mark.parametrize("body", [
    {"status": "ready", "checks": {"database": True, "redis": True, "migrations": False}},
    {"status": "ready", "checks": {"database": True, "redis": True}},
    {"status": "not_ready", "checks": {"database": True, "redis": True, "migrations": True}},
    {"status": "ready"},
    {"status": "ready", "checks": {"database": "true", "redis": True, "migrations": True}},
])
def test_ready_200_is_not_trusted_without_a_fully_true_checks_body(ca, tmp_path, body):
    acc, docker, http, clock = build(ca, tmp_path, http=FakeHttp({"/ready": [(200, json.dumps(body))]}),
                                     ready_timeout=10, poll_interval=5)
    assert statuses(acc.run())["http.ready"] == "FAIL"


def test_ready_recovers_after_initial_503(ca, tmp_path):
    good = (200, json.dumps({"status": "ready", "checks": {"database": True, "redis": True, "migrations": True}}))
    acc, docker, http, clock = build(ca, tmp_path, http=FakeHttp({"/ready": [(503, "{}"), (503, "{}"), good]}))
    report = acc.run()
    assert statuses(report)["http.ready"] == "PASS" and report.passed


@pytest.mark.parametrize("status,expected", [(401, "PASS"), (200, "FAIL"), (403, "FAIL"), (404, "FAIL"),
                                              (500, "FAIL"), (None, "FAIL")])
def test_unauthenticated_protected_route_must_be_exactly_401(ca, tmp_path, status, expected):
    route = "/api/v1/product-orchestrator/goals/acceptance-probe"
    acc, docker, http, clock = build(ca, tmp_path, http=FakeHttp({route: [(status, "{}")]}))
    assert statuses(acc.run())["http.auth_enforced"] == expected


def test_auth_probe_sends_no_credentials_and_only_get(ca, tmp_path):
    seen = []

    def http(url, timeout):
        seen.append(url)
        return FakeHttp()(url, timeout)
    acc, docker, _, clock = build(ca, tmp_path, http=http)
    acc.run()
    assert all(u.startswith("http://127.0.0.1:8000/") for u in seen)
    assert not any("token" in u.lower() or "key" in u.lower() or "@" in u for u in seen)


@pytest.mark.parametrize("result", [
    ("rc1", 1, "pong"), ("no_pong", 0, "Error: no nodes replied"), ("empty", 0, ""),
])
def test_worker_must_answer_a_real_broker_ping(ca, tmp_path, result):
    _, rc, out = result
    docker = FakeDocker(ca, exec=ca.CommandResult(rc, out, ""))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    assert statuses(acc.run())["worker.ping"] == "FAIL"


def test_worker_ping_runs_celery_inspect_in_the_worker_service(ca, tmp_path):
    acc, docker, http, clock = build(ca, tmp_path)
    acc.run()
    call = next(c for c in docker.calls if "exec" in c[7:])
    tail = call[call.index("exec"):]
    assert tail[:3] == ["exec", "-T", "worker"] and "inspect" in tail and "ping" in tail
    assert "app.workers.celery_app:celery_app" in tail


@pytest.mark.parametrize("names", ["", f"{PROJECT}_atlas-postgres\n", f"{PROJECT}_atlas-redis\n",
                                   "other_atlas-postgres\nother_atlas-redis\n"])
def test_declared_volumes_must_exist_for_this_project(ca, tmp_path, names):
    docker = FakeDocker(ca, volume_names=ca.CommandResult(0, names, ""))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    assert statuses(acc.run())["volumes.exist"] == "FAIL"


def test_api_restart_must_return_to_ready(ca, tmp_path):
    good = (200, json.dumps({"status": "ready", "checks": {"database": True, "redis": True, "migrations": True}}))
    bad = (503, "{}")
    # first readiness passes, then the post-restart readiness never does
    http = FakeHttp({"/ready": [good, bad]})
    acc, docker, _, clock = build(ca, tmp_path, http=http, ready_timeout=10, poll_interval=5)
    st = statuses(acc.run())
    assert st["http.ready"] == "PASS" and st["restart.api_ready"] == "FAIL"


def test_restart_command_failure_fails_the_restart_check(ca, tmp_path):
    docker = FakeDocker(ca, restart=ca.CommandResult(1, "", "no such service"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    assert statuses(acc.run())["restart.api_ready"] == "FAIL"


def test_cleanup_failure_fails_the_run_even_when_every_check_passed(ca, tmp_path):
    docker = FakeDocker(ca, down=ca.CommandResult(1, "", "cannot remove"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert statuses(report)["cleanup"] == "FAIL" and report.passed is False and report.exit_code == 1


def test_keep_flag_skips_teardown_and_says_so(ca, tmp_path):
    acc, docker, http, clock = build(ca, tmp_path, keep=True)
    report = acc.run()
    assert "down" not in docker.keys()
    assert statuses(report)["cleanup"] == "SKIPPED"
    assert report.passed is True  # checks passed; the operator chose to keep the stack
    assert "left running" in next(c for c in report.checks if c.name == "cleanup").detail


# ---------------------------------------------------------------- refusals: nothing started, nothing torn down

def assert_untouched(docker):
    keys = docker.keys()
    assert "up" not in keys and "down" not in keys and "restart" not in keys and "exec" not in keys


def test_missing_docker_cli_is_a_clear_failure_and_touches_nothing(ca, tmp_path):
    docker = FakeDocker(ca, docker_version=FileNotFoundError("docker"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert statuses(report)["preconditions.docker"] == "FAIL" and report.exit_code == 1
    assert "not found" in next(c for c in report.checks if c.name == "preconditions.docker").detail.lower()
    assert docker.keys() == ["docker_version"]


def test_compose_v2_plugin_missing_is_a_failure(ca, tmp_path):
    docker = FakeDocker(ca, compose_version=ca.CommandResult(1, "", "docker: 'compose' is not a docker command"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    assert statuses(acc.run())["preconditions.compose"] == "FAIL"
    assert_untouched(docker)


def test_placeholder_env_refuses_before_any_compose_command(ca, tmp_path):
    env = {**SENTINELS, "POSTGRES_PASSWORD": "CHANGE_ME_LONG_RANDOM_PASSWORD"}
    acc, docker, http, clock = build(ca, tmp_path, env=env)
    report = acc.run()
    assert statuses(report)["preconditions.env_file"] == "FAIL" and report.exit_code == 1
    assert set(docker.keys()) <= {"docker_version", "compose_version"}
    assert_untouched(docker)


def test_absent_env_file_refuses(ca, tmp_path):
    repo = make_repo(tmp_path)
    (repo / "deploy/local/.env").unlink()
    docker = FakeDocker(ca)
    acc = ca.Acceptance(repo_root=repo, env_file=repo / "deploy/local/.env", runner=docker, http_get=FakeHttp(),
                        port_in_use=lambda p: False, sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    report = acc.run()
    assert statuses(report)["preconditions.env_file"] == "FAIL"
    assert_untouched(docker)


def test_absent_compose_file_refuses(ca, tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    (repo / "e.env").write_text("".join(f"{k}={v}\n" for k, v in SENTINELS.items()))
    docker = FakeDocker(ca)
    acc = ca.Acceptance(repo_root=repo, env_file=repo / "e.env", runner=docker, http_get=FakeHttp(),
                        port_in_use=lambda p: False, sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    report = acc.run()
    assert report.exit_code == 1 and report.passed is False
    assert_untouched(docker)


def test_port_in_use_refuses_without_touching_anything(ca, tmp_path):
    acc, docker, http, clock = build(ca, tmp_path, port_busy=True)
    report = acc.run()
    assert statuses(report)["preconditions.port_free"] == "FAIL"
    assert "8000" in next(c for c in report.checks if c.name == "preconditions.port_free").detail
    assert_untouched(docker)


@pytest.mark.parametrize("key", ["ps_q", "volume_q"])
def test_existing_acceptance_project_state_is_never_adopted_or_deleted(ca, tmp_path, key):
    docker = FakeDocker(ca)
    docker.resp[key] = ca.CommandResult(0, "abc123\n", "")
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert statuses(report)["preconditions.clean_project"] == "FAIL" and report.exit_code == 1
    assert_untouched(docker)  # in particular: no `down -v` on something this run did not create


def test_compose_config_failure_refuses_and_touches_nothing(ca, tmp_path):
    docker = FakeDocker(ca, config=ca.CommandResult(1, "", "required variable missing"))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    assert statuses(acc.run())["compose.config"] == "FAIL"
    assert_untouched(docker)


def test_runner_timeout_or_oserror_becomes_a_failed_check_not_a_crash(ca, tmp_path):
    import subprocess
    docker = FakeDocker(ca, up=subprocess.TimeoutExpired(cmd="docker", timeout=1))
    acc, docker, http, clock = build(ca, tmp_path, docker=docker)
    report = acc.run()
    assert statuses(report)["compose.up"] == "FAIL" and report.exit_code == 1
    assert docker.keys().count("down") == 1  # up was attempted, so the project is cleaned


# ---------------------------------------------------------------- report honesty

def test_report_states_what_was_not_verified_and_the_gap(ca, tmp_path):
    acc, *_ = build(ca, tmp_path)
    data = acc.run().to_dict()
    assert data["gap"] == GAP and data["project"] == PROJECT
    text = " ".join(data["not_verified"]).lower()
    for topic in ("oidc", "persist", "tls", "backup"):
        assert topic in text, topic
    assert data["result"] == "PASS"
    assert {c["status"] for c in data["checks"]} == {"PASS"}


def test_report_result_is_fail_if_any_check_failed(ca, tmp_path):
    acc, *_ = build(ca, tmp_path, http=FakeHttp({"/health": [(500, "")]}))
    data = acc.run().to_dict()
    assert data["result"] == "FAIL"


def test_a_failure_never_produces_a_passing_exit_code_or_pass_summary(ca, tmp_path):
    acc, *_ = build(ca, tmp_path, port_busy=True)
    report = acc.run()
    assert report.exit_code != 0
    assert not any("acceptance passed" in l.lower() for l in acc._test_logs)


# ---------------------------------------------------------------- CLI

def test_main_writes_report_returns_exit_code_and_leaks_no_secrets(ca, tmp_path):
    repo = make_repo(tmp_path)
    out = tmp_path / "report.json"
    docker = FakeDocker(ca)
    code = ca.main(["--repo-root", str(repo), "--env-file", str(repo / "deploy/local/.env"), "--report", str(out)],
                   runner=docker, http_get=FakeHttp(), port_in_use=lambda p: False,
                   sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    assert code == 0
    data = json.loads(out.read_text())
    assert data["result"] == "PASS"
    assert not any(s in out.read_text() for s in SECRET_VALUES)


def test_main_returns_nonzero_when_a_check_fails(ca, tmp_path):
    repo = make_repo(tmp_path)
    code = ca.main(["--repo-root", str(repo), "--env-file", str(repo / "deploy/local/.env")],
                   runner=FakeDocker(ca), http_get=FakeHttp({"/health": [(500, "")]}), port_in_use=lambda p: False,
                   sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    assert code == 1


def test_main_default_env_file_is_deploy_local_dot_env_inside_repo_root(ca, tmp_path):
    repo = make_repo(tmp_path)
    docker = FakeDocker(ca)
    ca.main(["--repo-root", str(repo)], runner=docker, http_get=FakeHttp(), port_in_use=lambda p: False,
            sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    cfg = next(c for c in docker.calls if "config" in c[7:])
    assert cfg[cfg.index("--env-file") + 1] == str(repo / "deploy/local/.env")


def test_main_keep_flag_is_honoured(ca, tmp_path):
    repo = make_repo(tmp_path)
    docker = FakeDocker(ca)
    ca.main(["--repo-root", str(repo), "--keep"], runner=docker, http_get=FakeHttp(), port_in_use=lambda p: False,
            sleep=lambda s: None, monotonic=lambda: 0.0, log=lambda l: None)
    assert "down" not in docker.keys()


# ---------------------------------------------------------------- runbook

def test_runbook_exists_states_the_gap_and_the_exact_commands():
    text = RUNBOOK.read_text()
    assert GAP in text
    assert "python deploy/local/acceptance/compose_acceptance.py" in text
    assert PROJECT in text and "deploy/local/.env.example" in text
    assert "down -v" in text and "only" in text.lower()
    for topic in ("Prerequisites", "What the script checks", "What it does not check", "Reading the result", "Cleanup"):
        assert topic in text, topic


def test_runbook_does_not_claim_the_script_has_been_run_or_passed():
    low = RUNBOOK.read_text().lower()
    for phrase in ("has been run", "was run successfully", "verified on", "passed on a real", "tested on"):
        assert phrase not in low, phrase


def test_runbook_lists_every_check_name_the_script_emits(ca, tmp_path):
    acc, *_ = build(ca, tmp_path)
    names = [c.name for c in acc.run().checks]
    text = RUNBOOK.read_text()
    for name in names:
        assert name in text, name


def test_runbook_never_asks_for_secrets_in_chat_or_commit():
    low = RUNBOOK.read_text().lower()
    assert "do not commit" in low and ".env" in low
    assert "paste" not in low or "never paste" in low


# Named fresh-builder repair regressions, authored NOT RUN.
def test_make_repo_repeated_same_fixture_root_is_safe(tmp_path):
    first = make_repo(tmp_path)
    (first / 'preserved-marker').write_text('keep')
    second = make_repo(tmp_path, env={**SENTINELS, 'ATLAS_OIDC_AUDIENCE': 'updated-audience'})
    assert first == second
    assert (second / 'preserved-marker').read_text() == 'keep'
    assert 'updated-audience' in (second / 'deploy/local/.env').read_text()
    assert (second / 'deploy/local/docker-compose.yml').read_text() == COMPOSE.read_text()


def test_actual_not_verified_list_is_explicit_in_module_runbook_and_report(ca, tmp_path):
    expected = ('OIDC login', 'persistence', 'TLS-proxy-LAN', 'backups', 'perf-load',
                'task execution', 'other hosts', 'image provenance')
    doc = ast.get_docstring(ast.parse(SCRIPT.read_text()))
    runbook = RUNBOOK.read_text()
    report = build(ca, tmp_path)[0].run().to_dict()
    for topic in expected:
        assert topic in doc
        assert topic in runbook
        assert topic in ca.GAP_STATEMENT
        assert topic in report['gap']
    for text in (doc, runbook, ca.GAP_STATEMENT):
        assert ('Nothing beyond ' + 'executing it on a real host') not in text
    assert len(report['not_verified']) == 8
