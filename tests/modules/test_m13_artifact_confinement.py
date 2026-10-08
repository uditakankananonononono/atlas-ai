"""M13 artifact confinement: trusted root, swap-proof writes, id validation.

These tests reproduce the reported gap - a session directory swapped for a
symlink after creation, sending screenshot bytes outside the root - and pin
the fix: ids are validated before any filesystem use, and every artifact
byte is written through a pinned root descriptor walk that refuses symlinked
components instead of following them.
"""
import base64
import os
import stat

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m13_browser_agent.artifact_directory import (
    ArtifactContainmentError, ArtifactRoot, validate_segment)
from app.modules.m13_browser_agent.playwright_adapter import PlaywrightSessions
from app.modules.m13_browser_agent.service import Service
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.dispatch import (
    BridgedSessions, HybridSessions)
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry


# -- segment validation ------------------------------------------------------

@pytest.mark.parametrize("bad", ["..", ".", "...", "a/b", "", "x" * 121, "a\x00b", "a b"])
def test_validate_segment_rejects_traversal_and_malformed(bad):
    with pytest.raises(ArtifactContainmentError):
        validate_segment(bad)


@pytest.mark.parametrize("good", ["tenant-1", "pc.dev1.main", "a.b_c", "user@example.com", "t+1"])
def test_validate_segment_accepts_real_ids(good):
    assert validate_segment(good) == good


def test_playwright_sessions_check_id_rejects_dotdot():
    # ".." matched the old charset-only check; it must not reach the disk.
    with pytest.raises(ValueError):
        PlaywrightSessions._check_id("..")


# -- ArtifactRoot primitives ---------------------------------------------------

def test_write_bytes_modes_and_content(tmp_path):
    root = ArtifactRoot(tmp_path / "root")
    path = root.write_bytes(("tenant-1", "session-1"), "shot.png", b"png-bytes")
    assert path.read_bytes() == b"png-bytes"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    root.close()


def test_preexisting_symlink_component_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = ArtifactRoot(tmp_path / "root")
    (root._display / "t").mkdir()
    os.symlink(outside, root._display / "t" / "s")
    with pytest.raises(ArtifactContainmentError):
        root.write_bytes(("t", "s"), "a.png", b"x")
    assert not (outside / "a.png").exists()
    root.close()


def test_planted_symlink_at_filename_is_refused(tmp_path):
    outside_file = tmp_path / "escape.png"
    root = ArtifactRoot(tmp_path / "root")
    root.prepare_dir("t", "s")
    os.symlink(outside_file, root._display / "t" / "s" / "x.png")
    with pytest.raises(ArtifactContainmentError):
        root.write_bytes(("t", "s"), "x.png", b"x")
    assert not outside_file.exists()
    root.close()


def test_swap_after_prepare_dir_is_refused(tmp_path):
    """The reported gap: directory created, then swapped for a symlink."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = ArtifactRoot(tmp_path / "root")
    root.prepare_dir("t", "s")
    os.rmdir(root._display / "t" / "s")
    os.symlink(outside, root._display / "t" / "s")
    with pytest.raises(ArtifactContainmentError):
        root.write_bytes(("t", "s"), "a.png", b"x")
    assert not (outside / "a.png").exists()
    root.close()


def test_write_path_refuses_escape(tmp_path):
    root = ArtifactRoot(tmp_path / "root")
    with pytest.raises(ArtifactContainmentError):
        root.write_path(tmp_path / "elsewhere" / "x.png", b"x")
    kept = root.write_path(root._display / "t" / "x.png", b"data")
    assert kept.read_bytes() == b"data"
    root.close()


# -- Service wiring -------------------------------------------------------------


class _Locator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector


class _CleanPage:
    url = "https://example.com/form"

    def locator(self, selector):
        return _Locator(self, selector)

    async def screenshot(self, **kwargs):
        return b"png-clean"


class _SwappingPage:
    """Swaps the session directory for a symlink mid-screenshot."""

    url = "https://example.com/form"

    def __init__(self, root_path, tenant_id, session_id, outside):
        self._target = root_path / tenant_id / session_id
        self._outside = outside

    def locator(self, selector):
        return _Locator(self, selector)

    async def screenshot(self, **kwargs):
        if self._target.is_dir() and not self._target.is_symlink():
            os.rmdir(self._target)
            os.symlink(self._outside, self._target)
        return b"png-stolen"


class _Sessions:
    def __init__(self, page):
        self._page = page

    async def page(self, *args):
        return self._page


class _Store:
    def __init__(self):
        self.events = []

    async def append_audit(self, event):
        self.events.append(event)

    async def was_consumed(self, approval_id):
        return False

    async def consume(self, approval_id, tenant_id):
        pass


@pytest.mark.asyncio
async def test_service_screenshot_writes_confined(tmp_path):
    store = _Store()
    service = Service(_Sessions(_CleanPage()), None, store, str(tmp_path / "root"))
    path = await service.screenshot("tenant-1", "session-1")
    assert path.startswith(str((tmp_path / "root").resolve()))
    with open(path, "rb") as handle:
        assert handle.read() == b"png-clean"
    assert store.events and store.events[0].payload["sha256"]


@pytest.mark.asyncio
async def test_service_screenshot_survives_mid_write_swap(tmp_path):
    """Fake page swaps the session dir after validation; bytes must not escape."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    # The old flow created the session dir before the page ran; recreate
    # that precondition so the page has something to swap out.
    (root.resolve() / "tenant-1" / "session-1").mkdir(parents=True)
    page = _SwappingPage(root.resolve(), "tenant-1", "session-1", outside)
    service = Service(_Sessions(page), None, _Store(), str(root))
    with pytest.raises(ArtifactContainmentError):
        await service.screenshot("tenant-1", "session-1")
    assert list(outside.iterdir()) == []


@pytest.mark.asyncio
async def test_service_screenshot_rejects_traversal_ids_before_disk_use(tmp_path):
    root = tmp_path / "root"
    service = Service(_Sessions(_CleanPage()), None, _Store(), str(root))
    with pytest.raises(ArtifactContainmentError):
        await service.screenshot("..", "session-1")
    with pytest.raises(ArtifactContainmentError):
        await service.screenshot("tenant-1", "..")
    assert not (tmp_path / "root").exists() or list((tmp_path / "root").iterdir()) == []


# -- bridge wiring -----------------------------------------------------------


class _FakeConnection:
    def __init__(self):
        self.pacing_seconds = 2.0
        self.commands = []

    async def execute(self, kind, args, timeout=60.0):
        self.commands.append({"kind": kind, "args": args})
        if kind is protocol.CommandKind.SCREENSHOT:
            return {"png_base64": base64.b64encode(b"\x89PNG-fake").decode(),
                    "url": "https://example.com"}
        return {"url": "https://example.com"}


class _FakeHub:
    def __init__(self, connection):
        self.connection = connection

    def online(self, device_id):
        return True

    def get(self, device_id):
        return self.connection


def _bridged(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'bridge.db'}")
    Base.metadata.create_all(engine)
    registry = BridgeRegistry(sessionmaker(bind=engine, expire_on_commit=False))
    challenge = registry.create_challenge("t")
    device = registry.confirm_pairing(
        challenge["server_nonce"], challenge["code"], name="laptop",
        public_key="-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n",
        capabilities=["navigate", "extract", "screenshot", "read_values", "fill",
                      "click_nav", "click_submit", "close"])
    sessions = BridgedSessions(registry, _FakeHub(_FakeConnection()),
                               artifact_root=str(tmp_path / "artifacts"))
    return sessions, device


@pytest.mark.asyncio
async def test_bridged_screenshot_confined(tmp_path):
    sessions, device = _bridged(tmp_path)
    session_id = protocol.make_pc_session(device["device_id"], "main")
    path = await sessions.screenshot("t", session_id)
    assert path.startswith(str((tmp_path / "artifacts").resolve()))
    with open(path, "rb") as handle:
        assert handle.read() == b"\x89PNG-fake"


@pytest.mark.asyncio
async def test_bridged_page_path_write_refuses_escape(tmp_path):
    sessions, device = _bridged(tmp_path)
    session_id = protocol.make_pc_session(device["device_id"], "main")
    page = await sessions.page("t", session_id)
    with pytest.raises(ArtifactContainmentError):
        await page.screenshot(path=str(tmp_path / "outside.png"))
    inside = sessions.artifacts.prepare_dir("t") / "kept.png"
    data = await page.screenshot(path=str(inside))
    assert inside.read_bytes() == b"\x89PNG-fake" == data


@pytest.mark.asyncio
async def test_bridged_screenshot_rejects_traversal_tenant(tmp_path):
    sessions, device = _bridged(tmp_path)
    session_id = protocol.make_pc_session(device["device_id"], "main")
    with pytest.raises(ArtifactContainmentError):
        await sessions.screenshot("..", session_id)


# -- hybrid wiring -------------------------------------------------------------


class _ServerPage:
    url = "https://example.com"

    def locator(self, selector):
        return _Locator(self, selector)

    async def screenshot(self, **kwargs):
        return b"png-server"

    async def content(self):
        return "<html/>"


class _ServerSessions:
    def __init__(self):
        self.started = False

    async def start(self):
        self.started = True

    async def close(self):
        pass

    async def page(self, tenant_id, session_id, persistent=False):
        return _ServerPage()

    async def close_session(self, tenant_id, session_id):
        return True


@pytest.mark.asyncio
async def test_hybrid_screenshot_validates_before_any_disk_use(tmp_path):
    artifacts = tmp_path / "artifacts"
    hybrid = HybridSessions(_ServerSessions(), None, artifact_root=str(artifacts))
    # ".." previously created directories from raw ids before validation ran.
    with pytest.raises(ArtifactContainmentError):
        await hybrid.screenshot("..", "session-1")
    assert not artifacts.exists() or all(
        ".." not in part for part in (str(p) for p in artifacts.rglob("*")))


@pytest.mark.asyncio
async def test_hybrid_screenshot_confined_and_bytes_written(tmp_path):
    hybrid = HybridSessions(_ServerSessions(), None, artifact_root=str(tmp_path / "artifacts"))
    path = await hybrid.screenshot("tenant-1", "session-1")
    assert path.startswith(str((tmp_path / "artifacts").resolve()))
    with open(path, "rb") as handle:
        assert handle.read() == b"png-server"


# -- rename pins (reviewer SCOPE FAIL reproduction) ----------------------------


def test_held_fd_rename_write_is_refused(tmp_path):
    """The reviewer's attack: hold the dir fd, rename the dir outside, write."""
    import os as _os
    outside = tmp_path / "outside"
    outside.mkdir()
    root = ArtifactRoot(tmp_path / "root")
    fd = root.open_dir("t", "s")
    _os.rename(root._display / "t" / "s", outside / "s")
    with pytest.raises(ArtifactContainmentError):
        root.write_fd(fd, "x.png", b"x")
    _os.close(fd)
    assert not (outside / "s" / "x.png").exists()
    root.close()


def test_write_bytes_after_rename_stays_contained(tmp_path):
    """write_bytes re-walks from the root: a renamed-away component is
    recreated inside the root, and no byte follows the moved inode."""
    import os as _os
    outside = tmp_path / "outside"
    outside.mkdir()
    root = ArtifactRoot(tmp_path / "root")
    root.prepare_dir("t", "s")
    _os.rename(root._display / "t" / "s", outside / "s")
    path = root.write_bytes(("t", "s"), "a.png", b"data")
    assert str(path).startswith(str(root._display))
    assert path.read_bytes() == b"data"
    assert list((outside / "s").iterdir()) == []
    root.close()


def test_assert_dir_intact_detects_rename_and_symlink(tmp_path):
    import os as _os
    outside = tmp_path / "outside"
    outside.mkdir()
    root = ArtifactRoot(tmp_path / "root")
    root.prepare_dir("t", "s")
    root.assert_dir_intact("t", "s")
    _os.rename(root._display / "t" / "s", outside / "s")
    with pytest.raises(ArtifactContainmentError):
        root.assert_dir_intact("t", "s")
    _os.symlink(outside / "s", root._display / "t" / "s")
    with pytest.raises(ArtifactContainmentError):
        root.assert_dir_intact("t", "s")
    root.close()


# -- HAR post-close detection ---------------------------------------------------


def test_har_verification_passes_when_intact(tmp_path):
    sessions = PlaywrightSessions(root=str(tmp_path / "root"))
    har = sessions._artifacts.prepare_dir("t", "s") / "audit.har"
    har.write_bytes(b"har")
    sessions._verify_har_intact("t", "s", har)
    sessions._artifacts.close()


def test_har_verification_detects_rename_and_swap(tmp_path):
    import os as _os
    outside = tmp_path / "outside"
    outside.mkdir()
    sessions = PlaywrightSessions(root=str(tmp_path / "root"))
    har = sessions._artifacts.prepare_dir("t", "s") / "audit.har"
    har.write_bytes(b"har")
    _os.rename(tmp_path / "root" / "t" / "s", outside / "s")
    with pytest.raises(ArtifactContainmentError):
        sessions._verify_har_intact("t", "s", har)
    _os.symlink(outside / "s", tmp_path / "root" / "t" / "s")
    with pytest.raises(ArtifactContainmentError):
        sessions._verify_har_intact("t", "s", har)
    sessions._artifacts.close()
