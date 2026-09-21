"""Named evidence for GCW technical-spec tool-integration rows 189-194."""
import pytest

from app.runtime.technical_spec_166_198 import execute


def request(**changes):
    value = {
        "tenant_id": "tenant-one",
        "actor_id": "owner-one",
        "routes": [
            {"route": "browser", "name": "site-ui", "free": True},
            {"route": "api", "name": "paid-api", "free": False},
        ],
    }
    value.update(changes)
    return value


def test_row_189_typed_registry_selects_browser_when_no_free_api_and_emits_audit():
    result = execute(189, request(tools=[{
        "name": "submit_application", "description": "Use the site",
        "parameters": {"type": "object"}, "preconditions": ["signed_in"],
    }]))["result"]
    assert result["mechanism"] == "typed_registry_with_ui_routes"
    assert result["selected_route"] == "browser"
    assert result["audit_log"]["event"] == "gcw_tool_route_planned"
    assert result["isolation_key"] == "tenant-one:owner-one"
    assert result["evidence"] == [] and result["honest_completion"] is False


def test_row_190_python_sandbox_preserves_api_when_available_and_validates_types():
    result = execute(190, request(
        expression="6*7",
        routes=[{"route": "api", "name": "free-api", "free": True}],
    ))["result"]
    assert result["mechanism"] == "sandbox_or_compliant_ui_route"
    assert result["selected_route"] == "api" and result["result"] == 42
    with pytest.raises(ValueError, match="invalid tool-integration request"):
        execute(190, request(expression="2+2", routes=[{"route": "api"}]))


def test_row_191_shell_keeps_permission_boundary_and_actor_isolation():
    first = execute(191, request(command=["ls"]))["result"]
    second = execute(191, request(actor_id="owner-two", command=["ls"]))["result"]
    assert first["mechanism"] == "permission_bounded_shell_with_ui_route"
    assert first["execute"] is False and first["workspace_only"] is True
    assert first["isolation_key"] != second["isolation_key"]
    with pytest.raises(ValueError, match="permission boundary"):
        execute(191, request(command=["curl", "https://example.test"]))


def test_row_192_search_free_first_order_and_final_submit_approval_gate():
    result = execute(192, request(
        query="public scholarships",
        final_submit=True,
        routes=[
            {"route": "api", "name": "paid-search", "free": False},
            {"route": "paired_pc", "name": "free-search-ui", "free": True},
        ],
    ))["result"]
    assert result["mechanism"] == "public_search_api_or_compliant_ui"
    assert result["selected_route"] == "paired_pc"
    assert result["free_first_order"] == ["free-search-ui", "paid-search"]
    assert result["status"] == "waiting_approval" and result["approval_required"] is True
    assert result["approval_granted"] is False


def test_row_193_workspace_route_fails_honestly_when_site_blocks_automation():
    result = execute(193, request(
        path="workspace/report.md", operation="write",
        automation_blocked=True, block_reason="site presented an automation challenge",
    ))["result"]
    assert result["mechanism"] == "owner_workspace_or_paired_pc_ui"
    assert result["status"] == "blocked"
    assert result["failure"] == "site presented an automation challenge"
    assert result["honest_completion"] is False and result["evidence"] == []
    assert result["audit_log"]["status"] == "blocked"


def test_row_194_rest_paid_only_falls_back_to_github_build_test_deploy_pipeline():
    result = execute(194, request(
        routes=[{"route": "api", "name": "paid-vendor-api", "free": False}],
        github_repository="https://github.com/example/atlas-ai",
        native_build_allowed=True,
    ))["result"]
    assert result["mechanism"] == "allowlisted_api_or_compliant_ui_or_native_build"
    assert result["selected_route"] == "native_build_pipeline"
    assert result["paid_route_declined"] is True
    assert result["pipeline"] == ["discover", "implement", "test", "review", "deploy_after_approval"]
    assert result["status"] == "proposal" and result["approval_required"] is True


def test_rows_189_194_reject_missing_tenant_or_actor_and_do_not_fabricate_evidence():
    for row in range(189, 195):
        with pytest.raises(ValueError, match="invalid tool-integration request"):
            execute(row, {"tenant_id": "tenant-only"})
