"""Approved scientific tool adapters. Execution belongs in an isolated worker container."""
from dataclasses import dataclass
from pathlib import Path
import asyncio, os
import httpx

@dataclass(frozen=True)
class ToolResult:
    tool: str
    command: list[str] | None
    artifacts: list[str]
    detail: str

async def run_local_tool(command: list[str], workdir: Path, timeout_seconds: int = 3600) -> ToolResult:
    process = await asyncio.create_subprocess_exec(*command, cwd=workdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env={"PATH": os.getenv("PATH", "")})
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
    if process.returncode != 0:
        raise RuntimeError(f"tool failed ({process.returncode}): {stderr.decode()[-2000:]}")
    return ToolResult(command[0], command, [], stdout.decode()[-4000:])

class AutoDockVinaAdapter:
    async def dock(self, receptor: Path, ligand: Path, config: Path, output: Path) -> ToolResult:
        result = await run_local_tool(["vina", "--receptor", str(receptor), "--ligand", str(ligand), "--config", str(config), "--out", str(output)], receptor.parent)
        return ToolResult("autodock-vina", result.command, [str(output)], result.detail)

class PyMOLAdapter:
    async def render(self, script: Path, workdir: Path) -> ToolResult:
        return await run_local_tool(["pymol", "-cq", str(script)], workdir)

class GalaxyAdapter:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url, self.api_key = base_url.rstrip("/"), api_key
    async def run_workflow(self, workflow_id: str, history_id: str, inputs: dict) -> ToolResult:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/api/workflows/{workflow_id}/invocations", headers={"x-api-key": self.api_key}, json={"history": f"hist_id={history_id}", "inputs": inputs})
        response.raise_for_status(); data=response.json()
        return ToolResult("galaxy", None, [], f"invocation_id={data.get('id')}")

class ColabFoldAdapter:
    """Local ColabFold batch adapter. Public servers require their own documented client/rate policy."""
    async def predict(self, fasta: Path, output_dir: Path) -> ToolResult:
        result = await run_local_tool(["colabfold_batch", str(fasta), str(output_dir)], fasta.parent, 14400)
        return ToolResult("colabfold", result.command, [str(output_dir)], result.detail)
