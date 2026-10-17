import asyncio, pytest
from app.core.providers import ProviderOutcomeUnknown, ProviderError
from app.modules.m12_ai_research_lab.workflow import DagEngine, Workflow, Node
from app.modules.m12_ai_research_lab import wiring

def WF(*nodes): return Workflow("w", tuple(Node(i,"t",tuple(d),{}) for i,d in nodes))
def fail_with(exc):
    async def r(task,cfg,ctx):
        if ctx["parents"]: raise exc
        return {"text":"SECRET-OUTPUT"}
    try: asyncio.run(DagEngine(r).run(WF(("a",[]),("b",["a"])),{}))
    except RuntimeError as e: return e
    raise AssertionError("no error")

def test_unknown_outcome_maps_to_409_no_retry_without_leaks():
    e=fail_with(ProviderOutcomeUnknown("provider said: api_key=abc123 body=PRIVATE"))
    status,detail=wiring.workflow_error_response(e)
    assert status==409
    assert detail["state"]=="unknown" and detail["retry_allowed"] is False
    blob=repr(detail)
    assert "abc123" not in blob and "PRIVATE" not in blob and "SECRET-OUTPUT" not in blob
    assert detail["completed_nodes"]==["a"] and detail["failed_node"]=="b"

def test_unknown_outcome_found_through_cause_chain():
    try:
        try: raise ProviderOutcomeUnknown("x")
        except ProviderOutcomeUnknown as inner: raise ValueError("wrapped") from inner
    except ValueError as mid: e=fail_with(mid)
    assert wiring.workflow_error_response(e)[0]==409

def test_ordinary_node_failure_stays_422_generic():
    status,detail=wiring.workflow_error_response(fail_with(ProviderError("boom")))
    assert status==422 and detail=="node b failed"

def test_review_required_keeps_existing_422_shape():
    from dataclasses import dataclass
    @dataclass
    class Res: text:str="t"
    e=wiring.WorkflowReviewRequired(Res())
    status,detail=wiring.workflow_error_response(e)
    assert status==422 and detail["state"]=="review_required" and detail["retry_allowed"] is False and detail["downstream_executed"] is False
    assert detail["result"]["text"]=="t"
