"""Opt-in discovery binding: one live Service writer per tenant/local root.

No automatic provisioning. Root and writer ownership are supplied deployment
assumptions. Digest diffs cannot rehydrate removed display names after restart.
Persisted state authenticates no approval or collector permission.
"""
import asyncio
import time
from .service import Service
from .discovery_state_store import DiscoveryStateStore,StateError,fingerprint,MAX_QUERIES,MAX_SOURCES,MAX_CANDIDATES,KINDS

class DurableDiscoveryService(Service):
    def __init__(self,*args,discovery_store:DiscoveryStateStore,**kwargs):
        discovery_store.read() # refuse absent/corrupt before Service is exposed
        super().__init__(*args,**kwargs)
        self.discovery_store=discovery_store
        self._discovery_lock=asyncio.Lock()
        self._persistence_failed=False
        self._restore()

    def _restore(self):
        state=self.discovery_store.read()
        self._cooldown_until={};self.source_stats={}
        for collector in self.collectors:
            row=state['sources'].get(fingerprint(collector.name,'source'))
            if row:
                self._cooldown_until[collector.name]=row['cooldown_until']
                self.source_stats[collector.name]={k:v for k,v in row.items() if k!='cooldown_until'}
        return state

    async def _drain(self,collector,query,weights=None):
        found=[]
        async for raw in collector.collect(query):
            candidate=self._normalize(raw,collector.name,weights=weights)
            if candidate:
                found.append(candidate)
                if len(found)>MAX_CANDIDATES:raise StateError('candidate_capacity')
        return found

    async def discover(self,query,kinds=None,weights=None):
        async with self._discovery_lock:
            if self._persistence_failed:raise StateError('persistence_failed')
            try:
                state=self._restore()
                key=fingerprint(query,'query')
                if kinds is not None and (type(kinds) is not list or any(k not in KINDS for k in kinds)):
                    raise StateError('invalid_kind')
                if weights is not None:self._validate_weights(weights)
                if key not in state['queries'] and len(state['queries'])>=MAX_QUERIES:raise StateError('query_capacity')
                selected=[c for c in self.collectors if not kinds or getattr(c,'kind','tool') in kinds]
                names={fingerprint(c.name,'source') for c in selected}
                if len(names|set(state['sources']))>MAX_SOURCES:raise StateError('source_capacity')
                active=[c for c in selected if self._cooldown_until.get(c.name,0)<=time.time()]
                before={c.name:self.source_stats.get(c.name,{}).get('candidates',0) for c in active}
                ranked=await super().discover(query,kinds,weights)
                # Persist every attempted source before returning any candidates.
                for collector in active:
                    row=self.source_stats[collector.name]
                    self.discovery_store.record_source(collector.name,success=row['last_status']=='ok',
                        candidates=0 if row['last_status']=='error' else row['candidates']-before[collector.name],
                        latency_ms=row['last_latency_ms'],cooldown_until=self._cooldown_until.get(collector.name,0))
                diff=self.discovery_store.record_query(query,[self._key(x) for x in ranked],at=time.time(),kinds=kinds)
                self.last_diffs[query]={**diff,'identity_format':'sha256_candidate_key','display_names_restored':False}
                # Safe public error labels. Raw collector diagnostics stay out of durable state and return.
                self.last_errors={name:'source_unavailable_or_cooling' for name in self.last_errors}
                return ranked
            except StateError:
                self._persistence_failed=True
                self.candidates.clear()
                raise
