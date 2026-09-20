"""Safe, strict document templates without code execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from string import Formatter
from typing import Any, Mapping

from .lane_models import TemplateError


@dataclass(frozen=True, slots=True)
class DocumentTemplate:
    id: str
    name: str
    body: str
    required_fields: frozenset[str] = frozenset()
    defaults: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip() or not self.body.strip():
            raise TemplateError("template id, name, and body are required")
        referenced = self.fields()
        invalid = [key for key in referenced if "." in key or "[" in key or "]" in key]
        if invalid:
            raise TemplateError("attribute and item access are not allowed in templates")
        undeclared = self.required_fields - referenced
        if undeclared:
            raise TemplateError(f"required fields are not referenced: {sorted(undeclared)}")

    def fields(self) -> frozenset[str]:
        fields: set[str] = set()
        try:
            for _, name, _, _ in Formatter().parse(self.body):
                if name is not None:
                    fields.add(name)
        except ValueError as exc:
            raise TemplateError(f"invalid template syntax: {exc}") from exc
        return frozenset(fields)

    def render(self, values: Mapping[str, Any]) -> str:
        unknown = set(values) - self.fields()
        if unknown:
            raise TemplateError(f"unknown template fields: {sorted(unknown)}")
        merged = {**self.defaults, **values}
        missing = self.fields() - merged.keys()
        if missing:
            raise TemplateError(f"missing template fields: {sorted(missing)}")
        empty_required = [name for name in self.required_fields if not str(merged[name]).strip()]
        if empty_required:
            raise TemplateError(f"required template fields are empty: {sorted(empty_required)}")
        try:
            return self.body.format_map(merged)
        except (KeyError, ValueError) as exc:
            raise TemplateError(f"could not render template: {exc}") from exc


class TemplateRegistry:
    def __init__(self, templates: tuple[DocumentTemplate, ...] = ()) -> None:
        self._templates: dict[str, DocumentTemplate] = {}
        for template in templates:
            self.register(template)

    def register(self, template: DocumentTemplate, *, replace: bool = False) -> None:
        if template.id in self._templates and not replace:
            raise TemplateError(f"template {template.id!r} is already registered")
        self._templates[template.id] = template

    def get(self, template_id: str) -> DocumentTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise TemplateError(f"unknown template {template_id!r}") from exc

    def render(self, template_id: str, values: Mapping[str, Any]) -> str:
        return self.get(template_id).render(values)

    def list(self) -> tuple[DocumentTemplate, ...]:
        return tuple(sorted(self._templates.values(), key=lambda item: item.name.casefold()))
