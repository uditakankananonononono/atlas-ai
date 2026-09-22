# Install Atlas on an owner-controlled computer

## Requirements

- Linux, macOS or Windows with Docker Desktop / Docker Engine and Compose v2
- 8 GB RAM minimum for the API, worker, PostgreSQL and Redis; model or browser workloads need more
- A real OIDC provider configuration
- Provider credentials only for features you choose to enable

## Clean install

```sh
git clone https://github.com/uditakankananonononono/atlas-ai.git
cd atlas-ai
./scripts/bootstrap_local.sh
# first run creates .env.local and stops; replace every CHANGE_ME value
./scripts/bootstrap_local.sh
curl -fsS http://localhost:8000/ready
```

The migration runs as a one-shot service before API and workers. Persistent data lives in named PostgreSQL and Redis volumes. The default does not expose PostgreSQL, Redis or Ollama publicly. Atlas does not buy cloud capacity or enable paid providers on its own.

For Python-only development, use Python 3.12, `python -m pip install -e '.[dev]'`, then `pytest -q`. This is not the production-shaped install because SQLite and local headers are development conveniences.
