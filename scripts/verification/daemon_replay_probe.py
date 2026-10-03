"""Run with PYTHONPATH=backend python scripts/verification/daemon_replay_probe.py.

Works on baseline and repair. Fake clicks only; no Playwright or real submits.
"""
import asyncio
import inspect
import tempfile
import time
from pathlib import Path

from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon, DeviceIdentity
from app.modules.m13_browser_agent.session_bridge import protocol as p


class Browser:
    url = "about:blank"

    def __init__(self):
        self.clicks = 0

    async def page(self, session):
        await asyncio.sleep(0)
        return self

    def locator(self, selector):
        return self

    async def click(self):
        self.clicks += 1
        await asyncio.sleep(0)


async def probe(mode):
    with tempfile.TemporaryDirectory() as td:
        c = DaemonConfig(device_id="probe", command_secret="test-only", pacing_seconds=0,
                         capabilities=["click_submit"], key_path=td + "/key")
        identity = DeviceIdentity.load_or_create(Path(c.key_path))
        browser = Browser()

        def make():
            d = Daemon(c, identity)
            d.browser = browser
            return d
        args = dict(session="s", approval_id="a", selector="#go", capture_sha256="c"*64,
                    values_digest="d"*64)
        claims = {k: v for k, v in args.items() if k != "session"}
        if "device_id" in inspect.signature(p.submit_token).parameters:
            args["expires_at"] = int(time.time()) + 120
            claims.update(device_id=c.device_id, session="s", expires_at=args["expires_at"])
        args["token"] = p.submit_token(c.command_secret, **claims)
        cmd = p.make_command(p.CommandKind.CLICK_SUBMIT, args, command_id="same")
        d = make()
        if mode == "concurrent":
            answers = await asyncio.gather(d.execute(cmd), make().execute(cmd))
        else:
            answers = [await d.execute(cmd)]
            if mode == "restart":
                d = make()
            if mode == "different-command-id":
                cmd = {**cmd, "id": "different"}
            answers.append(await d.execute(cmd))
        print(f"{mode}: ok={[a['ok'] for a in answers]}, fake clicks={browser.clicks}")
        return browser.clicks


async def main():
    counts = [await probe(mode) for mode in
              ("serial", "concurrent", "restart", "different-command-id")]
    if "device_id" in inspect.signature(p.submit_token).parameters:
        assert counts == [1, 1, 1, 1], counts
    else:
        assert counts == [2, 2, 2, 2], counts


if __name__ == "__main__":
    asyncio.run(main())
