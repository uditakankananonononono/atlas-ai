#!/usr/bin/env python3
"""Pick a real Inkling-Small build that fits this machine, or refuse.

Never swaps in a different, smaller model. Sizes are the published file sizes
of unsloth/Inkling-Small-GGUF and thinkingmachines/Inkling-Small-NVFP4
(checked 2026-09-24). Inkling-Small is ~266B parameters (safetensors total).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

REPO_GGUF = "unsloth/Inkling-Small-GGUF"
REPO_NVFP4 = "thinkingmachines/Inkling-Small-NVFP4"
REPO_BF16 = "thinkingmachines/Inkling-Small"
SERVED_NAME = "inkling-small"

# (quant tag, total GB of weights) smallest -> largest, from the Hub file listing.
GGUF_QUANTS = [
    ("UD-IQ1_S", 74.8), ("UD-IQ1_M", 78.8), ("UD-IQ2_XXS", 82.3), ("UD-Q2_K_XL", 87.9),
    ("UD-IQ3_XXS", 97.9), ("UD-Q3_K_XL", 119.6), ("UD-IQ4_XS", 127.4), ("UD-Q4_K_XL", 163.3),
    ("UD-Q5_K_XL", 196.7), ("UD-Q6_K", 218.9), ("Q8_0", 280.3),
]
NVFP4_VRAM_GB = 180.0   # HF deployment table: 1x B300 (W4A4) or 2x H200 (W4A16)
BF16_VRAM_GB = 600.0    # HF deployment table: 8x H200
OVERHEAD_GB = 8.0       # OS + KV cache headroom at a modest context
HEADROOM = 1.10


def detect() -> dict:
    ram_gb = 0.0
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    ram_gb = int(line.split()[1]) / 1e6
    except OSError:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            ram_gb = int(out.stdout.strip() or 0) / 1e9
    gpus: list[float] = []
    if shutil.which("nvidia-smi"):
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True)
        gpus = [int(x) / 1024 for x in out.stdout.split() if x.strip().isdigit()]
    ram_gb = float(os.getenv("INKLING_FAKE_RAM_GB", ram_gb))
    if os.getenv("INKLING_FAKE_GPU_GB") is not None:
        gpus = [float(x) for x in os.getenv("INKLING_FAKE_GPU_GB", "").split(",") if x]
    return {"ram_gb": round(ram_gb, 1), "gpu_gb": [round(g, 1) for g in gpus]}


def plan(ram_gb: float, gpu_gb: list[float], engine: str = "auto") -> dict:
    vram = sum(gpu_gb)
    if engine in {"auto", "vllm", "sglang"} and vram >= BF16_VRAM_GB * HEADROOM:
        return {"ok": True, "engine": "sglang" if engine == "sglang" else "vllm", "repo": REPO_BF16, "quant": "BF16", "tp": len(gpu_gb), "weights_gb": BF16_VRAM_GB}
    if engine in {"auto", "vllm", "sglang"} and vram >= NVFP4_VRAM_GB * HEADROOM and len(gpu_gb) >= 1:
        return {"ok": True, "engine": "sglang" if engine == "sglang" else "vllm", "repo": REPO_NVFP4, "quant": "NVFP4", "tp": len(gpu_gb), "weights_gb": NVFP4_VRAM_GB}
    if engine in {"vllm", "sglang"}:
        return {"ok": False, "reason": f"{engine} needs >= {NVFP4_VRAM_GB * HEADROOM:.0f} GB total GPU memory for Inkling-Small NVFP4; this machine has {vram:.0f} GB."}
    budget = (ram_gb + vram - OVERHEAD_GB) / HEADROOM
    fitting = [q for q in GGUF_QUANTS if q[1] <= budget]
    if not fitting:
        need = GGUF_QUANTS[0][1] * HEADROOM + OVERHEAD_GB
        return {"ok": False, "reason": f"Inkling-Small needs at least ~{need:.0f} GB of RAM+VRAM combined (smallest real build {GGUF_QUANTS[0][0]} is {GGUF_QUANTS[0][1]} GB). This machine has {ram_gb:.0f} GB RAM + {vram:.0f} GB VRAM. Not substituting a smaller model."}
    tag, size = fitting[-1]
    return {"ok": True, "engine": "llamacpp", "repo": REPO_GGUF, "quant": tag, "weights_gb": size, "gpu_offload": vram > 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="auto", choices=["auto", "llamacpp", "vllm", "sglang"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    hw = detect()
    result = {"hardware": hw, "served_model_name": SERVED_NAME, **plan(hw["ram_gb"], hw["gpu_gb"], args.engine)}
    print(json.dumps(result) if args.json else "\n".join(f"{k}: {v}" for k, v in result.items()))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
