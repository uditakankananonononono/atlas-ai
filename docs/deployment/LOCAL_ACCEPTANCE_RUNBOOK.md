# Local Docker Compose acceptance runbook (single machine)

Unit X11, free substitute. This runbook and `deploy/local/acceptance/compose_acceptance.py` are
the free route to check the local Compose deployment: you run the script on your own computer.
Everything it uses is free and local: Docker, the Python standard library, and this repository.

Honest gap, stated verbatim: **NOT_VERIFIED: OIDC login, persistence, TLS-proxy-LAN, backups, perf-load, task execution, other hosts, image provenance**.

The script and its tests were written without running Docker. The unit tests use fakes, so they
show the script's decision logic is sound; only a real run on your machine shows that your Docker,
images and network behave the way the checks expect. Until you run it, nothing here is a
deployment result.

## Prerequisites

- Docker with the compose v2 plugin (`docker compose version` must work). Docker Desktop on
  Windows or macOS, or Docker Engine on Linux.
- A recent Python 3 (the script is standard library only and is written for Python 3.8 or newer).
- This repository checked out, with a working directory at its root.
- Free disk space and time for the first build: the images are built from the repository
  Dockerfile, which can take several minutes.
- Host port 8000 free (the compose file publishes `8000:8080`).
- A filled-in env file at `deploy/local/.env`. Copy `deploy/local/.env.example` to
  `deploy/local/.env` and replace every `CHANGE_ME` value. Do not commit `.env`; it holds secrets.
  `POSTGRES_PASSWORD` and `REDIS_PASSWORD` end up inside connection URLs, so use only letters,
  digits and `-` `_` `.` `~`. Put no trailing comments on a value line. Keep the value formats the
  example file asks for; the script does not check formats, only that each value is present and not
  a placeholder.

## Run it

From the repository root:

```
python deploy/local/acceptance/compose_acceptance.py
```

Useful options:

```
python deploy/local/acceptance/compose_acceptance.py --report acceptance-report.json
python deploy/local/acceptance/compose_acceptance.py --env-file path/to/other.env
python deploy/local/acceptance/compose_acceptance.py --keep
python deploy/local/acceptance/compose_acceptance.py --up-timeout 900 --ready-timeout 180
```

On some systems the interpreter is `python3`. The script prints one line per check. Never paste
the contents of your `.env` into a chat or ticket. The script redacts the secret values it knows
about from its output and report, but read a report before sharing it.

## What the script checks

It uses its own compose project name, `atlas-acceptance`, so it does not touch a stack you started
under another name. Check names, in order, as they appear in the output and the JSON report:

| Check | What a PASS means |
|---|---|
| `preconditions.docker` | the `docker` command runs |
| `preconditions.compose` | `docker compose version` succeeds |
| `preconditions.env_file` | the compose file and env file exist; all six required variables are set, none is a `CHANGE_ME` placeholder, and the two passwords are URL-safe |
| `preconditions.port_free` | nothing is listening on 127.0.0.1:8000 |
| `compose.config` | `docker compose config -q` accepts the file with your env file |
| `preconditions.clean_project` | no containers or volumes already exist for project `atlas-acceptance` |
| `compose.up` | `up -d --build` returned success |
| `services.state` | migrate exited 0; api, postgres and redis are running and healthy; worker is running |
| `http.health` | `GET http://127.0.0.1:8000/health` returned 200 with `{"status": "ok"}` |
| `http.ready` | `GET /ready` returned 200 and its body says ready with database, redis and migrations all true |
| `http.auth_enforced` | a request with no credentials to a protected API route returned exactly 401 |
| `worker.ping` | the worker answered a Celery inspect ping, a real round trip through Redis |
| `volumes.exist` | the two declared volumes exist for the project |
| `restart.api_ready` | after restarting api, `/ready` returned to the ready state |
| `cleanup` | `down -v --remove-orphans` for project `atlas-acceptance` succeeded |

A failure in a precondition, `compose.config`, `compose.up` or `services.state` skips the checks
after it and goes straight to cleanup. Failures in the later checks do not stop the other checks.

## What it does not check

A passing run still does not show any of these (they are also listed in the report under
`not_verified`):

- OIDC login against a real issuer. Only the unauthenticated rejection (401) is checked.
- Data persistence across down and up. Volumes are checked to exist; no data is written or read back.
- TLS, a reverse proxy, or access from another machine. Every request is `http://127.0.0.1`.
- Backup and restore.
- Performance, sizing and load.
- Celery task execution beyond a broker ping.
- Any machine other than the one that ran the script.
- Image provenance and vulnerability status.

## Reading the result

- Exit code 0 means every check was PASS (or the only non-PASS is `cleanup` skipped because you
  passed `--keep`). Exit code 1 means at least one check failed. Exit code 2 means bad arguments.
- The report (`--report`) has `result`, one entry per check with `status` and a short `detail`, the
  `not_verified` list, the `gap` line and, after a startup failure, `diagnostics` holding the last
  lines of the container logs with known secret values redacted.
- `SKIPPED` after a failure means the check did not run, not that it passed.
- If `preconditions.clean_project` fails, an earlier run left containers or volumes behind. The
  script refuses to adopt or delete them. If you are sure they are disposable, remove them yourself
  with `docker compose -p atlas-acceptance -f deploy/local/docker-compose.yml --env-file deploy/local/.env down -v`.

## Cleanup

By default the script ends with `docker compose -p atlas-acceptance ... down -v --remove-orphans`.
That removes only the containers, network and volumes of project `atlas-acceptance`, and only when
this run started them. Your data under any other compose project name is not touched. Built images
are kept; remove them with `docker image ls` and `docker image rm` if you want the space back.

With `--keep` the stack stays up and the `cleanup` check reports SKIPPED with the exact command to
remove it later.

## Not part of this runbook

Hosted or cloud deployment, Kubernetes, TLS termination, and the paid or managed services named in
`docs/DEPLOYMENT.md` are outside this free local substitute.
