from pydantic import BaseModel,Field
class NavigateIn(BaseModel):session_id:str=Field(min_length=1);url:str;persistent:bool=False
class FillIn(BaseModel):session_id:str;fields:list[dict];data:dict[str,str]
class SubmitIn(BaseModel):session_id:str;selector:str;values:dict[str,str]
class SubmitExecuteIn(SubmitIn):approval_id:str
