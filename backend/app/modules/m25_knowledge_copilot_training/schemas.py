from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

SourceKind = Literal['website','podcast','book','forum','meeting_audio','file']
class ConsentRecord(BaseModel):
    granted_by: str = Field(min_length=1)
    granted_at: datetime
    purposes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None
    evidence: str = Field(min_length=1)
class SourceRegistration(BaseModel):
    source_id: str = Field(min_length=1, pattern=r'^[A-Za-z0-9_.-]+$')
    kind: SourceKind
    canonical_url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    title: str = Field(min_length=1)
    consent: ConsentRecord
    metadata: dict[str, Any] = Field(default_factory=dict)
    @model_validator(mode='after')
    def validate_provenance(self):
        if self.kind in {'website','podcast','forum'} and not self.canonical_url:
            raise ValueError('canonical_url is required for network sources')
        if self.kind == 'podcast' and not {'episode_title','episode_id','duration_seconds'} <= self.metadata.keys():
            raise ValueError('podcast episode metadata is required')
        if self.kind == 'book' and not ({'isbn','edition'} <= self.metadata.keys()):
            raise ValueError('book ISBN and edition are required')
        if self.kind == 'forum' and 'thread_id' not in self.metadata:
            raise ValueError('forum thread structure is required')
        return self
class IngestRequest(BaseModel):
    source: SourceRegistration
    content: str | bytes
    mime_type: str
    actor_id: str = Field(min_length=1)
class Anchor(BaseModel):
    anchor_id: str
    kind: Literal['page','paragraph','timestamp','post','section']
    value: str
class Segment(BaseModel):
    text: str
    anchors: list[Anchor]
    speaker: str | None = None
    speaker_confidence: float | None = Field(None,ge=0,le=1)
    start_seconds: float | None = Field(None,ge=0)
    end_seconds: float | None = Field(None,ge=0)
class Citation(BaseModel):
    source_id: str; version: int; anchor_ids: list[str] = Field(min_length=1); quote_hash: str
class Claim(BaseModel):
    text: str = Field(min_length=1); citations: list[Citation] = Field(default_factory=list)
class SearchRequest(BaseModel):
    query: str = Field(min_length=1); limit: int = Field(10,ge=1,le=100)
