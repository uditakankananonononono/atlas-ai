"""Typed, tenant-scoped contracts for the Module 17 narrative architect."""
from __future__ import annotations
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, model_validator

class ProvenanceKind(str, Enum):
    ARTICLE="article"; TRANSCRIPT="transcript"; USER_MATERIAL="user_material"

class CollectIn(BaseModel):
    query:str=Field(min_length=3,max_length=500)
    platforms:list[str]=Field(default_factory=lambda:["reddit","youtube","pinterest","public_web"])
    limit_per_platform:int=Field(default=20,ge=1,le=100)
    owner_id:str|None=None

class TranscriptSpan(BaseModel):
    start_seconds:float|None=Field(default=None,ge=0)
    end_seconds:float|None=Field(default=None,ge=0)
    text:str=Field(min_length=1,max_length=6000)
    @model_validator(mode="after")
    def ordered(self):
        if self.start_seconds is not None and self.end_seconds is not None and self.end_seconds < self.start_seconds: raise ValueError("transcript end precedes start")
        return self

class SourceOut(BaseModel):
    url:HttpUrl
    platform:str
    content_hash:str
    rights:str="link_and_excerpt_only"
    injection_flags:list[str]=Field(default_factory=list)
    creator:str|None=None
    published_at:str|None=None
    provenance_kind:ProvenanceKind=ProvenanceKind.ARTICLE
    transcript_spans:list[TranscriptSpan]=Field(default_factory=list)
    credibility_score:float=Field(ge=0,le=1)
    credibility_reasons:list[str]=Field(default_factory=list)

class AdviceOut(BaseModel):
    source:SourceOut
    excerpt:str
    topic:str
    actionable_tips:list[str]
    confidence:float=Field(ge=0,le=1)
    citation:str
    cluster_id:str

class IdentityIn(BaseModel):
    traits:list[str]=Field(default_factory=list,max_length=50)
    pivotal_experiences:list[str]=Field(default_factory=list,max_length=50)
    values:list[str]=Field(default_factory=list,max_length=50)
    voice_samples:list[str]=Field(default_factory=list,max_length=30)
    forbidden_topics:list[str]=Field(default_factory=list,max_length=50)

class ConceptIn(BaseModel):
    prompt:str=Field(min_length=3,max_length=4000)
    profile:IdentityIn
    count:int=Field(default=7,ge=5,le=10)
    owner_id:str|None=None

class LiteraryDevice(BaseModel):
    device:str
    placement:str
    purpose:str
    caution:str="Use only if it sounds natural in the student's own voice."

class ConceptOut(BaseModel):
    title:str
    core_tension:str
    metaphor:str
    outline:list[str]=Field(min_length=3)
    opening:str
    evidence_urls:list[HttpUrl]=Field(default_factory=list)
    privacy_flags:list[str]=Field(default_factory=list)
    source_material_refs:list[str]=Field(default_factory=list)
    literary_devices:list[LiteraryDevice]=Field(default_factory=list)
    student_work_questions:list[str]=Field(default_factory=list)
    authorship_notice:str="Planning scaffold only. The student must write and verify the final prose."

class CritiqueIn(BaseModel):
    draft:str=Field(min_length=50,max_length=30000)
    target_prompt:str
    preserve_voice:bool=True
    voice_samples:list[str]=Field(default_factory=list,max_length=30)
    owner_id:str|None=None

class SuggestionOut(BaseModel):
    start:int=Field(ge=0)
    end:int=Field(ge=0)
    replacement:str|None=None
    reason:str
    category:str
    severity:str="suggestion"
    original:str|None=None
    model_votes:list[str]=Field(default_factory=list)
    @model_validator(mode="after")
    def valid_span(self):
        if self.end < self.start: raise ValueError("suggestion end precedes start")
        return self

class VoiceMetrics(BaseModel):
    sentence_length_similarity:float=Field(ge=0,le=1)
    vocabulary_similarity:float=Field(ge=0,le=1)
    punctuation_similarity:float=Field(ge=0,le=1)
    overall_similarity:float=Field(ge=0,le=1)
    sample_word_count:int=Field(ge=0)
    uncertainty:str

class CritiqueOut(BaseModel):
    narrative:list[SuggestionOut]=Field(default_factory=list)
    grammar:list[SuggestionOut]=Field(default_factory=list)
    admissions:list[SuggestionOut]=Field(default_factory=list)
    cliches:list[SuggestionOut]=Field(default_factory=list)
    techniques:list[SuggestionOut]=Field(default_factory=list)
    voice_drift_score:float=Field(ge=0,le=1)
    voice_metrics:VoiceMetrics
    model_agreement:float=Field(ge=0,le=1)
    critique_models:list[str]=Field(default_factory=list)
    authorship_notice:str="Suggestions are diffs, not replacement prose. The student owns the final wording and submission."
