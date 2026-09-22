#!/usr/bin/env sh
set -eu
command -v docker >/dev/null 2>&1 || { echo "Docker is required: https://docs.docker.com/get-docker/" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required" >&2; exit 1; }
cd "$(dirname "$0")/.."
[ -f .env.local ] || { cp deploy/local/.env.example .env.local; echo "Created .env.local. Replace every CHANGE_ME value before continuing."; exit 2; }
if grep -q 'CHANGE_ME' .env.local; then echo ".env.local still contains CHANGE_ME values" >&2; exit 2; fi
docker compose --env-file .env.local -f deploy/local/docker-compose.yml config --quiet
docker compose --env-file .env.local -f deploy/local/docker-compose.yml up --build -d
echo "Atlas started. Check readiness with: curl -fsS http://localhost:8000/ready"
