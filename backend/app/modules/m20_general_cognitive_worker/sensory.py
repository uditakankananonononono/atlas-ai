"""Sensory layer (spec 4.2.1): multimodal ingestion -> cognitive events.

Accepts tasks and inputs as natural language, voice, images, CSV, PDFs and
emails, and normalises everything into CognitiveEvent objects. Modalities
that need a model (audio transcription, image description, PDF parsing) are
handled behind injected protocols so the layer itself never does I/O or
network work; the integrator binds Whisper/GPT-4o/CogVLM implementations.
"""
from __future__ import annotations

import csv
import hashlib
import io
from typing import Any, Protocol, runtime_checkable

from .schemas import CognitiveEvent, Modality


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@runtime_checkable
class Transcriber(Protocol):
    """Audio -> text (Whisper in production)."""

    def transcribe(self, audio_bytes: bytes, *, media_type: str = "") -> str: ...


@runtime_checkable
class VisionModel(Protocol):
    """Image -> detailed textual description (GPT-4o/CogVLM in production)."""

    def describe(self, image_bytes: bytes, *, media_type: str = "") -> str: ...


@runtime_checkable
class DocumentParser(Protocol):
    """PDF bytes -> extracted text."""

    def parse(self, pdf_bytes: bytes) -> str: ...


class SensoryLayer:
    """Normalises every supported modality into a CognitiveEvent stream.

    Dedupes on external_id first, then content hash, so re-delivered inputs
    do not double-enter working memory.
    """

    def __init__(
        self,
        *,
        allowed_sources: set[str] | None = None,
        transcriber: Transcriber | None = None,
        vision: VisionModel | None = None,
        document_parser: DocumentParser | None = None,
        max_rows_preview: int = 50,
    ) -> None:
        self.allowed_sources = allowed_sources
        self.transcriber = transcriber
        self.vision = vision
        self.document_parser = document_parser
        self.max_rows_preview = max_rows_preview
        self._seen_external_ids: set[str] = set()
        self._seen_hashes: set[str] = set()

    def _accept(self, event: CognitiveEvent) -> CognitiveEvent | None:
        if self.allowed_sources is not None and event.source not in self.allowed_sources:
            return None
        if event.external_id and event.external_id in self._seen_external_ids:
            return None
        if event.content_hash and event.content_hash in self._seen_hashes:
            return None
        if event.external_id:
            self._seen_external_ids.add(event.external_id)
        if event.content_hash:
            self._seen_hashes.add(event.content_hash)
        return event

    def ingest_text(
        self, text: str, *, source: str, external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        event = CognitiveEvent(
            modality=Modality.TEXT, text=text, source=source,
            external_id=external_id, content_hash=content_hash(text),
            metadata=metadata or {},
        )
        return self._accept(event)

    def ingest_audio(
        self, audio_bytes: bytes, *, source: str, media_type: str = "",
        external_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        if self.transcriber is None:
            raise RuntimeError("no transcriber bound for audio ingestion")
        text = self.transcriber.transcribe(audio_bytes, media_type=media_type)
        event = CognitiveEvent(
            modality=Modality.AUDIO, text=text, source=source,
            external_id=external_id, content_hash=content_hash(text),
            metadata={**(metadata or {}), "media_type": media_type},
        )
        return self._accept(event)

    def ingest_image(
        self, image_bytes: bytes, *, source: str, media_type: str = "",
        external_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        if self.vision is None:
            raise RuntimeError("no vision model bound for image ingestion")
        description = self.vision.describe(image_bytes, media_type=media_type)
        event = CognitiveEvent(
            modality=Modality.IMAGE, text=description, source=source,
            external_id=external_id, content_hash=content_hash(description),
            metadata={**(metadata or {}), "media_type": media_type},
        )
        return self._accept(event)

    def ingest_csv(
        self, csv_text: str, *, source: str, external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        if not rows:
            return None
        header, body = rows[0], rows[1:]
        preview = body[: self.max_rows_preview]
        lines = [", ".join(header)]
        lines.extend(", ".join(row) for row in preview)
        text = (
            f"CSV with {len(body)} data rows and columns [{', '.join(header)}].\n"
            + "\n".join(lines)
        )
        event = CognitiveEvent(
            modality=Modality.CSV, text=text, source=source,
            external_id=external_id, content_hash=content_hash(csv_text),
            metadata={
                **(metadata or {}),
                "columns": header,
                "row_count": len(body),
                "truncated": len(body) > self.max_rows_preview,
            },
        )
        return self._accept(event)

    def ingest_pdf(
        self, pdf_bytes: bytes, *, source: str, external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        if self.document_parser is None:
            raise RuntimeError("no document parser bound for PDF ingestion")
        text = self.document_parser.parse(pdf_bytes)
        event = CognitiveEvent(
            modality=Modality.PDF, text=text, source=source,
            external_id=external_id, content_hash=content_hash(text),
            metadata=metadata or {},
        )
        return self._accept(event)

    def ingest_email(
        self, *, subject: str, body: str, sender: str, source: str = "email",
        external_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> CognitiveEvent | None:
        text = f"From: {sender}\nSubject: {subject}\n\n{body}"
        event = CognitiveEvent(
            modality=Modality.EMAIL, text=text, source=source,
            external_id=external_id, content_hash=content_hash(text),
            metadata={**(metadata or {}), "sender": sender, "subject": subject},
        )
        return self._accept(event)
