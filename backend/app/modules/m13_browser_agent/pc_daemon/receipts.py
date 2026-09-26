"""Hash-chained action receipts, in the M21 audit format the server verifies."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class ReceiptChain:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self._events: list[dict[str, Any]] = []

    def append(self, action_id: str, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self._events[-1]["event_hash"] if self._events else "0" * 64
        sequence = len(self._events) + 1
        body = json.dumps({"sequence": sequence, "device_id": self.device_id,
                           "action_id": action_id, "phase": phase, "payload": payload,
                           "previous_hash": previous}, sort_keys=True, default=str)
        event = {"sequence": sequence, "device_id": self.device_id, "action_id": action_id,
                 "phase": phase, "payload": payload, "previous_hash": previous,
                 "event_hash": hashlib.sha256(body.encode()).hexdigest()}
        self._events.append(event)
        return event

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)
