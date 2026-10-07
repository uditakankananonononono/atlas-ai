"""Pins for M13 artifact path containment and unknown-approval error mapping.

Artifact ids that become filesystem path segments are validated: separators
and the traversal segments "." / ".." are rejected before any directory is
created or file written. Service.submit maps an unknown approval id to
PermissionError (409 at the route), matching the sibling submit flows.

Establishes input validation and error mapping only; no device authority,
no real screenshots, no approval-semantics change.
"""
import pytest
from app.modules.m13_browser_agent import security
from app.modules.m13_browser_agent.playwright_adapter import PlaywrightSessions
from app.modules.m13_browser_agent.service import Service
from app.modules.m13_browser_agent.session_bridge.protocol import make_pc_session,split_pc_session
def test_safe_artifact_segment_rejects_traversal_and_separators():
    for bad in ("..",".","../x","a/b","a\\b","",None):
        with pytest.raises(ValueError):security.safe_artifact_segment(bad)
    assert security.safe_artifact_segment("pc.dev01.local-form")== "pc.dev01.local-form"
    assert security.safe_artifact_segment("name.with.dots")=="name.with.dots"
def test_split_pc_session_rejects_traversal_local_names():
    device,name=split_pc_session("pc.dev01.local-form")
    assert (device,name)==("dev01","local-form")
    assert split_pc_session("pc.dev01.name.with.dots")==("dev01","name.with.dots")
    for bad in ("pc.dev01/..","pc.dev01/../x","pc.dev01/a/b","pc.dev01/..\\x","pc.dev01."):
        with pytest.raises(ValueError):split_pc_session(bad)
def test_playwright_check_id_rejects_dot_segments():
    check=PlaywrightSessions._check_id
    assert check("tenant-1")=="tenant-1"
    for bad in ("..",".","a/b",""):
        with pytest.raises(ValueError):check(bad)
class _NoSessions:
    async def page(self,*a):raise AssertionError("must not open a page for an invalid id")
class _NoStore:
    async def append_audit(self,*a):raise AssertionError("must not audit an invalid id")
@pytest.mark.asyncio
async def test_screenshot_rejects_dotdot_before_touching_disk(tmp_path):
    service=Service(_NoSessions(),None,_NoStore(),artifact_root=str(tmp_path))
    with pytest.raises(ValueError):await service.screenshot("tenant-1","..")
    assert list(tmp_path.iterdir())==[]  # nothing created outside or inside
class _MissingApprovals:
    def get(self,approval_id):
        from app.modules.m00_approval_center.service import ApprovalNotFoundError
        raise ApprovalNotFoundError(approval_id)
@pytest.mark.asyncio
async def test_submit_unknown_approval_maps_to_permission_error():
    service=Service(_NoSessions(),_MissingApprovals(),_NoStore())
    with pytest.raises(PermissionError,match="approval not found"):
        await service.submit("tenant-1","session-1","#go",{"a":"b"},"no-such-approval")
class _BuggyApprovals:
    def get(self,approval_id):raise KeyError("internal-payload-bug")  # not a lookup miss
@pytest.mark.asyncio
async def test_submit_internal_keyerror_propagates_unmasked():
    # Establishes only ApprovalNotFoundError is remapped; an internal KeyError
    # from inside the approval store is not masked as "approval not found".
    service=Service(_NoSessions(),_BuggyApprovals(),_NoStore())
    with pytest.raises(KeyError,match="internal-payload-bug"):
        await service.submit("tenant-1","session-1","#go",{"a":"b"},"a1")
def test_artifact_directory_rejects_path_bearing_tenant(tmp_path):
    # The BridgedSessions/HybridSessions screenshot sites build the artifact
    # path through this helper before any page lookup; it is their only guard.
    for bad in ("..","../evil","a/b","a\\b",""):
        with pytest.raises(ValueError):security.artifact_directory(tmp_path,bad,"session-1")
    ok=security.artifact_directory(tmp_path,"tenant-1","session-1")
    assert ok.is_relative_to(tmp_path.resolve())
@pytest.mark.asyncio
async def test_screenshot_refuses_preexisting_symlinked_tenant_dir(tmp_path):
    # Segment charset alone trusts directory entries: a pre-existing symlink at
    # root/<tenant> would let mkdir/write escape the root. Resolution-time
    # containment must reject before any directory or file is created outside.
    # Scope: pre-existing symlinks only, under a trusted root. A swap of the
    # session directory for a symlink AFTER the check (TOCTOU race) is not
    # caught - this is not atomic filesystem confinement.
    outside=tmp_path.parent/"outside-m13";outside.mkdir(exist_ok=True)
    root=tmp_path/"art";root.mkdir()
    (root/"tenant-1").symlink_to(outside,target_is_directory=True)
    service=Service(_NoSessions(),None,_NoStore(),artifact_root=str(root))
    with pytest.raises(ValueError):await service.screenshot("tenant-1","session-1")
    assert list(outside.iterdir())==[]

@pytest.mark.asyncio
async def test_bridge_screenshot_validates_tenant_before_page_lookup():
    # A path-bearing tenant must be rejected by the containment helper BEFORE
    # any page is opened: validation ordered after the page lookup would still
    # reject, but only after touching the session. Establishes ordering only,
    # not daemon confinement.
    from app.modules.m13_browser_agent.session_bridge.dispatch import BridgedSessions
    bridge=object.__new__(BridgedSessions)
    async def _page(*a):raise AssertionError("page must not open for an invalid tenant")
    bridge.page=_page
    with pytest.raises(ValueError):
        await bridge.screenshot("../evil","pc.dev01.local-form")
