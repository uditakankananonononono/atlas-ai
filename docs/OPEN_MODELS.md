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

Honest note on hardware: Inkling-Small is ~266B parameters (Hub safetensors total), and full Inkling is 975B. Neither fits a normal PC. See "Run Inkling-Small yourself" below for exact floors. Until the hardware exists, the HF router is the working Inkling.

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

## Run Inkling-Small yourself (self_hosted)

This is the real Inkling-Small, never a smaller stand-in. One command checks the machine, picks the largest real build that fits, starts an OpenAI-compatible server and writes `.env.inkling` for Atlas:

```bash
scripts/inkling/setup.sh                 # Linux / macOS / WSL; add --dry-run to only print the plan
scripts/inkling/setup.sh --engine vllm   # force vLLM on a GPU server
powershell -ExecutionPolicy Bypass -File scripts\inkling\setup.ps1   # Windows, llama.cpp
```

Then load `.env.inkling` into Atlas's env and check `GET /api/v1/models/health` (openai_compat reachable). Call it with `model_name="inkling-small"`.

Hardware floor (weights sizes from the Hub; +10% and ~8 GB headroom):

| Machine | What runs | Engine |
|---|---|---|
| Under ~90 GB RAM+VRAM combined | Nothing. Setup refuses and says why | - |
| ~90-100 GB RAM+VRAM | `unsloth/Inkling-Small-GGUF` UD-IQ1_S (74.8 GB), 1-bit, slow on CPU | llama.cpp |
| ~150 GB | UD-IQ4_XS (127.4 GB) | llama.cpp, GPU offload if present |
| ~190 GB+ | UD-Q4_K_XL (163 GB) | llama.cpp |
| >= ~198 GB GPU memory (e.g. 2x H200, 1x B300) | `thinkingmachines/Inkling-Small-NVFP4` | vLLM or SGLang, tensor parallel |
| >= ~660 GB GPU memory (8x H200) | `thinkingmachines/Inkling-Small` BF16 | vLLM or SGLang |

The vLLM command follows the published recipe (`--trust-remote-code --tokenizer-mode inkling --tool-call-parser inkling --reasoning-parser inkling`). First launch downloads the weights: 75 GB to 530 GB depending on the build. On CPU-heavy setups, llama.cpp's `--cpu-moe` keeps the MoE experts in RAM and the rest on the GPU. Expect a few tokens per second, not chat speed.

## Any other local model

```bash
# llama.cpp server (any GGUF that fits your RAM/VRAM)
llama-server -hf <org>/<model>-GGUF --port 8080
export ATLAS_LOCAL_OPENAI_URL=http://localhost:8080/v1
curl -s localhost:8000/api/v1/models/generate -H 'content-type: application/json' -d '{"prompt":"hello","model_name":"inkling"}'
```
