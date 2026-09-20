"""Orchestration facade for Module 15."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Any

from .lane_builder import DocumentBuilder
from .lane_export import DocumentExporter, ExportArtifact
from .lane_grounding import GroundingEngine
from .lane_models import Document, ExportFormat, GroundedDocument
from .lane_templates import TemplateRegistry


class DocumentGeneratorService:
    def __init__(self, *, grounding: GroundingEngine | None = None,
                 templates: TemplateRegistry | None = None,
                 exporter: DocumentExporter | None = None,
                 builder: DocumentBuilder | None = None) -> None:
        self.grounding = grounding or GroundingEngine()
        self.templates = templates or TemplateRegistry()
        self.exporter = exporter or DocumentExporter()
        self.builder = builder or DocumentBuilder()

    def build(self, payload: Mapping[str, Any]) -> Document:
        return self.builder.build(payload)

    def build_and_export(self, payload: Mapping[str, Any], format: ExportFormat | str) -> ExportArtifact:
        return self.export(self.build(payload), format)

    def ground(self, document: Document) -> GroundedDocument:
        return self.grounding.ground(document)

    def export(self, document: Document, format: ExportFormat | str) -> ExportArtifact:
        return self.exporter.export(self.ground(document), format)

    def export_to(self, document: Document, format: ExportFormat | str,
                  directory: str | Path, *, overwrite: bool = False) -> Path:
        artifact = self.export(document, format)
        return self.exporter.write(artifact, directory, overwrite=overwrite)

    def render_template(self, template_id: str, values: Mapping[str, Any]) -> str:
        return self.templates.render(template_id, values)
