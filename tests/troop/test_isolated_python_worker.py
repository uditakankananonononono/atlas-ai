import pytest
from app.troop.roles import Step,Plan,RuleReviewer
from app.troop.runner import TroopRunner
from app.troop.isolated_worker import IsolatedPythonWorker

def test_actual_namespace_workers_execute_dependency_inputs_and_hashes():
    worker=IsolatedPythonWorker(timeout_seconds=2)
    worker.register('first','def action(args, inputs, attempt, feedback):\n return {"total":sum(args["values"])}\n')
    worker.register('next','def action(args, inputs, attempt, feedback):\n return inputs["a"]["total"] * 2\n')
    class Planner:
        def plan(self,task):return Plan(task['id'],(Step('a','first',{'values':[2,3]}),Step('b','next',depends_on=('a',))))
    result=TroopRunner(Planner(),worker,RuleReviewer(),max_attempts=1).run({'id':'isolated'})
    assert result.status=='completed' and result.outputs['b']==10
    assert len(worker.receipts)==2
    assert all(r['backend']=='bubblewrap' and r['exit_code']==0 and len(r['source_sha256'])==64 for r in worker.receipts)

def test_timeout_ends_hung_worker_blocks_dependents_not_independent():
    # Sleep exercises the wall timer without racing RLIMIT_CPU on a busy loop.
    worker=IsolatedPythonWorker(timeout_seconds=1)
    worker.register('hang','def action(args, inputs, attempt, feedback):\n import time\n time.sleep(30)\n')
    worker.register('ok','def action(args, inputs, attempt, feedback):\n return 7\n')
    class Planner:
        def plan(self,task):return Plan(task['id'],(Step('a','hang'),Step('b','ok',depends_on=('a',)),Step('c','ok')))
    result=TroopRunner(Planner(),worker,RuleReviewer(),max_attempts=1,max_workers=2).run({'id':'timeout'})
    assert result.step_status=={'a':'failed','b':'blocked','c':'completed'} or result.step_status=={'c':'completed','a':'failed','b':'blocked'}
    assert result.outputs=={'c':7}
    assert any(r['timed_out'] for r in worker.receipts)

def test_non_json_outputs_refused_and_registered_sources_cannot_be_overwritten():
    worker=IsolatedPythonWorker(timeout_seconds=2)
    worker.register('bad','def action(args, inputs, attempt, feedback):\n return {1,2}\n')
    with pytest.raises(ValueError,match='already registered'):worker.register('bad','def action(*args): return 0')
    with pytest.raises(Exception):worker.execute(Step('a','bad'),{},1,None)
    assert worker.receipts[-1]['exit_code']!=0

def test_actual_worker_network_and_filesystem_boundaries(tmp_path):
    secret=tmp_path/'outside.txt';secret.write_text('private fixture')
    worker=IsolatedPythonWorker(timeout_seconds=2)
    worker.register('probe',f'''def action(args, inputs, attempt, feedback):
 import socket, os
 visible=os.path.exists({str(secret)!r})
 try:
  connection=socket.create_connection(('127.0.0.1',9),timeout=.2)
  connection.close()
  network=True
 except OSError:
  network=False
 try:
  open('/input/changed','w').write('bad')
  writable=True
 except OSError:
  writable=False
 return {{'outside_visible':visible,'network_connected':network,'input_writable':writable}}
''')
    assert worker.execute(Step('p','probe'),{},1,None)=={'outside_visible':False,'network_connected':False,'input_writable':False}
    assert worker.receipts[0]['isolation']['network']=='none (network namespace)'

def test_capped_receipts_and_detached_reads():
    worker=IsolatedPythonWorker(max_receipts=1)
    worker.register('ok','def action(args, inputs, attempt, feedback):\n return args["value"]\n')
    worker.execute(Step('a','ok',{'value':1}),{},1,None)
    worker.execute(Step('b','ok',{'value':2}),{},1,None)
    assert len(worker.receipts)==1 and worker.receipts[0]['step_id']=='b'
    view=worker.receipts;view[0]['step_id']='mutated';assert worker.receipts[0]['step_id']=='b'

def test_actual_receipt_hashes_bind_exact_source_payload_and_output():
    import hashlib
    from app.troop.isolated_worker import canonical
    source='def action(args, inputs, attempt, feedback):\n return args["value"]\n'
    worker=IsolatedPythonWorker(timeout_seconds=2)
    worker.register('echo',source)
    assert worker.execute(Step('e','echo',{'value':7}),{},1,None)==7
    receipt=worker.receipts[0]
    assert receipt['source_sha256']==hashlib.sha256(source.encode()).hexdigest()
    assert receipt['input_sha256']==hashlib.sha256(canonical({'args':{'value':7},'inputs':{},'attempt':1,'feedback':None}).encode()).hexdigest()
    assert receipt['output_sha256']==hashlib.sha256(b'7').hexdigest()
