from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_hash(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_id: str
    code_version: str
    seed: int
    parameters: dict[str, Any]
    input_hashes: dict[str, str]
    output_hashes: dict[str, str]
    python_version: str
    platform: str

    @classmethod
    def create(cls, code_version: str, seed: int, parameters: dict[str, Any], inputs: dict[str, Any], outputs: dict[str, Any]) -> "RunManifest":
        input_hashes = {key: content_hash(value) for key, value in sorted(inputs.items())}
        output_hashes = {key: content_hash(value) for key, value in sorted(outputs.items())}
        identity = content_hash({"code_version": code_version, "seed": seed, "parameters": parameters,
                                 "inputs": input_hashes, "outputs": output_hashes})[7:23]
        return cls(f"run-{identity}", code_version, seed, parameters, input_hashes, output_hashes,
                   platform.python_version(), platform.platform())

    def write(self, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(canonical_json(asdict(self)) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return path


@contextmanager
def deterministic_random(seed: int) -> Iterator[random.Random]:
    """Yield an isolated RNG; global random state is never mutated."""
    yield random.Random(seed)
