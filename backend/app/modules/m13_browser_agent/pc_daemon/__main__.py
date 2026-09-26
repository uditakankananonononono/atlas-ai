"""CLI for the paired-PC daemon.

  python -m app.modules.m13_browser_agent.pc_daemon pair --server URL --nonce N --code 123456 --name "My laptop"
  python -m app.modules.m13_browser_agent.pc_daemon run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import DEFAULT_STATE_DIR, DaemonConfig
from .daemon import Daemon, DeviceIdentity, pair_with_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas-pc-daemon")
    sub = parser.add_subparsers(dest="command", required=True)

    pair = sub.add_parser("pair", help="pair this PC with your Atlas server")
    pair.add_argument("--server", required=True)
    pair.add_argument("--nonce", required=True)
    pair.add_argument("--code", required=True)
    pair.add_argument("--name", default="My PC")
    pair.add_argument("--capabilities", nargs="+",
                      default=["navigate", "extract", "screenshot", "read_values", "social_read"])
    pair.add_argument("--pacing-seconds", type=float, default=None)

    run = sub.add_parser("run", help="connect to Atlas and serve commands")
    run.add_argument("--cdp-url", default=None,
                     help="attach to an already-running browser, e.g. http://127.0.0.1:9222")
    run.add_argument("--config", default=str(DEFAULT_STATE_DIR / "config.json"))

    args = parser.parse_args(argv)
    if args.command == "pair":
        config = pair_with_server(args.server, args.nonce, args.code, name=args.name,
                                  capabilities=args.capabilities, pacing_seconds=args.pacing_seconds,
                                  key_path=Path(DEFAULT_STATE_DIR / "device_key.pem"),
                                  config_path=Path(DEFAULT_STATE_DIR / "config.json"))
        print(f"Paired as device {config.device_id}. Credentials stored in {DEFAULT_STATE_DIR}.")
        return 0
    config = DaemonConfig.load(Path(args.config))
    if args.cdp_url:
        config.cdp_url = args.cdp_url
    if not config.device_id or not config.command_secret:
        print("This PC is not paired yet; run the 'pair' command first.", file=sys.stderr)
        return 2
    identity = DeviceIdentity.load_or_create(Path(config.key_path))
    asyncio.run(Daemon(config, identity).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
