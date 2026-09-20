"""Typed document/version contracts for LaTeX, DOCX and PPTX generation."""
from typing import Any,Literal
from pydantic import BaseModel,Field,model_validator
Format=Literal["latex","docx","pptx","pdf"]
class Citation(BaseModel): key:str;title:str;url:str|None=None;authors:list[str]=[];accessed_at:str|None=None;quote:str|None=None
class FigureSpec(BaseModel):
    id:str;engine:Literal["plotly","matplotlib"];kind:Literal["line","bar","scatter","pie"];data:dict[str,Any];options:dict[str,Any]={};alt_text:str=Field(min_length=3,max_length=2000)
class CreateVersionRequest(BaseModel):
    title:str=Field(min_length=1,max_length=500);format:Format;template_id:str=Field(min_length=1,max_length=200)
    content:dict[str,Any];parent_version_id:str|None=None;citations:list[Citation]=Field(default_factory=list,max_length=1000);figures:list[FigureSpec]=Field(default_factory=list,max_length=100)
    @model_validator(mode="after")
    def accessible(self):
        if self.format=="pptx" and any(not slide.get("title") for slide in self.content.get("slides",[])):raise ValueError("every slide requires a title")
        return self
class DocumentVersion(BaseModel):
    id:str;tenant_id:str;document_id:str;version_number:int;format:Format;template_id:str;content:dict[str,Any]
    parent_version_id:str|None=None;content_hash:str;status:str="draft";output_uri:str|None=None;citations:list[Citation]=[];figures:list[FigureSpec]=[]
class DiffEntry(BaseModel):path:str;operation:Literal["add","remove","replace"];before:Any=None;after:Any=None
class DiffResponse(BaseModel):from_version_id:str;to_version_id:str;changes:list[DiffEntry]
class ExportProposal(BaseModel):approval_id:str;version_id:str;status:str;action_type:Literal["render_document"]="render_document"
