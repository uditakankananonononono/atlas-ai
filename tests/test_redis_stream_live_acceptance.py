"""Real Redis stream acceptance. Never flush a shared Redis database."""
import json
import os
import subprocess
import sys
import uuid

import pytest
from redis import Redis


def test_stream_bus_cross_process_cursor_replay_and_stream_isolation():
    url=os.getenv('ATLAS_ACCEPTANCE_REDIS_URL') or os.getenv('ATLAS_REDIS_URL')
    if not url:
        pytest.skip('real Redis acceptance needs ATLAS_ACCEPTANCE_REDIS_URL or ATLAS_REDIS_URL')
    client=Redis.from_url(url,decode_responses=True,socket_connect_timeout=3,socket_timeout=3)
    client.ping()  # A configured but unavailable server must fail, not silently skip.
    stream=f'atlas:acceptance:{uuid.uuid4()}'
    other=f'{stream}:other'
    code='''
import json,sys
from app.platform.integrations import RedisStreamBus
url,stream,other,mode=sys.argv[1:]
bus=RedisStreamBus(url)
if mode=='write':
 first=bus.publish(stream,{'type':'created','id':1})
 second=bus.publish(stream,{'type':'created','id':2})
 bus.publish(other,{'type':'private-other-stream','id':3})
 print(json.dumps([first,second]))
else:
 print(json.dumps(bus.read(stream,last_id=mode,count=10,block_ms=10)))
'''
    def run(mode):
        result=subprocess.run([sys.executable,'-c',code,url,stream,other,mode],
                              capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stderr
        return json.loads(result.stdout)
    try:
        first,second=run('write')
        assert first != second
        assert run('0-0')==[{'id':first,'event':{'type':'created','id':1}},
                           {'id':second,'event':{'type':'created','id':2}}]
        assert run(first)==[{'id':second,'event':{'type':'created','id':2}}]
        assert run(second)==[]
        assert client.xlen(other)==1
    finally:
        client.delete(stream,other)
