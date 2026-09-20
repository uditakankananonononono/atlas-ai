from __future__ import annotations
from dataclasses import dataclass
import re
@dataclass(frozen=True)
class FieldDescriptor:
    selector:str; label:str=""; name:str=""; placeholder:str=""; input_type:str="text"; required:bool=False
_TOKEN=re.compile(r"[a-z0-9]+")
def _tokens(s:str)->set[str]: return set(_TOKEN.findall(s.lower()))
def match_fields(fields:list[FieldDescriptor],data:dict[str,str],threshold:float=.38)->dict[str,str]:
    result={}
    for field in fields:
        hay=_tokens(" ".join((field.label,field.name,field.placeholder)))
        scored=[]
        for key,val in data.items():
            key_tokens=_tokens(key); score=len(hay&key_tokens)/max(1,len(hay|key_tokens))
            if field.input_type=="email" and "email" in key_tokens: score+=.6
            if field.input_type=="tel" and ({"phone","mobile","telephone"}&key_tokens): score+=.6
            scored.append((score,key,val))
        if scored:
            score,_,val=max(scored)
            if score>=threshold: result[field.selector]=val
    return result
