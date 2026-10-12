# E4 step 1: Colab cells (run once on 2026-10-12 with the jax/flax pin below; see RESULTS.md)

Free-tier T4 only. Runtime > Change runtime type > T4 GPU. Do not upgrade, do not mount Drive.
Run each block as its own cell. Nothing here sends data anywhere except downloads from GitHub and Hugging Face.

## Cell 1: setup
```python
import os
os.environ["NEEDLE_TELEMETRY"] = "0"; os.environ["DO_NOT_TRACK"] = "1"
!pip -q install "cactus-needle[train,gpu]==3.0.5" "jax[cuda12]==0.9.0" "flax==0.10.7" 2>&1 | tail -2
!git clone -q --depth 1 https://github.com/uditakankananonononono/atlas-ai.git
!cd atlas-ai && git rev-parse --short HEAD
!needle download needle3.safetensors --out /content/ck
import jax; print(jax.default_backend(), jax.devices())
```
Expect backend `gpu`. If `cpu`, stop: the GPU extra did not install; report, do not continue.

## Cell 2: data (task set A)
```python
!mkdir -p /content/e4 && cp atlas-ai/experiments/e4_continual_learning/gen_tasks.py /content/e4/ && cd /content/e4 && python gen_tasks.py && wc -l *.jsonl
```

## Cell 3: one-epoch finetune on A (the confirmation step)
```python
!cd /content/e4 && needle finetune A_train.jsonl --checkpoint /content/ck/checkpoints/needle3.safetensors --epochs 1 --batch-size 4 --lora-rank 4 --max-len 256 --val-split 0 --out /content/e4/adA.safetensors --checkpoint-dir /content/e4/ckpt 2>&1 | tail -25
```
Record: did it finish, wall time, peak memory if shown, final loss.

## Cell 4: build and evaluate held-out A (and refusals)
```python
!cd /content/e4 && needle build /content/ck/checkpoints/needle3.safetensors --lora adA.safetensors --out /content/e4/adA.cact 2>&1 | tail -5
import json, needle
rows = [json.loads(l) for l in open("/content/e4/A_test.jsonl")]
tools = rows[0]["tools"]
agent = needle.Needle(tools=tools, weights="/content/e4/adA.cact", stateless=True)
ok = n = 0; refuse_ok = refuse_n = 0
for r in rows:
    resp = agent.complete(r["query"])
    calls = [{"name": c.get("name"), "arguments": c.get("arguments")} for c in resp.get("function_calls") or []]
    if r["answers"]:
        n += 1; ok += calls == r["answers"]
    else:
        refuse_n += 1; refuse_ok += calls == []
print("held-out exact match", ok, "/", n, "| refusals correct", refuse_ok, "/", refuse_n)
```
If `needle.Needle(...)` rejects `weights` or `stateless` in 3.0.5, read `help(needle.Needle.__init__)` and adjust; note that in the report.

## Report back (no secrets, no screenshots of account pages)
GPU backend line, wall time of Cell 3, last 5 lines of Cell 3 output, Cell 4 print line. A single run on 6+6 held-out rows is a feasibility signal, not an accuracy claim.
