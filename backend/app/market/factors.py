from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class Factor:
    key: str
    value: float
    unit: str | None
    path: str

class FactorPipeline:
    """Derives only real numeric/categorical variables present in wired records."""
    def extract(self, source: str, payload: dict[str, Any]) -> list[Factor]:
        output: list[Factor] = []
        self._walk(source, payload, "", output)
        return output

    def _walk(self, source: str, value: Any, path: str, output: list[Factor]) -> None:
        if isinstance(value, bool):
            output.append(Factor(f"{source}:{path}", float(value), None, path)); return
        if isinstance(value, (int,float)):
            output.append(Factor(f"{source}:{path}", float(value), None, path)); return
        if isinstance(value, dict):
            for key, child in value.items(): self._walk(source, child, f"{path}.{key}".strip("."), output)
        elif isinstance(value, list):
            output.append(Factor(f"{source}:{path}.count", float(len(value)), "count", path))
            for index, child in enumerate(value[:100]): self._walk(source, child, f"{path}[{index}]", output)
