"""Daemon configuration: JSON file plus CLI overrides, free-first defaults."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_STATE_DIR = Path.home() / ".atlas-pc"


@dataclass
class DaemonConfig:
    server_url: str = ""                     # e.g. https://atlas.example.com
    device_id: str = ""
    command_secret: str = ""
    key_path: str = str(DEFAULT_STATE_DIR / "device_key.pem")
    profile_dir: str = str(DEFAULT_STATE_DIR / "browser-profile")
    cdp_url: str | None = None               # e.g. http://127.0.0.1:9222 to attach to her Chrome
    pacing_seconds: float = 5.0
    capabilities: list[str] = field(default_factory=lambda: ["navigate", "extract", "screenshot", "read_values"])
    command_timeout_seconds: float = 90.0
    # Session pages run in their own browser context (see BrowserHandle._session_context).
    isolate_session_context: bool = True
    browser_args: list[str] = field(default_factory=list)
    # Hosts the guarded session may resolve (the site). With them, a browser the daemon launches gets
    # --host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE <hosts>" so a secret cannot leave as a DNS name.
    site_hosts: list[str] = field(default_factory=list)
    # Over CDP the daemon cannot set launch flags. The owner must attest that the attached browser was
    # started with them (see BrowserHandle.launch_args); the daemon then also runs a live UDP probe.
    cdp_containment_attested: bool = False
    # Consumed submit tokens/approvals survive a daemon restart here (audit finding F2).
    consumed_path: str = str(DEFAULT_STATE_DIR / "consumed_submit.json")

    @classmethod
    def load(cls, path: Path) -> "DaemonConfig":
        data = json.loads(path.read_text())
        return cls(**{key: value for key, value in data.items() if key in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))
        path.chmod(0o600)
