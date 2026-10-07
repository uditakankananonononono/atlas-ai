from app.modules.m20_general_cognitive_worker.local_tools import register_local_tools
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry
from app.modules.m20_general_cognitive_worker.schemas import Risk


def test_local_catalog_is_read_only_bounded_registered_handlers():
    registry=ToolRegistry();register_local_tools(registry)
    expected={'rule_check','require_value','temporal_check','csv_filter','csv_reconcile','csv_summary'}
    assert {row['name'] for row in registry.describe()}==expected
    assert {row['function']['name'] for row in registry.function_schemas()}==expected
    for name in expected:
        spec=registry.get(name).spec
        assert spec.risk==Risk.READ and spec.max_retries==1
        assert spec.parameters['type']=='object' and spec.parameters['additionalProperties'] is False
