"""Real worker transport acceptance using Atlas config and a test-only task."""
import os
import subprocess
import sys
import uuid

import pytest
from celery import Celery
from redis import Redis


def test_atlas_celery_worker_executes_json_task_and_stores_redis_result(tmp_path):
    url=os.getenv('ATLAS_ACCEPTANCE_REDIS_URL') or os.getenv('ATLAS_REDIS_URL')
    if not url:
        pytest.skip('real Celery acceptance needs a configured Redis URL')
    Redis.from_url(url,socket_connect_timeout=3,socket_timeout=3).ping()
    queue=f'atlas-acceptance-{uuid.uuid4()}'
    taskname=f'atlas.acceptance.{uuid.uuid4()}'
    code='''
import os
from app.workers.celery_app import celery_app
celery_app.conf.include=[]
@celery_app.task(name=os.environ['ACCEPTANCE_TASK'])
def echo(payload):
 return {'transport':'real-worker','payload':payload}
celery_app.worker_main(['worker','--pool=solo','--concurrency=1','--without-gossip',
 '--without-mingle','--without-heartbeat','--loglevel=WARNING','-Q',os.environ['ACCEPTANCE_QUEUE']])
'''
    env={**os.environ,'ATLAS_REDIS_URL':url,'ACCEPTANCE_TASK':taskname,'ACCEPTANCE_QUEUE':queue}
    log=tmp_path/'worker.log'
    with log.open('w') as output:
        worker=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=output,stderr=subprocess.STDOUT)
        app=Celery('acceptance-client',broker=url,backend=url)
        app.conf.update(task_serializer='json',result_serializer='json',accept_content=['json'])
        result=None
        try:
            payload={'tenant':'test-only','value':42,'items':['a',None,True]}
            result=app.send_task(taskname,args=[payload],queue=queue,expires=30)
            assert result.get(timeout=30)=={'transport':'real-worker','payload':payload}
            assert result.state=='SUCCESS'
            assert worker.poll() is None,log.read_text()
        finally:
            worker.terminate()
            try:worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill();worker.wait(timeout=5)
            if result is not None:result.forget()
            Redis.from_url(url).delete(queue)
            app.close()
