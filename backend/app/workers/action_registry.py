"""Registered post-approval executors. Importing a module cannot execute an effect."""
from __future__ import annotations
from typing import Any, Callable

Executor = Callable[[dict[str, Any]], dict[str, Any]]
_EXECUTORS: dict[tuple[int, str], Executor] = {}

def register_executor(module_id: int, action_type: str, executor: Executor) -> None:
    key=(module_id,action_type)
    if key in _EXECUTORS: raise ValueError(f"duplicate approved-action executor: {key}")
    _EXECUTORS[key]=executor

def require_executor(module_id: int, action_type: str) -> Executor:
    executor = _EXECUTORS.get((module_id, action_type))
    if executor is None: raise LookupError(f"no approved-action executor registered for {module_id}:{action_type}")
    return executor


def execute_registered(module_id: int, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    executor=_EXECUTORS.get((module_id,action_type))
    if executor is None: raise LookupError(f"no approved-action executor registered for {module_id}:{action_type}")
    result=executor(payload)
    if not isinstance(result,dict): raise TypeError("approved-action executor must return a mapping")
    return result


# M10 has no production conditional adapter until provider support is verified.
_CONDITIONAL_EXECUTORS: dict[tuple[int, str], Any] = {}


def register_conditional_executor(module_id: int, action_type: str, adapter: Any) -> None:
    key = (module_id, action_type)
    if key in _CONDITIONAL_EXECUTORS or not callable(getattr(adapter, "dispatch_if_current", None)):
        raise ValueError("conditional adapter must implement dispatch_if_current and register once")
    _CONDITIONAL_EXECUTORS[key] = adapter


def require_conditional_executor(module_id: int, action_type: str) -> Any:
    from app.modules.m00_approval_center.service import ApprovalConflictError
    adapter = _CONDITIONAL_EXECUTORS.get((module_id, action_type))
    if adapter is None:
        raise ApprovalConflictError("conditional dispatch unavailable; M10 dispatch refused, no risk acceptance configured")
    return adapter
