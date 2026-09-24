# Open models and free-first routing

Code: `backend/app/core/model_catalog.py`, `backend/app/core/providers.py`, `backend/app/core/model_routes.py`. Tests: `tests/test_model_catalog.py`.

## What the named models actually are (checked 2026-09-24)

| Name | What it is | Open weights? | How Atlas reaches it | Cost |
|---|---|---|---|---|
| Inkling | Thinking Machines Lab multimodal MoE, 975B total / 41B active, text+image+audio in. Released 2026-07-15. | Yes | Local llama.cpp server with `unsloth/inkling-GGUF`, or the HF Inference Providers router (`thinkingmachines/Inkling`) | Free locally (needs a very large-memory machine); HF free-tier credits |
| Inkling-Small | Smaller Inkling, Apache-2.0 | Yes | Self-host with vLLM/SGLang (NVFP4 ~180 GB VRAM), or HF router (`thinkingmachines/Inkling-Small`) | Free locally; HF free-tier credits |
| Fugu (Sakana) | Multi-agent orchestrator sold as one hosted model (`fugu`, `fugu-ultra`) | **No** - hosted API only | `fugu` provider, OpenAI-compatible Chat Completions | **Paid** per token. Off unless `ATLAS_ALLOW_PAID=true` |
| Ultron | Not one model. Several unrelated small community checkpoints share the name | - | **Not wired.** Name the exact Hub repo and serve it through `openai_compat` | - |

Sources: https://huggingface.co/blog/thinkingmachines-inkling, https://huggingface.co/thinkingmachines/Inkling-Small, https://github.com/SakanaAI/Fugu, https://console.sakana.ai/pricing, https://huggingface.co/trojan0x/ultron, https://huggingface.co/passing2961/Ultron-11B

Honest note on hardware: Inkling is huge. A normal PC can't hold it, even at 1-bit. On a normal PC, run a model that fits in Ollama (default `llama3.1:8b`, see `ollama-32gb.env`) or a small GGUF through llama.cpp. Use the HF free tier when you want Inkling itself.

## Providers

| Provider id | Aliases | Env | Cost |
|---|---|---|---|
| `ollama` | `local` | `ATLAS_OLLAMA_URL`, `ATLAS_OLLAMA_MODEL` | free |
| `openai_compat` | `llamacpp`, `vllm`, `lmstudio`, `sglang` | `ATLAS_LOCAL_OPENAI_URL` (default `http://localhost:8080/v1`), `ATLAS_LOCAL_OPENAI_MODEL`, optional `ATLAS_LOCAL_OPENAI_KEY` | free |
| `huggingface` | `hf` | `HF_TOKEN`, `ATLAS_HF_MODEL` (default `thinkingmachines/Inkling-Small`) | free tier |
| `fugu` | `sakana` | `FUGU_API_KEY`, `FUGU_BASE_URL`, `ATLAS_FUGU_MODEL`, **`ATLAS_ALLOW_PAID=true`** | paid |
| `openai`, `anthropic`, `gemini`, `deepseek` | - | their API keys | paid (optional config) |

## Free-first rule

`generate_free_first()` tries Ollama, then the local OpenAI-compatible server, then HF (only if `HF_TOKEN` is set). Paid routes are skipped unless `ATLAS_ALLOW_PAID=true`. If every free route fails, it raises `no free model route succeeded; Atlas stopped instead of using a paid provider` and lists why each route failed.

## API

- `GET /api/v1/models/catalog` - the table above as JSON, plus `paid_allowed`.
- `POST /api/v1/models/generate` `{"prompt": "...", "model_name": "inkling"}` - free-first generation. Returns 503 with the reason when it stops.

Both need a tenant (OIDC in production).

## Run Inkling-class models on your PC

```bash
# llama.cpp server (any GGUF that fits your RAM/VRAM)
llama-server -hf <org>/<model>-GGUF --port 8080
export ATLAS_LOCAL_OPENAI_URL=http://localhost:8080/v1
curl -s localhost:8000/api/v1/models/generate -H 'content-type: application/json' -d '{"prompt":"hello","model_name":"inkling"}'
```
