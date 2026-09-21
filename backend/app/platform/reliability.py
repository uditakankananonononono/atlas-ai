from __future__ import annotations
import asyncio,time
from collections import defaultdict,deque
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable,Callable,TypeVar
T=TypeVar("T")

class RateLimitExceeded(RuntimeError): pass
class CircuitOpen(RuntimeError): pass

class TenantRateLimiter:
    def __init__(self,limit:int,window_seconds:float=60):
        if limit<1 or window_seconds<=0: raise ValueError("positive limit and window required")
        self.limit,self.window=limit,window_seconds; self._hits:dict[tuple[str,str],deque[float]]=defaultdict(deque)
    def check(self,tenant:str,actor:str,now:float|None=None)->None:
        if not tenant or not actor: raise ValueError("tenant and actor are required")
        now=time.monotonic() if now is None else now; q=self._hits[(tenant,actor)]
        while q and q[0] <= now-self.window: q.popleft()
        if len(q)>=self.limit: raise RateLimitExceeded("tenant actor rate limit exceeded")
        q.append(now)

class State(str,Enum): CLOSED="closed"; OPEN="open"; HALF_OPEN="half_open"
@dataclass
class CircuitBreaker:
    failure_threshold:int=3; recovery_seconds:float=30; clock:Callable[[],float]=time.monotonic
    def __post_init__(self): self.failures=0; self.opened_at:float|None=None
    @property
    def state(self)->State:
        if self.opened_at is None:return State.CLOSED
        return State.HALF_OPEN if self.clock()-self.opened_at>=self.recovery_seconds else State.OPEN
    async def call(self,operation:Callable[[],Awaitable[T]],timeout_seconds:float,retries:int=0)->T:
        if self.state==State.OPEN: raise CircuitOpen("dependency circuit is open")
        last:Exception|None=None
        for attempt in range(retries+1):
            try:
                value=await asyncio.wait_for(operation(),timeout_seconds); self.failures=0; self.opened_at=None; return value
            except Exception as exc:
                last=exc; self.failures+=1
                if self.failures>=self.failure_threshold: self.opened_at=self.clock(); break
                if attempt<retries: await asyncio.sleep(min(.05*(2**attempt),.5))
        assert last is not None; raise last

class IdempotencyConflict(RuntimeError): pass
class IdempotencyStore:
    def __init__(self): self._values:dict[tuple[str,str],tuple[str,object]]={}
    def execute(self,tenant:str,key:str,fingerprint:str,operation:Callable[[],T])->tuple[T,bool]:
        if not tenant or not key or not fingerprint: raise ValueError("tenant, key and fingerprint are required")
        existing=self._values.get((tenant,key))
        if existing:
            old,value=existing
            if old!=fingerprint: raise IdempotencyConflict("key reused with a different request")
            return value,True
        value=operation(); self._values[(tenant,key)]=(fingerprint,value); return value,False
