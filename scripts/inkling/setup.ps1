# Windows: check hardware, pick a real Inkling-Small GGUF that fits, launch llama.cpp.
#   powershell -ExecutionPolicy Bypass -File scripts\inkling\setup.ps1 [-Port 8080] [-DryRun]
# (vLLM/SGLang need Linux or WSL; use setup.sh there.)
param([int]$Port = 8080, [switch]$DryRun)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ramGb = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1e9
$gpu = ""
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  $gpu = ((nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits) | ForEach-Object { [math]::Round([int]$_ / 1024, 1) }) -join ","
}
$env:INKLING_FAKE_RAM_GB = [math]::Round($ramGb, 1)
$env:INKLING_FAKE_GPU_GB = $gpu
$plan = python "$here\fit.py" --engine llamacpp --json | ConvertFrom-Json
if (-not $plan.ok) { Write-Error "Inkling-Small can't run here: $($plan.reason)"; exit 2 }
$args = @("-hf", "$($plan.repo):$($plan.quant)", "--alias", $plan.served_model_name, "--host", "127.0.0.1", "--port", "$Port", "--jinja", "-c", "16384")
if ($plan.gpu_offload) { $args += @("-ngl", "999", "--cpu-moe") }
"ATLAS_LOCAL_OPENAI_URL=http://127.0.0.1:$Port/v1`nATLAS_LOCAL_OPENAI_MODEL=$($plan.served_model_name)" | Set-Content -Encoding ascii ".env.inkling"
Write-Host "Plan: llama.cpp, $($plan.repo) ($($plan.quant)). Env written to .env.inkling."
Write-Host "Command: llama-server $($args -join ' ')"
if ($DryRun) { exit 0 }
if (-not (Get-Command llama-server -ErrorAction SilentlyContinue)) { Write-Error "llama-server not found. Install: winget install llama.cpp"; exit 3 }
& llama-server @args
