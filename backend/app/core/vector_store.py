"""Provider-neutral pgvector storage. Embedding generation is configured separately."""
from typing import Any
from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.core.database import Base

EMBEDDING_DIMENSIONS = 1024

class MemoryEmbeddingRow(Base):
    __tablename__ = "memory_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    namespace: Mapped[str] = mapped_column(String(120), index=True)
    text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
