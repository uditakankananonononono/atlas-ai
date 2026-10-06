import os
import subprocess
import sys


def test_missing_cvxpy_does_not_disable_unrelated_workbench_algorithms():
 code='''
import builtins
original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name=='cvxpy' or name.startswith('cvxpy.'):raise ImportError('test missing dependency')
 return original(name,*args,**kwargs)
builtins.__import__=guarded
from app.modules.m20_general_cognitive_worker.optimization_story_235_280 import execute,WorkbenchError
source={'title':'fixture','url':'https://example.org'}
r=execute('admm',{'source':source,'quadratic':[[1.]],'linear':[2.],'l1_penalty':.2})
assert abs(r['result']['solution'][0]-1.8)<1e-5
try:execute('semidefinite_programming',{'source':source})
except WorkbenchError as e:assert 'CVXPY is unavailable' in str(e)
else:raise AssertionError('missing conic solver did not fail closed')
'''
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONPATH':'backend'},capture_output=True,text=True,timeout=30)
 assert result.returncode==0,result.stderr
