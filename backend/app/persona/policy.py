"""Behavior contract shared by Atlas modules that speak or act for a user."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

class AssistantPersona(BaseModel):
    name: str = "Atlas"
    voice: str = "direct, warm, plain-spoken"
    humor: str = "dry and light only when stakes are low; never during safety, money, loss, or distress"
    truthfulness: tuple[str, ...]
    approval_etiquette: tuple[str, ...]
    reasoning_transparency: tuple[str, ...]
    forbidden: tuple[str, ...]

class BehaviorCheck(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    disclosure: str | None = None

@dataclass(frozen=True)
class PersonaPolicy:
    persona: AssistantPersona

    def check(self, *, proposed_text: str = "", external_effect: bool = False,
              irreversible: bool = False, money: bool = False,
              evidence: list[dict[str, Any]] | None = None,
              limitations: list[str] | None = None) -> BehaviorCheck:
        text=proposed_text.lower(); reasons=[]
        deception_markers=("pretend i", "lie to", "make up experience", "fabricate", "false claim")
        if any(marker in text for marker in deception_markers):
            return BehaviorCheck(allowed=False,reasons=["deception or fabrication requested"])
        if (external_effect or irreversible or money) and not proposed_text.strip():
            return BehaviorCheck(allowed=False,reasons=["approval preview needs exact proposed content"],requires_approval=True)
        needs=external_effect or irreversible or money
        if needs: reasons.append("human review required before external effect")
        disclosure=None
        gaps=list(limitations or [])
        if not evidence: gaps.append("no supporting evidence attached")
        if gaps: disclosure="Limits: " + "; ".join(dict.fromkeys(gaps))
        return BehaviorCheck(allowed=True,reasons=reasons,requires_approval=needs,disclosure=disclosure)

    def system_instruction(self) -> str:
        p=self.persona
        return "\n".join([
            f"You are {p.name}. Voice: {p.voice}. Humor: {p.humor}.",
            "Truthfulness: " + " ".join(p.truthfulness),
            "Approval etiquette: " + " ".join(p.approval_etiquette),
            "Reasoning transparency: " + " ".join(p.reasoning_transparency),
            "Never: " + " ".join(p.forbidden),
        ])

def default_persona(path: str | Path = "config/assistant_persona.json") -> PersonaPolicy:
    return PersonaPolicy(AssistantPersona.model_validate(json.loads(Path(path).read_text())))
