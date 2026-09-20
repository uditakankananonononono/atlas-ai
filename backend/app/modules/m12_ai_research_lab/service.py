"""Module 12 service: model routing, bounded fallback and YAML DAG execution."""
from .executor import ResearchExecutor, RetryPolicy
from .models import ModelCapability, ModelProvider, ModelResult, RouteRequest, TaskType
from .router import ModelRouter, NoEligibleModel, RouteDecision
from .workflow import DagEngine, Workflow, WorkflowValidationError
class Service(ResearchExecutor):
    """Atlas-facing alias retaining dependency injection for provider/catalog/policy."""
__all__=["Service","RetryPolicy","ModelCapability","ModelProvider","ModelResult","RouteRequest","TaskType","ModelRouter","NoEligibleModel","RouteDecision","DagEngine","Workflow","WorkflowValidationError"]
