"""Self-hosted Inkling-Small: real hardware planning and launcher behaviour (dry-run)."""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inkling_fit", ROOT / "scripts/inkling/fit.py")
fit = importlib.util.module_from_spec(spec); spec.loader.exec_module(fit)


def test_refuses_instead_of_downgrading_on_a_normal_pc():
    out = fit.plan(32, [8])
    assert out["ok"] is False and "Not substituting a smaller model" in out["reason"]


def test_big_ram_pc_gets_largest_fitting_real_inkling_small_gguf():
    out = fit.plan(128, [24])
    assert out == {"ok": True, "engine": "llamacpp", "repo": "unsloth/Inkling-Small-GGUF", "quant": "UD-IQ4_XS", "weights_gb": 127.4, "gpu_offload": True}


def test_gpu_server_gets_vllm_nvfp4_with_tensor_parallel():
    out = fit.plan(512, [141, 141])
    assert (out["engine"], out["repo"], out["tp"]) == ("vllm", "thinkingmachines/Inkling-Small-NVFP4", 2)


def test_eight_h200_gets_full_precision():
    assert fit.plan(1024, [141] * 8)["repo"] == "thinkingmachines/Inkling-Small"


def test_forcing_vllm_without_gpus_explains_the_floor():
    out = fit.plan(256, [], "vllm")
    assert out["ok"] is False and "198 GB" in out["reason"]


def test_every_plan_serves_inkling_small_only():
    for ram, gpus in [(96, []), (200, [48]), (512, [141, 141])]:
        out = fit.plan(ram, gpus)
        assert out["ok"] and "Inkling-Small" in out["repo"]


def _run(tmp_path, ram, gpus, *extra):
    env = {**os.environ, "INKLING_FAKE_RAM_GB": str(ram), "INKLING_FAKE_GPU_GB": gpus, "ATLAS_ENV_FILE": str(tmp_path / ".env.inkling")}
    return subprocess.run(["bash", str(ROOT / "scripts/inkling/setup.sh"), "--dry-run", *extra], env=env, capture_output=True, text=True)


def test_setup_dry_run_writes_atlas_env_and_llamacpp_command(tmp_path):
    res = _run(tmp_path, 128, "24", "--port", "8099")
    assert res.returncode == 0, res.stderr
    assert "llama-server -hf unsloth/Inkling-Small-GGUF:UD-IQ4_XS --alias inkling-small" in res.stdout
    env = (tmp_path / ".env.inkling").read_text()
    assert "ATLAS_LOCAL_OPENAI_URL=http://127.0.0.1:8099/v1" in env and "ATLAS_LOCAL_OPENAI_MODEL=inkling-small" in env


def test_setup_refuses_on_small_machine_and_writes_nothing(tmp_path):
    res = _run(tmp_path, 32, "8")
    assert res.returncode == 2 and "can't run here" in res.stderr
    assert not (tmp_path / ".env.inkling").exists()


def test_setup_vllm_command_matches_published_recipe(tmp_path):
    res = _run(tmp_path, 512, "141,141")
    assert "vllm serve thinkingmachines/Inkling-Small-NVFP4 --trust-remote-code --tokenizer-mode inkling --tensor-parallel-size 2" in res.stdout
    assert "--served-model-name inkling-small" in res.stdout
