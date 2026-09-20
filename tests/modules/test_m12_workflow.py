import pytest
from app.modules.m12_ai_research_lab.workflow import *
def test_yaml_dag_validation():
    wf=Workflow.from_yaml("name: x\nnodes:\n- {id: a, task: model}\n- {id: b, task: model, depends_on: [a]}\n")
    assert wf.nodes[1].depends_on==("a",)
def test_cycle_rejected():
    with pytest.raises(WorkflowValidationError): Workflow.from_yaml("nodes:\n- {id: a, task: x, depends_on: [b]}\n- {id: b, task: x, depends_on: [a]}\n")
@pytest.mark.asyncio
async def test_engine_passes_declared_parent_outputs():
    async def runner(task,config,ctx): return {"parents":list(ctx["parents"])}
    wf=Workflow.from_yaml("nodes:\n- {id: a, task: x}\n- {id: b, task: x, depends_on: [a]}\n")
    out=await DagEngine(runner).run(wf,{})
    assert out["b"]["parents"]==["a"]
