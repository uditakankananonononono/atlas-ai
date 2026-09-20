"""Read-only official Google Docs and Sheets grounding adapter."""
from __future__ import annotations
from dataclasses import dataclass
import os
from typing import Any
import httpx

@dataclass(frozen=True)
class GroundedSource:
    source_type:str;source_id:str;locator:str;text:str;provenance:dict[str,Any]

class GoogleWorkspaceGrounder:
    def __init__(self,access_token:str|None=None,client:httpx.AsyncClient|None=None):
        self.token=access_token or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
        self.client=client or httpx.AsyncClient(timeout=60)
        self.owns=client is None
    def _headers(self):
        if not self.token:raise RuntimeError("GOOGLE_OAUTH_ACCESS_TOKEN is not configured")
        return {"Authorization":f"Bearer {self.token}"}
    async def close(self):
        if self.owns:await self.client.aclose()
    async def document(self,document_id:str)->GroundedSource:
        r=await self.client.get(f"https://docs.googleapis.com/v1/documents/{document_id}",headers=self._headers())
        r.raise_for_status();data=r.json();parts=[]
        def walk(node):
            if isinstance(node,dict):
                if "textRun" in node:parts.append(node["textRun"].get("content", ""))
                for value in node.values():walk(value)
            elif isinstance(node,list):
                for value in node:walk(value)
        walk(data.get("body",{}))
        return GroundedSource("google_doc",document_id,f"docs/{document_id}","".join(parts).strip(),{"revision_id":data.get("revisionId"),"title":data.get("title"),"api":"Google Docs v1"})
    async def sheet(self,spreadsheet_id:str,ranges:list[str])->list[GroundedSource]:
        if not ranges:raise ValueError("at least one A1 range is required")
        r=await self.client.get(f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet",headers=self._headers(),params=[("ranges",x) for x in ranges])
        r.raise_for_status();out=[]
        for block in r.json().get("valueRanges",[]):
            values=block.get("values",[]);text="\n".join("\t".join(map(str,row)) for row in values)
            out.append(GroundedSource("google_sheet",spreadsheet_id,block.get("range",""),text,{"major_dimension":block.get("majorDimension"),"api":"Google Sheets v4"}))
        return out
