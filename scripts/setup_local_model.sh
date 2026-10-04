#!/usr/bin/env bash
# Reproducible FREE local model setup for Atlas abstractive mode. Downloads (not committed) and verifies a pinned GGUF.
# Model: Qwen/Qwen2.5-0.5B-Instruct-GGUF, q4_k_m, Apache-2.0 per the Hugging Face model card. Hub repo sha 9217f5db79a29953eb74d5343926648285ec7e67.
# 0.5B quality is LOW; it is not Gemini/Claude/GPT-4 and its summaries are unverified. Not tested on the Dell i5.
set -euo pipefail
DEST="${1:-./models}"; mkdir -p "$DEST"
URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf"
SHA=74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
curl -fL -o "$DEST/q.gguf" "$URL"
echo "$SHA  $DEST/q.gguf" | sha256sum -c -
echo "Run: python -m llama_cpp.server --model $DEST/q.gguf --host 127.0.0.1 --port 8089   (pip install 'llama-cpp-python[server]')"
echo "Then: export ATLAS_LOCAL_OPENAI_URL=http://127.0.0.1:8089/v1"
