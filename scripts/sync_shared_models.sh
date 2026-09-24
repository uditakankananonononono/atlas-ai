#!/usr/bin/env bash
# Re-vendor instinct_models from shared-models at a pinned commit.
# Usage: scripts/sync_shared_models.sh <commit-sha>
set -euo pipefail
sha="${1:?commit sha required}"
repo="${SHARED_MODELS_REPO:-git@github.com:uditakankananonononono/shared-models.git}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone -q "$repo" "$tmp/sm"
git -C "$tmp/sm" checkout -q "$sha"
dest="$(cd "$(dirname "$0")/.." && pwd)/backend/instinct_models"
keep="$(cat "$dest/VENDORED.md" 2>/dev/null || true)"
rm -rf "$dest"; mkdir -p "$dest"
cp -r "$tmp/sm/instinct_models/." "$dest/"
find "$dest" -name __pycache__ -prune -exec rm -rf {} +
short="$(git -C "$tmp/sm" rev-parse --short HEAD)"
printf '%s\n' "$keep" | sed "s/^Pinned commit: .*/Pinned commit: $short/" > "$dest/VENDORED.md"
echo "vendored instinct_models at $short"
