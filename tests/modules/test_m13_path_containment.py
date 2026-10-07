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
    def get(self,approval_id):raise KeyError(approval_id)  # m00 ApprovalNotFoundError is a KeyError
@pytest.mark.asyncio
async def test_submit_unknown_approval_maps_to_permission_error():
    service=Service(_NoSessions(),_MissingApprovals(),_NoStore())
    with pytest.raises(PermissionError,match="approval not found"):
        await service.submit("tenant-1","session-1","#go",{"a":"b"},"no-such-approval")
