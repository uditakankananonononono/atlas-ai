"""Chunk A tests: schemas, embeddings, sensory layer."""
from datetime import datetime, timezone

import pytest

from app.modules.m20_general_cognitive_worker.embeddings import (
    DeterministicEmbedding, cosine_similarity, tokenize,
)
from app.modules.m20_general_cognitive_worker.schemas import (
    ApprovalGateRequest, ChunkType, CognitiveEvent, Episode, EpisodeOutcome,
    MemoryChunk, Modality, Risk, TaskContext, TaskState,
)
from app.modules.m20_general_cognitive_worker.sensory import SensoryLayer


class FakeTranscriber:
    def transcribe(self, audio_bytes, *, media_type=""):
        return "transcribed words"


class FakeVision:
    def describe(self, image_bytes, *, media_type=""):
        return "a chart showing revenue growth"


class FakeParser:
    def parse(self, pdf_bytes):
        return "extracted pdf text"


def test_schema_defaults_and_enums():
    chunk = MemoryChunk(type=ChunkType.GOAL, content="finish the report")
    assert chunk.confidence == 1.0 and chunk.salience == 0.5
    event = CognitiveEvent(modality=Modality.TEXT, text="hi", source="test")
    assert event.confidence == 1.0
    assert isinstance(event.observed_at, datetime)
    ctx = TaskContext(goal="ship it", importance=4)
    assert ctx.state == TaskState.PENDING
    req = ApprovalGateRequest(action_type="send_email", summary="send", risk=Risk.EXTERNAL)
    assert req.module_id == 20
    ep = Episode(task_id="t1", goal="g", outcome=EpisodeOutcome.FAILED)
    assert ep.outcome.value == "failed"


def test_deterministic_embedding_is_stable_and_normalized():
    emb = DeterministicEmbedding(64)
    a = emb.embed("grant proposal for climate research")
    b = emb.embed("grant proposal for climate research")
    c = emb.embed("unrelated pizza recipe")
    assert a == b
    assert abs(sum(v * v for v in a) - 1.0) < 1e-6
    assert cosine_similarity(a, b) > 0.99
    assert cosine_similarity(a, c) < 0.6
    assert cosine_similarity([], a) == 0.0
    with pytest.raises(ValueError):
        DeterministicEmbedding(2)


def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello, World-2026!") == ["hello", "world", "2026"]


def test_text_ingestion_and_dedupe():
    layer = SensoryLayer()
    e1 = layer.ingest_text("hello", source="chat", external_id="m1")
    assert e1 is not None and e1.modality == Modality.TEXT
    assert layer.ingest_text("hello", source="chat", external_id="m1") is None
    assert layer.ingest_text("hello", source="chat", external_id="m2") is None  # same hash


def test_source_allowlist():
    layer = SensoryLayer(allowed_sources={"api"})
    assert layer.ingest_text("x", source="api") is not None
    assert layer.ingest_text("y", source="rogue") is None


def test_audio_requires_transcriber_and_uses_it():
    layer = SensoryLayer()
    with pytest.raises(RuntimeError):
        layer.ingest_audio(b"\x00", source="voice")
    layer = SensoryLayer(transcriber=FakeTranscriber())
    event = layer.ingest_audio(b"\x00", source="voice", media_type="audio/ogg")
    assert event.text == "transcribed words"
    assert event.modality == Modality.AUDIO


def test_image_and_pdf_paths():
    layer = SensoryLayer(vision=FakeVision(), document_parser=FakeParser())
    img = layer.ingest_image(b"\xff\xd8", source="upload")
    assert "revenue growth" in img.text
    pdf = layer.ingest_pdf(b"%PDF-1.4", source="upload")
    assert pdf.text == "extracted pdf text"
    bare = SensoryLayer()
    with pytest.raises(RuntimeError):
        bare.ingest_image(b"\xff", source="upload")
    with pytest.raises(RuntimeError):
        bare.ingest_pdf(b"%PDF", source="upload")


def test_csv_normalization_preview_and_metadata():
    rows = ["name,score"] + [f"row{i},{i}" for i in range(60)]
    layer = SensoryLayer(max_rows_preview=10)
    event = layer.ingest_csv("\n".join(rows), source="upload")
    assert event.metadata["columns"] == ["name", "score"]
    assert event.metadata["row_count"] == 60
    assert event.metadata["truncated"] is True
    assert "60 data rows" in event.text
    assert layer.ingest_csv("", source="upload") is None


def test_email_normalization():
    layer = SensoryLayer()
    event = layer.ingest_email(subject="Hi", body="Body text", sender="a@b.c")
    assert event.modality == Modality.EMAIL
    assert "a@b.c" in event.text and "Hi" in event.text
