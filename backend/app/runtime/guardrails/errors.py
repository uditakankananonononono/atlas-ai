"""Shared refusal type for the guardrail enforcement layer.

A GuardrailRefusal is a verdict: the gate evaluated the request and refused
it. It is never raised for malformed input - callers raising ValueError for
shape/type violations follow the same convention as the underlying contract
modules (P68/P69/P70, m02 reviewed_execution). A refusal carries a stable
machine code so callers, receipts and tests can pin the exact rule that fired.
"""
from __future__ import annotations


class GuardrailRefusal(RuntimeError):
    """A guardrail evaluated the request and refused it.

    code: stable machine code, e.g. "BIOGATE:prohibited_bio:pathogen_enhancement".
    details: small JSON-able dict with the evidence behind the refusal
    (matched pattern, missing evidence kinds, shortfall counts). Never carries
    secrets, credentials or payload bodies.
    ledger: when the gate appended the refusal verdict to its ledger before
    raising, the extended ledger, so the refusal is durable evidence.
    """

    def __init__(self, code: str, message: str, details: dict | None = None,
                 ledger: list | None = None) -> None:
        if type(code) is not str or not code.strip():
            raise ValueError("refusal code must be non-blank text")
        if type(message) is not str or not message.strip():
            raise ValueError("refusal message must be non-blank text")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = dict(details or {})
        # When the refusing gate ledgered the refusal verdict before raising,
        # the extended ledger rides on the refusal so the caller (enforcer)
        # can persist it. None means the gate kept no ledger change.
        self.ledger = ledger

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


__all__ = ["GuardrailRefusal"]
