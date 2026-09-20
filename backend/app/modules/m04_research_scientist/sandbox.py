from dataclasses import dataclass
from pathlib import Path
import asyncio

@dataclass(frozen=True)
class SandboxLimits:
    cpus: float = 2.0
    memory: str = "8g"
    timeout_seconds: int = 3600
    network: str = "none"

async def run_analysis_container(image: str, command: list[str], input_dir: Path, output_dir: Path, limits: SandboxLimits = SandboxLimits()) -> int:
    """Execute approved analysis in ephemeral Docker with no network and bounded resources."""
    args=["docker","run","--rm","--network",limits.network,"--cpus",str(limits.cpus),"--memory",limits.memory,"--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=1g","-v",f"{input_dir}:/input:ro","-v",f"{output_dir}:/output:rw",image,*command]
    process=await asyncio.create_subprocess_exec(*args)
    try:
        return await asyncio.wait_for(process.wait(), limits.timeout_seconds)
    except asyncio.TimeoutError:
        process.kill(); await process.wait(); raise
