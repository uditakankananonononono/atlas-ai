"""Validators raise PublicValidationError(reason, detail) when the *reason* is a fixed, owner-controlled string.
The global 422 handler echoes only `.reason` (never `detail`, which may hold caller input such as ids/keys)."""
from __future__ import annotations


class PublicValidationError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        if not reason or len(reason) > 120:
            raise ValueError("reason must be a short fixed string")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class PublicLookupError(LookupError):
    """Not-found style error with a fixed public reason; `detail` (ids, labels) is never sent."""
    def __init__(self, reason: str, detail: str = "") -> None:
        if not reason or len(reason) > 120:
            raise ValueError("reason must be a short fixed string")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def public_reason(error: Exception, generic: str = "invalid input") -> str:
    """Client-safe text for a caught ValueError: the fixed reason of a PublicValidationError, else a fixed generic string.
    str(error) is never returned (it can include caller-derived detail)."""
    return error.reason if isinstance(error, (PublicValidationError, PublicLookupError)) else generic
