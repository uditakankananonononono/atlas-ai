from __future__ import annotations
import contextvars,json,logging,uuid
trace_id_var=contextvars.ContextVar("trace_id",default="")
class CloudJsonFormatter(logging.Formatter):
    def format(self,record:logging.LogRecord)->str:
        return json.dumps({"severity":record.levelname,"message":record.getMessage(),"logger":record.name,"trace_id":trace_id_var.get(),"service":"atlas-api"},separators=(",",":"))
def bind_trace(incoming:str|None=None)->str:
    trace=(incoming or "").strip() or uuid.uuid4().hex
    trace_id_var.set(trace[:128]); return trace_id_var.get()
def inject_trace(headers:dict[str,str])->dict[str,str]:
    result=dict(headers); result["traceparent"]=trace_id_var.get(); return result
