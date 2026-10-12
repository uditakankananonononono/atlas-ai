# E4: continual learning with Needle LoRA: feasibility check (step 0 only)

Source pin: atlas-ai commit ef1f6af; shared-models default branch as read on 2026-10-12 (README and `evidence/needle-real.txt`). Package under test: cactus-needle 3.0.5 (`needle[train]` = JAX/Flax/optax), base checkpoint `needle3.safetensors` (242.05 MB) from Hugging Face.

Question: does Needle run at all, and can its LoRA fine-tune run where this experiment would be trained? No training experiment was designed or run. This is the gate the parent asked for before any design.

## Results

| Claim | Status |
|---|---|
| Needle base inference runs on CPU and returns a correct tool call (get_weather Lagos, confidence 0.9464) and a no-call refusal; recorded 2026-10-01 in shared-models `evidence/needle-real.txt` (Python 3.10.12, engine 3.0.2, 1 GB RAM sandbox). I read this file; I did not re-run it | VERIFIED |
| `pip install "cactus-needle[train]==3.0.5"` installs on Python 3.12 and JAX reports backend `cpu` | VERIFIED |
| The 242.05 MB training checkpoint downloads with `needle download needle3.safetensors` | VERIFIED |
| `needle finetune` on a 15-row dataset (LoRA rank 4, batch 2, max-len 128, 1 epoch, 8 steps) was killed with exit 137 during JAX compilation on this sandbox (2 CPUs, about 2 GB RAM, no GPU); an earlier attempt at batch 4, max-len 256 also died silently.  | VERIFIED |
| The cause of that kill is memory exhaustion (no kernel log checked) | UNVERIFIED |
| `needle finetune` in 3.0.5 rejects `--layers` (the flag appears in the CLI docstring and in the build command, not in finetune's argument list), so the smaller-rung training shortcut is unavailable on this version | VERIFIED |
| A LoRA fine-tune completes on Colab free tier (not attempted: it needs the user's Google account and a notebook session, and I was not authorized to use it) | UNVERIFIED |
| Fine-tuning completes on CPU in any environment smaller than this sandbox | UNVERIFIED |
| Any continual-learning claim (forgetting, replay benefit); nothing trained, no adapter produced | UNVERIFIED |

## Consequence
E4 as proposed is blocked until a training-capable environment is confirmed. Smallest next step: one Colab run of `gen_tasks.py` task set A, `needle finetune` for 1 epoch, then `needle run` on the held-out A queries. If that completes, the replay-vs-no-replay design below can proceed; if it does not, E4 drops to the lexical floor in shared-models (`LexicalToolModel`), which is not Needle.

## Draft protocol (not run; will be re-checked after feasibility)
- Tasks: `gen_tasks.py` writes two disjoint 3-tool sets (A: weather, timer, music; B: email, todo, web search), 4 train and 2 held-out argument values per tool, plus 3 refusal rows each. This is tiny on purpose (15 train rows per set); a run needs more rows and paraphrases or the held-out score will be near 100% or noise.
- Arms: (1) train A then train B, no replay; (2) train A then B with 10% of A mixed in; (3) train A+B jointly (upper bound). 3 seeds. Metrics: held-out exact-match of tool name and arguments on A after B (forgetting), on B, refusal accuracy.
- A result counts only if it exceeds the seed spread, as in the cognition-harness noise study.
- Needs `NEEDLE_TELEMETRY=0` and `DO_NOT_TRACK=1`, per the shared-models privacy guard.
