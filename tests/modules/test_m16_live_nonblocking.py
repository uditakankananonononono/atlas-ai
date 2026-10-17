import asyncio,threading,time
from types import SimpleNamespace
from app.modules.m16_executive_dashboard import routes

class _Req:
    headers={}
    def __init__(self,stop):self.stop=stop
    async def is_disconnected(self):return self.stop.is_set()

class _SlowService:
    """events_after blocks the calling thread like a synchronous DB read."""
    def __init__(self):self.threads=[]
    def events_after(self,cursor):
        self.threads.append(threading.get_ident());time.sleep(0.3);return []

def test_live_db_read_does_not_block_event_loop(monkeypatch):
    real_sleep=asyncio.sleep
    async def fast_sleep(_):await real_sleep(0)
    monkeypatch.setattr(routes.asyncio,"sleep",fast_sleep)
    async def run():
        stop=asyncio.Event();svc=_SlowService()
        stop_t=threading.Event()
        resp=await routes.live(_Req(stop_t),0,svc)
        gaps=[];last=time.monotonic()
        async def ticker():
            nonlocal last
            while not stop.is_set():
                await real_sleep(0.01);now=time.monotonic();gaps.append(now-last);last=now
        async def consume():
            n=0
            async for _ in resp.body_iterator:
                n+=1
                if n>=3:stop_t.set()
        t=asyncio.create_task(ticker());await consume();stop.set();await t
        return gaps,svc.threads
    gaps,threads=asyncio.run(run())
    assert max(gaps)<0.2,max(gaps)          # a 0.3s blocking read on the loop would show as ~0.3s
    assert threading.get_ident() not in threads
