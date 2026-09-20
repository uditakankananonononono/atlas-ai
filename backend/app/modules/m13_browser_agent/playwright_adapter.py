from __future__ import annotations
from pathlib import Path
from playwright.async_api import async_playwright
class PlaywrightSessions:
    """One tenant-scoped context per session. HAR is recorded at context creation."""
    def __init__(self,root:str="/tmp/atlas-browser"): self.root=Path(root); self._pw=None; self._browser=None; self._contexts={}
    async def start(self): self._pw=await async_playwright().start(); self._browser=await self._pw.chromium.launch(headless=True)
    async def close(self):
        for ctx in self._contexts.values(): await ctx.close()
        if self._browser: await self._browser.close()
        if self._pw: await self._pw.stop()
    async def page(self,tenant_id:str,session_id:str,persistent:bool):
        key=(tenant_id,session_id); path=self.root/tenant_id/session_id; path.mkdir(parents=True,exist_ok=True)
        if key not in self._contexts:
            self._contexts[key]=await self._browser.new_context(record_har_path=str(path/"audit.har"))
        pages=self._contexts[key].pages
        return pages[0] if pages else await self._contexts[key].new_page()
