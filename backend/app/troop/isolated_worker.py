"""Registered Python actions in M04 namespace isolation, not thread callables.

The host registers source code. No network, credentials, account connections or
external effects are provided. The default runner executes only Python/stdlib.
Attempts that reach the sandbox keep hashes, exit state and capped diagnostic logs in a bounded
in-process receipt list. Receipts are execution evidence, not approval authority.
"""
from __future__ import annotations
import ast,hashlib,json,tempfile
from pathlib import Path
from threading import Lock
from .roles import WorkerError

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
class IsolatedPythonWorker:
    def __init__(self,*,timeout_seconds=15,memory_mb=256,max_receipts=1000):
        for name,value,low,high in [('timeout_seconds',timeout_seconds,1,300),('memory_mb',memory_mb,64,4096),('max_receipts',max_receipts,1,10000)]:
            if type(value) is not int or not low<=value<=high:raise ValueError(name+' outside bounds')
        self.timeout_seconds=timeout_seconds;self.memory_mb=memory_mb;self.max_receipts=max_receipts
        self._sources={};self._receipts=[];self._lock=Lock()
    @property
    def receipts(self):
        with self._lock:return json.loads(canonical(self._receipts))
    def register(self,name,source):
        if not isinstance(name,str) or not name.strip() or len(name)>128:raise ValueError('bounded action name required')
        if not isinstance(source,str) or not source.strip() or len(source)>100000:raise ValueError('bounded source required')
        parsed=ast.parse(source)
        if not any(isinstance(n,ast.FunctionDef) and n.name=='action' for n in parsed.body):raise ValueError('action function required')
        with self._lock:
            if name in self._sources:raise ValueError('action already registered')
            self._sources[name]=source
    def execute(self,step,inputs,attempt,feedback):
        from app.modules.m04_research_scientist.approved_sandbox import BubblewrapBackend,ExecutionLimits
        with self._lock:source=self._sources.get(step.action)
        if source is None:raise WorkerError('unregistered isolated action')
        # Freeze action arguments and upstream values before invoking any code.
        payload=canonical({'args':step.args,'inputs':inputs,'attempt':attempt,'feedback':feedback})
        if len(payload.encode())>1_000_000:raise WorkerError('action input exceeds 1MB')
        backend=BubblewrapBackend()
        with tempfile.TemporaryDirectory(prefix='atlas-troop-isolated-') as root:
            input_dir=Path(root)/'input';output_dir=Path(root)/'output';input_dir.mkdir();output_dir.mkdir()
            (input_dir/'payload.json').write_text(payload)
            entry=source+'''\n
import json as _atlas_json
with open('/input/payload.json',encoding='utf-8') as _atlas_file:
    _atlas_payload=_atlas_json.load(_atlas_file)
_atlas_result=action(_atlas_payload['args'],_atlas_payload['inputs'],_atlas_payload['attempt'],_atlas_payload['feedback'])
_atlas_encoded=_atlas_json.dumps(_atlas_result,sort_keys=True,separators=(',',':'),allow_nan=False)
if len(_atlas_encoded.encode())>1000000:
    raise ValueError('output exceeds 1MB')
with open('/output/result.json','w',encoding='utf-8') as _atlas_file:
    _atlas_file.write(_atlas_encoded)
'''
            (input_dir/'analysis.py').write_text(entry)
            run=backend.run(language='python',input_dir=input_dir,output_dir=output_dir,limits=ExecutionLimits(timeout_seconds=self.timeout_seconds,memory_mb=self.memory_mb,max_file_mb=2,max_log_bytes=65536,max_output_bytes=1_000_000))
            receipt={'step_id':step.id,'action':step.action,'attempt':attempt,'source_sha256':digest(source),'input_sha256':digest(payload),'backend':run.backend,'isolation':run.isolation,'exit_code':run.exit_code,'timed_out':run.timed_out,'stdout':run.stdout.decode(errors='replace'),'stderr':run.stderr.decode(errors='replace'),'stdout_truncated':run.stdout_truncated,'stderr_truncated':run.stderr_truncated,'duration_seconds':run.duration_seconds,'output_sha256':None}
            try:
                if run.timed_out or run.exit_code!=0:raise WorkerError('isolated action timed out or failed')
                path=output_dir/'result.json'
                if path.is_symlink() or not path.is_file() or path.stat().st_size>1_000_000:raise WorkerError('bounded result file required')
                raw=path.read_bytes();value=json.loads(raw)
                canonical(value) # Refuse non-finite JSON constants accepted by Python decoder.
                receipt['output_sha256']=hashlib.sha256(raw).hexdigest()
                return value
            except (ValueError,OSError) as exc:raise WorkerError('invalid isolated action result') from exc
            finally:
                with self._lock:
                    self._receipts.append(receipt);self._receipts=self._receipts[-self.max_receipts:]
