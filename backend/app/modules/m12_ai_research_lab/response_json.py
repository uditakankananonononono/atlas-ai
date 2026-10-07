"""JSON-safe diagnostic delivery, with every discarded value identified."""
from math import isfinite

def safe_workflow_json(value):
    invalid=[]
    active=set()
    def walk(item,path,depth=0):
        if item is None or type(item) in (str,bool,int):return item
        if type(item) is float:
            if isfinite(item):return item
            invalid.append(path);return None
        if depth>100 or type(item) not in (dict,list,tuple) or id(item) in active:
            invalid.append(path);return None
        active.add(id(item))
        try:
            if isinstance(item,dict):
                out={}
                for key,child in item.items():
                    if not isinstance(key,str):invalid.append(path+'.<nontext-key>');continue
                    out[key]=walk(child,path+'.'+key,depth+1)
                return out
            return [walk(child,path+f'[{i}]',depth+1) for i,child in enumerate(item)]
        finally:active.remove(id(item))
    return walk(value,'$'),invalid

def model_result_fields(result):
    """Shallow projection: diagnostic traversal owns cycles, not asdict."""
    return {key:getattr(result,key) for key in ("text","model_id","confidence","logprobs","usage","metadata")}
