"""Registered post-approval executors. Importing a module cannot execute an effect."""
from __future__ import annotations
from typing import Any, Callable

Executor = Callable[[dict[str, Any]], dict[str, Any]]
_EXECUTORS: dict[tuple[int, str], Executor] = {}

def register_executor(module_id: int, action_type: str, executor: Executor) -> None:
    key=(module_id,action_type)
    if key in _EXECUTORS: raise ValueError(f"duplicate approved-action executor: {key}")
    _EXECUTORS[key]=executor

def execute_registered(module_id: int, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    executor=_EXECUTORS.get((module_id,action_type))
    if executor is None: raise LookupError(f"no approved-action executor registered for {module_id}:{action_type}")
    result=executor(payload)
    if not isinstance(result,dict): raise TypeError("approved-action executor must return a mapping")
    return result
