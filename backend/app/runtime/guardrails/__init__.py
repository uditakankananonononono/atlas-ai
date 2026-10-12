"""Guardrail enforcement layer (instinct-doc groups 134-142).

Each gate is an enforced runtime check: the guarded runner only executes the
caller-supplied effect after the gate admits the request, and every decision -
admission or refusal - is appended to the gate's hash-chained ledger. The
gates are pure, deterministic and stdlib-only; callers inject clocks, effects
and approval/verification hooks. See docs/GUARDRAILS_*_CONTRACT.md.
"""
from .errors import GuardrailRefusal

__all__ = ["GuardrailRefusal"]
