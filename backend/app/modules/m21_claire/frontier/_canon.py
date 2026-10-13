from __future__ import annotations
import json
from typing import Any

def canonical_json(value: Any) -> str:
    # allow_nan=False: NaN/Infinity are not valid JSON and would make hashes ambiguous.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
