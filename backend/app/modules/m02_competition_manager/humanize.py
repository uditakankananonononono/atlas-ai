"""Factual natural-voice pass for application answers before owner review."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Awaitable,Callable
import re
Generate=Callable[[str,str,str|None],Awaitable[tuple[str,str]]]
@dataclass(frozen=True)
class HumanizedAnswer:
 field:str;original:str;humanized:str;model:str;facts_preserved:bool;requires_user_review:bool=True;purpose:str='clarity_and_natural_voice'
class NaturalVoiceService:
 def __init__(self,generate:Generate):self.generate=generate
 async def humanize(self,field:str,answer:str,provider='openai',model=None):
  if not answer.strip():raise ValueError('answer is empty')
  prompt=("Rewrite this application answer in a clear, natural voice while preserving every factual claim, number, name, date, citation, and uncertainty marker. Do not add achievements, experiences, commitments, evidence, or facts. Do not optimize for AI-detector evasion or conceal authorship. Return only the revised answer.\nFIELD: "+field+"\nANSWER:\n"+answer)
  used,text=await self.generate(prompt,provider,model)
  text=text.strip()
  if not text:raise RuntimeError('natural-voice pass returned empty text')
  return HumanizedAnswer(field,answer,text,used,self._anchors(answer)<=self._anchors(text))
 @staticmethod
 def _anchors(text):
  return set(re.findall(r'\b(?:\d+(?:\.\d+)?%?|[A-Z][A-Za-z0-9_-]{2,}|\[[A-Z _-]+\])\b',text))
