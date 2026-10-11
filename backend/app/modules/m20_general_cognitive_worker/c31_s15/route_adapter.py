"""Unregistered stdlib transport adapter; host must authenticate tenant first."""
if __package__:
    from .lenses import run,Refused
else:
    from lenses import run,Refused

class Routes:
    def __init__(self,store,guard):
        self.store=store
        self.guard=guard
    def dispatch(self,method,path,tenant_id,payload=None,*,as_of):
        if not isinstance(tenant_id,str) or not tenant_id.strip():
            raise Refused('FLEET_REFUSED_TENANT')
        if (method,path)==('POST','/api/v1/c31/lenses/run'):
            report=run(payload,as_of=as_of,guard=self.guard)
            self.store[tenant_id]=report
            return report
        if (method,path)==('GET','/api/v1/c31/lenses/report'):
            self.guard('read')
            if tenant_id not in self.store:
                raise Refused('FLEET_REFUSED_NOTRUN')
            return self.store[tenant_id]
        raise Refused('FLEET_REFUSED_ROUTE')
