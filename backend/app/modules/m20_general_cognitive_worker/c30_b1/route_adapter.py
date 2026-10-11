"""Stdlib transport adapter; host must supply an authenticated tenant identifier.

Not mounted on the Atlas server by this additive unit. No anonymous access or
raw-ledger endpoint is exposed. Tenant state is caller-owned, not process-global.
"""
if __package__:
    from .chat_bind import ChatBinder, Refused
else:
    from chat_bind import ChatBinder, Refused

class Routes:
    def __init__(self, tenant_store):
        self.store = tenant_store

    def dispatch(self, method, path, tenant_id, payload=None):
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise Refused('PLAN_REFUSED_TENANT')
        if (method,path)==('POST','/api/v1/c30/chat-bind/run'):
            self.store[tenant_id] = ChatBinder(payload)
            return self.store[tenant_id].report()
        if (method,path)==('GET','/api/v1/c30/chat-bind/report'):
            if tenant_id not in self.store:
                raise Refused('PLAN_REFUSED_NOTRUN')
            return self.store[tenant_id].report()
        raise Refused('PLAN_REFUSED_ROUTE')
