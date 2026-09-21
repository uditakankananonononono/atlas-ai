"""Portable, content-addressed computational-science reproducibility bundles."""
from __future__ import annotations
import hashlib,json,platform,sys,zipfile
from io import BytesIO
from typing import Any

def _canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),default=str).encode()
def build_bundle(*,title:str,code:str,language:str,inputs:dict[str,Any],parameters:dict[str,Any],seed:int,expected_outputs:list[str],dependencies:list[str],source_urls:list[str])->tuple[bytes,dict]:
 if not title.strip() or not code.strip():raise ValueError('title and code are required')
 if language not in {'python','r'}:raise ValueError('language must be python or r')
 if seed<0:raise ValueError('seed must be non-negative')
 input_hashes={k:'sha256:'+hashlib.sha256(_canonical(v)).hexdigest() for k,v in sorted(inputs.items())}
 manifest={'schema_version':1,'title':title,'language':language,'seed':seed,'parameters':parameters,'input_hashes':input_hashes,'expected_outputs':expected_outputs,'dependencies':sorted(set(dependencies)),'source_urls':source_urls,'runtime':{'python':sys.version.split()[0],'platform':platform.platform()},'execution_performed':False}
 manifest['manifest_sha256']='sha256:'+hashlib.sha256(_canonical(manifest)).hexdigest()
 out=BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('manifest.json',json.dumps(manifest,indent=2,sort_keys=True))
  z.writestr('analysis.py' if language=='python' else 'analysis.R',code)
  z.writestr('parameters.json',json.dumps(parameters,indent=2,sort_keys=True))
  z.writestr('inputs.json',json.dumps(inputs,indent=2,sort_keys=True,default=str))
  z.writestr('README.md',f'# {title}\n\nRun only after reviewing the manifest, inputs, dependencies and code. Seed: `{seed}`. No execution is claimed by this bundle.\n')
 payload=out.getvalue();manifest['bundle_sha256']='sha256:'+hashlib.sha256(payload).hexdigest()
 return payload,manifest
