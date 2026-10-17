import asyncio, pytest
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m12_ai_research_lab.workflow import DagEngine, Workflow, Node, WorkflowValidationError
from app.modules.m12_ai_research_lab.wiring import workflow_error_response
def run(wf):
    async def r(task,cfg,ctx):
        if task=="unknown": raise ProviderOutcomeUnknown("x PRIVATE")
        if task=="generic": raise ValueError("g")
        return {"ok":task}
    try: asyncio.run(DagEngine(r).run(wf,{}))
    except RuntimeError as e: return e
    raise AssertionError("no error")
@pytest.mark.parametrize("order",[("unknown","generic"),("generic","unknown"),("generic","ok","unknown"),("unknown","ok","generic")])
def test_unknown_wins_in_any_order_and_all_failures_listed(order):
    wf=Workflow("w",tuple(Node(f"n{i}",t,(),{}) for i,t in enumerate(order)))
    e=run(wf); s,d=workflow_error_response(e)
    assert s==409 and d["retry_allowed"] is False
    assert e.failed_nodes==[f"n{i}" for i,t in enumerate(order) if t!="ok"]
    assert "PRIVATE" not in repr(d)
def test_ready_order_follows_workflow_order():
    seen=[]
    async def r(task,cfg,ctx): seen.append(task); return {}
    asyncio.run(DagEngine(r).run(Workflow("w",tuple(Node(c,c,(),{}) for c in "zyxwvu")),{}))
    assert seen==list("zyxwvu")
@pytest.mark.parametrize("raw",["[]","false","0",'""',"[1]"])
def test_falsey_nonmapping_yaml_rejected(raw):
    with pytest.raises(WorkflowValidationError): Workflow.from_yaml(raw)
def test_empty_and_null_yaml_still_empty():
    assert Workflow.from_yaml("").nodes==() and Workflow.from_yaml("null").nodes==() and Workflow.from_yaml("~").nodes==()
