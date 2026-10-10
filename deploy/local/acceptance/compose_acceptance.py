#!/usr/bin/env python3
"""Single-machine Docker Compose acceptance for the Atlas local stack (unit X11, free substitute).

What this is: a script an operator runs on their own machine. It starts the stack defined by
deploy/local/docker-compose.yml under its own compose project name (atlas-acceptance), checks that
the stack actually came up and behaves as that file declares, writes a JSON report, and removes only
what it created. It uses Docker, the Python standard library and this repository. No paid service,
account, cloud resource or large-memory hardware is involved.

What it checks (each is a named check in the report):
  - docker and the compose v2 plugin are available; the env file has every variable the compose
    file demands, none still a CHANGE_ME placeholder, and URL-safe database/cache passwords;
  - host port 8000 is free and no earlier atlas-acceptance containers or volumes exist;
  - `docker compose config` accepts the file; `up -d --build` succeeds;
  - migrate exited 0; api, postgres and redis are healthy; worker is running;
  - GET /health returns {"status":"ok"}; GET /ready returns 200 with database, redis and migrations
    all true; an unauthenticated request to a protected route is rejected with 401;
  - the worker answers a Celery broker ping (a real round trip through Redis);
  - the project's two declared volumes exist; restarting api returns it to ready;
  - teardown (`down -v --remove-orphans`) of this project only.

What it honestly cannot cover (named gap, verbatim): NOT_VERIFIED: OIDC login, persistence, TLS-proxy-LAN, backups, perf-load, task execution, other hosts, image provenance

In practice that means: this file and its tests were authored without running Docker, and the unit
tests use fakes, so they prove the script's decision logic only. Whether a given machine's Docker,
network and images behave the way the checks assume is shown only by running the script there.
The report lists what a passing run still does not show (see NOT_VERIFIED).

Safety properties: every compose command carries the fixed project name and the compose file and env
file paths; secrets are read from the env file, passed by file path (never on a command line), and
redacted from every log line, detail and report field; the script refuses to start if the project
already has containers or volumes, so it never adopts or deletes state it did not create; the only
destructive command is `down -v --remove-orphans` for project atlas-acceptance, and only after this
run started that project. Built images are not removed.

Exit status: 0 only when every check passed (or passed with the stack deliberately kept via --keep);
1 otherwise; 2 for bad arguments.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

GAP_STATEMENT = "NOT_VERIFIED: OIDC login, persistence, TLS-proxy-LAN, backups, perf-load, task execution, other hosts, image provenance"
PROJECT_NAME = "atlas-acceptance"
COMPOSE_RELATIVE = "deploy/local/docker-compose.yml"
ENV_RELATIVE = "deploy/local/.env"
HOST_PORT = 8000
BASE_URL = f"http://127.0.0.1:{HOST_PORT}"
PROTECTED_PROBE_PATH = "/api/v1/product-orchestrator/goals/acceptance-probe"
EXPECTED_SERVICES = ("migrate", "api", "worker", "postgres", "redis")
EXPECTED_VOLUMES = (f"{PROJECT_NAME}_atlas-postgres", f"{PROJECT_NAME}_atlas-redis")
REQUIRED_ENV = (
    "POSTGRES_PASSWORD", "REDIS_PASSWORD", "ATLAS_TOKEN_KEY",
    "ATLAS_API_KEY_ENCRYPTION_KEY", "ATLAS_OIDC_ISSUER", "ATLAS_OIDC_AUDIENCE",
)
URL_EMBEDDED_SECRETS = ("POSTGRES_PASSWORD", "REDIS_PASSWORD")  # compose puts these inside connection URLs
PLACEHOLDER = "CHANGE_ME"
READY_CHECKS = ("database", "redis", "migrations")
NOT_VERIFIED = (
    "OIDC login against a real issuer (only that an unauthenticated request is rejected with 401)",
    "data persistence across down/up (volumes are checked to exist; no data is written or read back)",
    "TLS, reverse proxy, remote or LAN access (every request is http://127.0.0.1)",
    "backup and restore",
    "performance, sizing and load",
    "Celery task execution beyond a broker ping",
    "any host other than the one that ran this script",
    "image provenance and vulnerability status",
)
GATING = ("preconditions.", "compose.", "services.")  # a failure here skips every later check
_MAX_DETAIL = 600
_MAX_DIAGNOSTICS = 4000


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | SKIPPED
    detail: str = ""


# ----------------------------------------------------------------------------- pure helpers

def parse_env_file(text: str) -> dict:
    """Parse KEY=VALUE lines literally: no interpolation, no inline-comment stripping."""
    env: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        env[key] = value
    return env


def validate_env(env: dict) -> list:
    """Return problems as text naming variables only, never their values."""
    problems = []
    for key in REQUIRED_ENV:
        value = env.get(key)
        if value is None or not value.strip():
            problems.append(f"{key}: missing or empty")
        elif PLACEHOLDER in value:
            problems.append(f"{key}: still a placeholder value ({PLACEHOLDER}); set a real one")
        elif key in URL_EMBEDDED_SECRETS and not re.fullmatch(r"[A-Za-z0-9._~-]+", value):
            problems.append(f"{key}: contains characters unsafe inside the compose connection url "
                            "(allowed: letters, digits, '-', '_', '.', '~')")
    return problems


def secret_values(env: dict) -> list:
    return [v for k, v in env.items() if re.search(r"PASSWORD|KEY|SECRET|TOKEN", k) and len(v) >= 4]


def redact(text: str, secrets) -> str:
    for secret in sorted({s for s in secrets if isinstance(s, str) and len(s) >= 4}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def parse_compose_ps(text: str) -> list:
    """Accept both `docker compose ps --format json` shapes: one JSON array or one object per line."""
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        rows = json.loads(stripped)
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError("ps output is not a list of objects")
        return rows
    rows = []
    for line in stripped.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("ps line is not an object")
        rows.append(row)
    return rows


def evaluate_services(rows: list) -> tuple:
    """Return (ok, problems). An empty list is never ok."""
    problems = []
    for service in EXPECTED_SERVICES:
        mine = [r for r in rows if r.get("Service") == service]
        if not mine:
            problems.append(f"{service}: not present")
            continue
        for row in mine:
            state, health = row.get("State"), row.get("Health") or ""
            if service == "migrate":
                code = row.get("ExitCode")
                try:
                    code_ok = int(code) == 0
                except (TypeError, ValueError):
                    code_ok = False
                if state != "exited" or not code_ok:
                    problems.append(f"migrate: state={state} exit={code} (must have exited 0)")
            elif service == "worker":
                if state != "running" or health not in ("", "healthy"):
                    problems.append(f"worker: state={state} health={health or 'none'} (need running)")
            elif state != "running" or health != "healthy":
                problems.append(f"{service}: state={state} health={health or 'none'} (need running and healthy)")
    return (not problems), problems


def _json_or_none(body: str):
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        return None


def _failing_checks(body: str) -> list:
    data = _json_or_none(body)
    if not isinstance(data, dict):
        return []
    checks = data.get("checks")
    if not isinstance(checks, dict) and isinstance(data.get("detail"), dict):
        checks = data["detail"].get("checks")
    if not isinstance(checks, dict):
        return []
    return sorted(k for k, v in checks.items() if v is not True)


def ready_ok(status, body: str) -> bool:
    """200 alone is not trusted: the body must say ready and every readiness check must be True."""
    if status != 200:
        return False
    data = _json_or_none(body)
    if not isinstance(data, dict) or data.get("status") != "ready":
        return False
    checks = data.get("checks")
    return (isinstance(checks, dict) and all(k in checks for k in READY_CHECKS)
            and all(v is True for v in checks.values()))


# ----------------------------------------------------------------------------- default I/O

def _default_runner(argv, timeout):
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, stdin=subprocess.DEVNULL, check=False)
    return CommandResult(done.returncode, done.stdout or "", done.stderr or "")


def _default_http_get(url, timeout):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost must not use env proxies
    request = urllib.request.Request(url, method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(65536).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, f"connection failed: {type(exc).__name__}"


def _default_port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


# ----------------------------------------------------------------------------- acceptance run

class Report:
    def __init__(self, checks, diagnostics, keep):
        self.checks = checks
        self.diagnostics = diagnostics
        self.keep = keep

    @property
    def passed(self):
        return all(c.status == "PASS" or (c.name == "cleanup" and self.keep and c.status == "SKIPPED")
                   for c in self.checks)

    @property
    def exit_code(self):
        return 0 if self.passed else 1

    def to_dict(self):
        return {
            "tool": "deploy/local/acceptance/compose_acceptance.py",
            "project": PROJECT_NAME,
            "result": "PASS" if self.passed else "FAIL",
            "gap": GAP_STATEMENT,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks],
            "not_verified": list(NOT_VERIFIED),
            "diagnostics": self.diagnostics,
        }


class Acceptance:
    def __init__(self, *, repo_root, env_file, runner: Optional[Callable] = None,
                 http_get: Optional[Callable] = None, port_in_use: Optional[Callable] = None,
                 sleep: Optional[Callable] = None, monotonic: Optional[Callable] = None,
                 keep: bool = False, log: Optional[Callable] = None, up_timeout: float = 600,
                 ready_timeout: float = 120, poll_interval: float = 5, command_timeout: float = 1800,
                 http_timeout: float = 5):
        self.repo_root = Path(repo_root)
        self.env_file = Path(env_file)
        self.compose_file = self.repo_root / COMPOSE_RELATIVE
        self.runner = runner or _default_runner
        self.http_get = http_get or _default_http_get
        self.port_in_use = port_in_use or _default_port_in_use
        self.sleep = sleep or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.keep = keep
        self.log = log or (lambda line: print(line, flush=True))
        self.up_timeout, self.ready_timeout = up_timeout, ready_timeout
        self.poll_interval, self.command_timeout, self.http_timeout = poll_interval, command_timeout, http_timeout
        self.checks: list = []
        self.diagnostics = ""
        self._secrets: list = []
        self._started = False

    # -- plumbing
    def _compose(self, *args):
        return ["docker", "compose", "-p", PROJECT_NAME, "-f", str(self.compose_file),
                "--env-file", str(self.env_file), *args]

    def _exec(self, argv) -> CommandResult:
        try:
            return self.runner(argv, self.command_timeout)
        except FileNotFoundError:
            return CommandResult(127, "", f"command not found: {argv[0]}")
        except subprocess.TimeoutExpired:
            return CommandResult(124, "", f"timed out after {self.command_timeout}s")
        except OSError as exc:
            return CommandResult(126, "", f"could not run command: {type(exc).__name__}")

    def _clean(self, text: str) -> str:
        return redact(text or "", self._secrets)

    def _record(self, name, status, detail=""):
        detail = self._clean(detail).strip()[:_MAX_DETAIL]
        self.checks.append(Check(name, status, detail))
        self.log(f"[{status}] {name}" + (f" - {detail}" if detail else ""))

    def _get(self, path):
        try:
            status, body = self.http_get(BASE_URL + path, self.http_timeout)
        except Exception as exc:  # a failing probe is a failed check, never a crash
            return None, f"request failed: {type(exc).__name__}"
        return status, body

    def _capture_diagnostics(self):
        result = self._exec(self._compose("logs", "--no-color", "--tail", "40"))
        text = (result.stdout or "") + (result.stderr or "")
        self.diagnostics = self._clean(text)[-_MAX_DIAGNOSTICS:]

    @staticmethod
    def _first_line(result: CommandResult) -> str:
        text = (result.stderr or result.stdout or "").strip()
        return text.splitlines()[0] if text else f"exit code {result.returncode}"

    # -- checks: each returns (ok, detail)
    def _check_docker(self):
        result = self._exec(["docker", "--version"])
        if result.returncode == 127:
            return False, "docker CLI not found on PATH"
        return result.returncode == 0, (result.stdout.strip() or self._first_line(result))

    def _check_compose_plugin(self):
        result = self._exec(["docker", "compose", "version"])
        if result.returncode != 0:
            return False, "docker compose v2 plugin unavailable: " + self._first_line(result)
        return True, result.stdout.strip()

    def _check_env_file(self):
        if not self.compose_file.is_file():
            return False, f"compose file not found: {self.compose_file}"
        if not self.env_file.is_file():
            return False, (f"env file not found: {self.env_file}; copy deploy/local/.env.example to "
                           "deploy/local/.env and fill it in (do not commit it)")
        env = parse_env_file(self.env_file.read_text(encoding="utf-8", errors="replace"))
        self._secrets = secret_values(env)
        problems = validate_env(env)
        if problems:
            return False, "; ".join(problems)
        return True, f"{len(REQUIRED_ENV)} required variables present, no placeholders (values not shown)"

    def _check_port(self):
        if self.port_in_use(HOST_PORT):
            return False, (f"port {HOST_PORT} on 127.0.0.1 is already in use; stop whatever listens there "
                           f"(the compose file publishes {HOST_PORT}:8080)")
        return True, f"port {HOST_PORT} is free"

    def _check_config(self):
        result = self._exec(self._compose("config", "-q"))
        return result.returncode == 0, ("compose file accepted" if result.returncode == 0 else self._first_line(result))

    def _check_clean_project(self):
        containers = self._exec(self._compose("ps", "-a", "-q"))
        if containers.returncode != 0:
            return False, "could not list project containers: " + self._first_line(containers)
        if containers.stdout.strip():
            return False, (f"containers for project {PROJECT_NAME} already exist; this script will not adopt or "
                           f"delete them. If they are disposable, remove them yourself first")
        volumes = self._exec(["docker", "volume", "ls", "-q", "--filter",
                              f"label=com.docker.compose.project={PROJECT_NAME}"])
        if volumes.returncode != 0:
            return False, "could not list project volumes: " + self._first_line(volumes)
        if volumes.stdout.strip():
            return False, (f"volumes for project {PROJECT_NAME} already exist; this script will not adopt or "
                           f"delete them. If they are disposable, remove them yourself first")
        return True, f"no existing {PROJECT_NAME} containers or volumes"

    def _check_up(self):
        self._started = True
        result = self._exec(self._compose("up", "-d", "--build"))
        if result.returncode != 0:
            self._capture_diagnostics()
            return False, "docker compose up failed: " + self._first_line(result)
        return True, "up -d --build returned 0"

    def _check_services(self):
        deadline = self.monotonic() + self.up_timeout
        problems = ["no ps output yet"]
        while True:
            result = self._exec(self._compose("ps", "-a", "--format", "json"))
            if result.returncode == 0:
                try:
                    ok, problems = evaluate_services(parse_compose_ps(result.stdout))
                except ValueError:
                    ok, problems = False, ["could not parse docker compose ps output"]
                if ok:
                    return True, "migrate exited 0; api, postgres, redis healthy; worker running"
            else:
                problems = ["docker compose ps failed: " + self._first_line(result)]
            if self.monotonic() >= deadline:
                self._capture_diagnostics()
                return False, f"not up within {self.up_timeout}s: " + "; ".join(problems)
            self.sleep(self.poll_interval)

    def _check_health(self):
        status, body = self._get("/health")
        if status == 200 and _json_or_none(body) == {"status": "ok"}:
            return True, "200 {'status': 'ok'}"
        return False, f"expected 200 with status ok, got HTTP {status}"

    def _poll_ready(self):
        deadline = self.monotonic() + self.ready_timeout
        while True:
            status, body = self._get("/ready")
            if ready_ok(status, body):
                return True, "200 ready; database, redis and migrations all true"
            if self.monotonic() >= deadline:
                failing = _failing_checks(body)
                suffix = f"; failing checks: {', '.join(failing)}" if failing else ""
                return False, f"not ready within {self.ready_timeout}s (HTTP {status}){suffix}"
            self.sleep(self.poll_interval)

    def _check_auth(self):
        status, _ = self._get(PROTECTED_PROBE_PATH)
        if status == 401:
            return True, "unauthenticated request rejected with 401"
        return False, f"expected 401 without credentials on a protected route, got {status}"

    def _check_worker(self):
        result = self._exec(self._compose("exec", "-T", "worker", "celery", "-A",
                                          "app.workers.celery_app:celery_app", "inspect", "ping", "--timeout", "10"))
        if result.returncode == 0 and "pong" in (result.stdout or "").lower():
            return True, "worker answered a celery inspect ping"
        return False, "no pong from worker: " + self._first_line(result)

    def _check_volumes(self):
        result = self._exec(["docker", "volume", "ls", "--filter",
                             f"label=com.docker.compose.project={PROJECT_NAME}", "--format", "{{.Name}}"])
        if result.returncode != 0:
            return False, "could not list volumes: " + self._first_line(result)
        names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        missing = [v for v in EXPECTED_VOLUMES if v not in names]
        if missing:
            return False, "missing volumes: " + ", ".join(missing)
        return True, "declared volumes exist: " + ", ".join(EXPECTED_VOLUMES)

    def _check_restart(self):
        result = self._exec(self._compose("restart", "api"))
        if result.returncode != 0:
            return False, "restart api failed: " + self._first_line(result)
        return self._poll_ready()

    # -- orchestration
    def run(self) -> Report:
        steps = (
            ("preconditions.docker", self._check_docker),
            ("preconditions.compose", self._check_compose_plugin),
            ("preconditions.env_file", self._check_env_file),
            ("preconditions.port_free", self._check_port),
            ("compose.config", self._check_config),
            ("preconditions.clean_project", self._check_clean_project),
            ("compose.up", self._check_up),
            ("services.state", self._check_services),
            ("http.health", self._check_health),
            ("http.ready", self._poll_ready),
            ("http.auth_enforced", self._check_auth),
            ("worker.ping", self._check_worker),
            ("volumes.exist", self._check_volumes),
            ("restart.api_ready", self._check_restart),
        )
        blocked = False
        try:
            for name, step in steps:
                if blocked:
                    self._record(name, "SKIPPED", "an earlier gating check failed")
                    continue
                try:
                    ok, detail = step()
                except Exception as exc:  # unexpected: report, never crash before cleanup
                    ok, detail = False, f"internal error: {type(exc).__name__}"
                self._record(name, "PASS" if ok else "FAIL", detail)
                if not ok and name.startswith(GATING):
                    blocked = True
        finally:
            self._cleanup()
        report = Report(self.checks, self.diagnostics, self.keep)
        if report.passed:
            self.log("compose acceptance passed: every check above is PASS. See not_verified in the report "
                     f"for what this does not show. Gap: {GAP_STATEMENT}")
        else:
            self.log("compose acceptance FAILED: see the FAIL lines above.")
        return report

    def _cleanup(self):
        if not self._started:
            self._record("cleanup", "SKIPPED", "nothing was started, nothing to remove")
        elif self.keep:
            self._record("cleanup", "SKIPPED",
                         f"--keep given: stack left running under project {PROJECT_NAME}; remove it with "
                         f"`docker compose -p {PROJECT_NAME} -f {self.compose_file} --env-file {self.env_file} "
                         "down -v --remove-orphans`")
        else:
            result = self._exec(self._compose("down", "-v", "--remove-orphans"))
            if result.returncode == 0:
                self._record("cleanup", "PASS", f"removed project {PROJECT_NAME} containers, network and volumes "
                                                "(built images are kept)")
            else:
                self._record("cleanup", "FAIL", "teardown failed: " + self._first_line(result))


def main(argv=None, *, runner=None, http_get=None, port_in_use=None, sleep=None, monotonic=None, log=None) -> int:
    default_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(
        description="Docker Compose single-machine acceptance for the Atlas local stack. "
                    f"Gap: {GAP_STATEMENT}.")
    parser.add_argument("--repo-root", default=str(default_root))
    parser.add_argument("--env-file", default=None, help=f"default: <repo-root>/{ENV_RELATIVE}")
    parser.add_argument("--report", default=None, help="write the JSON report to this path")
    parser.add_argument("--keep", action="store_true", help="leave the stack running after the checks")
    parser.add_argument("--up-timeout", type=float, default=600.0)
    parser.add_argument("--ready-timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    env_file = Path(args.env_file) if args.env_file else repo_root / ENV_RELATIVE
    acceptance = Acceptance(repo_root=repo_root, env_file=env_file, runner=runner, http_get=http_get,
                            port_in_use=port_in_use, sleep=sleep, monotonic=monotonic, keep=args.keep, log=log,
                            up_timeout=args.up_timeout, ready_timeout=args.ready_timeout)
    report = acceptance.run()
    if args.report:
        try:
            Path(args.report).write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"could not write report: {type(exc).__name__}", file=sys.stderr)
            return 1
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
