#!/usr/bin/env bash
# One command: check hardware, pick a real Inkling-Small build that fits, launch an
# OpenAI-compatible server, and write the Atlas env lines. Linux, macOS or WSL.
#   scripts/inkling/setup.sh [--engine auto|llamacpp|vllm|sglang] [--port N] [--dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE=auto; PORT=8080; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --engine) ENGINE="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    *) echo "unknown option $1" >&2; exit 64;;
  esac
done
PY=$(command -v python3 || command -v python)
set +e; PLAN=$("$PY" "$HERE/fit.py" --engine "$ENGINE" --json); CODE=$?; set -e
get() { "$PY" -c "import json,sys;print(json.loads(sys.argv[1]).get(sys.argv[2],''))" "$PLAN" "$1"; }
if [ "$CODE" -ne 0 ]; then echo "Inkling-Small can't run here: $(get reason)" >&2; exit 2; fi
ENG=$(get engine); REPO=$(get repo); QUANT=$(get quant); TP=$(get tp); NAME=$(get served_model_name)
case "$ENG" in
  llamacpp)
    CMD=(llama-server -hf "$REPO:$QUANT" --alias "$NAME" --host 127.0.0.1 --port "$PORT" --jinja -c 16384)
    [ "$(get gpu_offload)" = "True" ] && CMD+=(-ngl 999 --cpu-moe)
    NEED=llama-server; HINT="install llama.cpp: 'brew install llama.cpp' (macOS/Linux) or 'winget install llama.cpp' (Windows), or build from https://github.com/ggml-org/llama.cpp";;
  vllm)
    CMD=(vllm serve "$REPO" --trust-remote-code --tokenizer-mode inkling --tensor-parallel-size "$TP" --enable-auto-tool-choice --tool-call-parser inkling --reasoning-parser inkling --served-model-name "$NAME" --host 127.0.0.1 --port "$PORT")
    NEED=vllm; HINT="uv pip install -U vllm --pre --extra-index-url https://wheels.vllm.ai/nightly/cu130 --extra-index-url https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match";;
  sglang)
    CMD=("$PY" -m sglang.launch_server --model-path "$REPO" --tp-size "$TP" --served-model-name "$NAME" --host 127.0.0.1 --port "$PORT")
    NEED=""; HINT="pip install sglang";;
esac
ENVFILE="${ATLAS_ENV_FILE:-.env.inkling}"
cat > "$ENVFILE" <<EOF
ATLAS_LOCAL_OPENAI_URL=http://127.0.0.1:$PORT/v1
ATLAS_LOCAL_OPENAI_MODEL=$NAME
EOF
echo "Plan: $ENG, $REPO ($QUANT). Env written to $ENVFILE."
echo "Command: ${CMD[*]}"
[ "$DRY" -eq 1 ] && exit 0
if [ -n "$NEED" ] && ! command -v "$NEED" >/dev/null; then echo "$NEED not found. $HINT" >&2; exit 3; fi
[ "$ENG" = sglang ] && ! "$PY" -c 'import sglang' 2>/dev/null && { echo "sglang not installed. $HINT" >&2; exit 3; }
echo "First launch downloads the weights (tens to hundreds of GB)."
exec "${CMD[@]}"
