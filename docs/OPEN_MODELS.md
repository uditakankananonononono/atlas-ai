# Open models and free-first routing

Code: `backend/app/core/model_catalog.py`, `backend/app/core/providers.py`, `backend/app/core/model_routes.py`. Tests: `tests/test_model_catalog.py`.

## What the named models actually are (checked 2026-09-24)

| Name | What it is | Open weights? | How Atlas reaches it | Kind |
|---|---|---|---|---|
| Inkling | Thinking Machines Lab multimodal MoE, 975B total / 41B active, text+image+audio in. Released 2026-07-15. | Yes | Primary: HF Inference Providers router (`thinkingmachines/Inkling-Small`, then `thinkingmachines/Inkling`). Alternate: self-hosted `unsloth/inkling-GGUF` / vLLM | hosted_free, then self_hosted |
| Inkling-Small | Smaller Inkling, Apache-2.0 | Yes | Primary: HF router (`thinkingmachines/Inkling-Small`). Alternate: vLLM/SGLang (NVFP4 ~180 GB VRAM) | hosted_free, then self_hosted |
| Fugu (Sakana) | Multi-agent orchestrator sold as one hosted model (`fugu`, `fugu-ultra`) | **No** - hosted API only | `fugu` provider, OpenAI-compatible Chat Completions | hosted_paid. Off unless `ATLAS_ALLOW_PAID=true` |
| Ultron | Not one model. Several unrelated small community checkpoints share the name | - | **Not wired.** Name the exact Hub repo and serve it through `openai_compat` | - |

Sources: https://huggingface.co/blog/thinkingmachines-inkling, https://huggingface.co/thinkingmachines/Inkling-Small, https://github.com/SakanaAI/Fugu, https://console.sakana.ai/pricing, https://huggingface.co/trojan0x/ultron, https://huggingface.co/passing2961/Ultron-11B

Honest note on hardware: Inkling is huge. A normal PC can't hold it, even at 1-bit. On a normal PC, run a model that fits in Ollama (default `llama3.1:8b`, see `ollama-32gb.env`) or a small GGUF through llama.cpp. Use the HF free tier when you want Inkling itself.

Kinds match the Meemee model layer: `local`, `self_hosted`, `hosted_free`, `hosted_paid`.

## Turn on Inkling (free Hugging Face token)

1. Sign in or sign up at https://huggingface.co (free).
2. Go to https://huggingface.co/settings/tokens, click **Create new token**, choose **Fine-grained**, and tick **Make calls to Inference Providers**.
3. Put it in Atlas's env: `HF_TOKEN=hf_...` (the same `.env` as the rest of the config; never paste it into chat).
4. Check it: `GET /api/v1/models/health` should show `huggingface` as `reachable: true`. Then `POST /api/v1/models/generate {"prompt":"hi","model_name":"inkling"}`.

Credit limit, plainly: free HF accounts get about $0.10 of Inference Providers credit a month (https://huggingface.co/docs/inference-providers/pricing). Inkling is listed at about $1 in / $4.05 out per million tokens, so that's a few dozen normal replies a month. When the credit runs out HF returns 402, and Atlas says "credits exhausted" and moves on to the next free route instead of buying more. If you ever add a payment method to your HF account, HF can bill past the free credit. Atlas has no way to see that, so leave HF billing off if you want it to stay free.

## Providers

| Provider id | Aliases | Env | Kind |
|---|---|---|---|
| `ollama` | `local` | `ATLAS_OLLAMA_URL`, `ATLAS_OLLAMA_MODEL` | local |
| `openai_compat` | `llamacpp`, `vllm`, `lmstudio`, `sglang` | `ATLAS_LOCAL_OPENAI_URL` (default `http://localhost:8080/v1`), `ATLAS_LOCAL_OPENAI_MODEL`, optional `ATLAS_LOCAL_OPENAI_KEY` | local / self_hosted |
| `huggingface` | `hf` | `HF_TOKEN`, `ATLAS_HF_MODEL` (default `thinkingmachines/Inkling-Small`) | hosted_free |
| `fugu` | `sakana` | `FUGU_API_KEY`, `FUGU_BASE_URL`, `ATLAS_FUGU_MODEL`, **`ATLAS_ALLOW_PAID=true`** | hosted_paid |
| `openai`, `anthropic`, `gemini`, `deepseek` | - | their API keys | hosted_paid (optional config) |

## Free-first rule

`generate_free_first()` with no model name tries Ollama, then the local OpenAI-compatible server, then HF (only if `HF_TOKEN` is set). With `model_name="inkling"` it tries HF Inkling-Small, then HF Inkling, then the self-hosted server. Paid routes are skipped unless `ATLAS_ALLOW_PAID=true`. If every free route fails, it raises `no free model route succeeded; Atlas stopped instead of using a paid provider` and lists why each route failed.

## API

- `GET /api/v1/models/catalog` - the table above as JSON, plus `paid_allowed`.
- `GET /api/v1/models/health` - zero-token probe (model-list GET) of each provider: configured, reachable, paid disabled.
- `POST /api/v1/models/generate` `{"prompt": "...", "model_name": "inkling"}` - free-first generation. Returns 503 with the reason when it stops.

Both need a tenant (OIDC in production).

## Run Inkling-class models on your PC

```bash
# llama.cpp server (any GGUF that fits your RAM/VRAM)
llama-server -hf <org>/<model>-GGUF --port 8080
export ATLAS_LOCAL_OPENAI_URL=http://localhost:8080/v1
curl -s localhost:8000/api/v1/models/generate -H 'content-type: application/json' -d '{"prompt":"hello","model_name":"inkling"}'
```
