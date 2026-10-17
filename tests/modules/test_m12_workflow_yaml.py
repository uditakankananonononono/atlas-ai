import pytest
from app.modules.m12_ai_research_lab.workflow import Workflow, WorkflowValidationError
BAD=['a: [','- 1','nodes: abc','nodes: [1]','nodes: [{task: t}]','nodes: [{id: a}]',
 'nodes: [{id: a, task: t, depends_on: bc}]','nodes: [{id: a, task: t, depends_on: [[1]]}]',
 'nodes: [{id: [1], task: t}]','nodes: [{id: a, task: t, config: x}]','nodes: [{id: "", task: t}]',
 'nodes: [{id: a, task: 5}]','nodes: [{id: a, task: t, depends_on: [1]}]','nodes: {a: 1}']
@pytest.mark.parametrize("y",BAD)
def test_malformed_workflow_is_validation_error(y):
    with pytest.raises(WorkflowValidationError): Workflow.from_yaml(y)
def test_valid_unchanged():
    w=Workflow.from_yaml("name: n\nnodes:\n - {id: a, task: research}\n - {id: b, task: draft, depends_on: [a], config: {prompt: x}}\n")
    assert w.name=="n" and [n.id for n in w.nodes]==["a","b"] and w.nodes[1].depends_on==("a",) and w.nodes[1].config=={"prompt":"x"}
def test_empty_document_unchanged():
    assert Workflow.from_yaml("").nodes==()
