"""Validators raise PublicValidationError(reason, detail) when the *reason* is a fixed, owner-controlled string.
The global 422 handler echoes only `.reason` (never `detail`, which may hold caller input such as ids/keys)."""
from __future__ import annotations


class PublicValidationError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        if not reason or len(reason) > 120:
            raise ValueError("reason must be a short fixed string")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
