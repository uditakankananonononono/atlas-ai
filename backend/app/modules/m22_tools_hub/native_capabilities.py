"""Native Atlas capability workbench inspired by useful interaction patterns.

This module copies no provider implementation or branding. It provides local,
testable primitives for app generation, code workspaces, cited research,
multimodal event normalization, and approval-gated capability installation.
"""
from __future__ import annotations
import ast, copy, hashlib, io, json, re, subprocess, sys, tempfile, time, uuid
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

class CapabilityError(ValueError): pass
class SandboxError(CapabilityError): pass

def _id(prefix: str, value: str = "") -> str:
    return prefix + "_" + hashlib.sha256((value or str(uuid.uuid4())).encode()).hexdigest()[:16]

def _path(name: str) -> str:
    p=Path(name)
    if p.is_absolute() or '..' in p.parts or not p.name: raise CapabilityError(f"unsafe workspace path: {name}")
    return p.as_posix()

def _validate_python(source: str) -> None:
    try: tree=ast.parse(source)
    except SyntaxError as exc: raise SandboxError(f"invalid Python: {exc.msg}") from exc
    banned=(ast.Global,ast.Nonlocal)
    if any(isinstance(n,banned) for n in ast.walk(tree)): raise SandboxError("global/nonlocal statements are disabled")
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in {'models','app'} for a in n.names): raise SandboxError("only workspace-local models/app imports are allowed")
        if isinstance(n,ast.ImportFrom) and n.module not in {'models','app'}: raise SandboxError("only workspace-local models/app imports are allowed")
    banned_calls={'eval','exec','compile','open','input','__import__'}
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in banned_calls:
            raise SandboxError(f"call disabled in sandbox: {n.func.id}")
        if isinstance(n,ast.Attribute) and n.attr.startswith('__'): raise SandboxError("dunder access is disabled")

@dataclass
class Snapshot:
    id: str; files: dict[str,str]; manifest: dict[str,str]; reason: str; created_at: float

class CodeWorkspace:
    """Tenant-scoped in-memory workspace with snapshots and a bounded Python runner."""
    def __init__(self, workspace_id: str|None=None):
        self.id=workspace_id or _id('ws'); self.files={}; self.manifest={}; self.snapshots=[]; self.logs=[]
        self.snapshot('initial')
    def write(self,path:str,content:str)->dict[str,Any]:
        path=_path(path)
        if not isinstance(content,str): raise CapabilityError('content must be text')
        if len(content)>200_000: raise CapabilityError('file exceeds 200KB workspace limit')
        self.files[path]=content
        return {'path':path,'sha256':hashlib.sha256(content.encode()).hexdigest(),'bytes':len(content.encode())}
    def set_manifest(self,manifest:dict[str,str])->dict[str,str]:
        for k,v in manifest.items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]+',k) or not re.fullmatch(r'[A-Za-z0-9*+_.<>=!~,-]+',v): raise CapabilityError('invalid dependency manifest entry')
        self.manifest=dict(sorted(manifest.items())); return self.manifest
    def snapshot(self,reason:str)->Snapshot:
        snap=Snapshot(_id('snap',self.id+str(len(self.snapshots))+reason),copy.deepcopy(self.files),copy.deepcopy(self.manifest),reason,time.time())
        self.snapshots.append(snap); return snap
    def rollback(self,snapshot_id:str)->dict[str,Any]:
        snap=next((s for s in self.snapshots if s.id==snapshot_id),None)
        if not snap: raise CapabilityError('snapshot not found')
        before=self.snapshot('before rollback'); self.files=copy.deepcopy(snap.files); self.manifest=copy.deepcopy(snap.manifest)
        return {'rolled_back_to':snap.id,'safety_snapshot':before.id,'files':sorted(self.files)}
    def run(self,path:str,timeout_seconds:float=2)->dict[str,Any]:
        path=_path(path)
        if path not in self.files: raise SandboxError('entry file not found')
        if not path.endswith('.py'): raise SandboxError('only Python entries are executable')
        _validate_python(self.files[path])
        timeout_seconds=min(max(float(timeout_seconds),.05),3.0)
        with tempfile.TemporaryDirectory(prefix='atlas-workspace-') as root:
            for name,content in self.files.items():
                target=Path(root)/_path(name); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content)
            try:
                cp=subprocess.run([sys.executable,'-B',path],cwd=root,text=True,capture_output=True,timeout=timeout_seconds,env={'PYTHONIOENCODING':'utf-8'})
                result={'command':['python','-B',path],'exit_code':cp.returncode,'stdout':cp.stdout[-10000:],'stderr':cp.stderr[-10000:],'timed_out':False}
            except subprocess.TimeoutExpired as exc:
                result={'command':['python','-B',path],'exit_code':124,'stdout':(exc.stdout or '')[-10000:] if isinstance(exc.stdout,str) else '','stderr':'execution timed out','timed_out':True}
        self.logs.append(result); return result
    def test(self,test_path:str)->dict[str,Any]:
        result=self.run(test_path); result['passed']=result['exit_code']==0; return result

class SpecAppBuilder:
    TYPES={'string':'str','integer':'int','number':'float','boolean':'bool'}
    def build(self,spec:dict[str,Any])->dict[str,Any]:
        name=str(spec.get('name','')).strip(); entities=spec.get('entities');
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9 _-]{1,60}',name): raise CapabilityError('app name is required and must be safe')
        if not isinstance(entities,list) or not entities: raise CapabilityError('at least one entity is required')
        ws=CodeWorkspace(_id('app',name)); schema={}; api=[]; ui=[]
        model_lines=[]
        for entity in entities:
            en=entity.get('name',''); fields=entity.get('fields',[])
            if not re.fullmatch(r'[A-Z][A-Za-z0-9]*',en) or not fields: raise CapabilityError('entity names must be PascalCase and have fields')
            model_lines += [f'class {en}:']
            seen=set(); normalized=[]
            for f in fields:
                fn=f.get('name',''); ft=f.get('type')
                if not re.fullmatch(r'[a-z][a-z0-9_]*',fn) or fn in seen or ft not in self.TYPES: raise CapabilityError(f'invalid field in {en}')
                seen.add(fn); normalized.append({'name':fn,'type':ft,'required':bool(f.get('required',True))}); model_lines.append(f"    {fn}: {self.TYPES[ft]}")
            schema[en]=normalized; low=en.lower(); api += [f'GET /api/{low}',f'POST /api/{low}',f'GET /api/{low}/{{id}}',f'DELETE /api/{low}/{{id}}']; ui += [f'{en}List',f'{en}Form',f'{en}Detail']
        ws.write('models.py','\n'.join(model_lines)+'\n')
        ws.write('app.py',"from models import *\n\ndef health(): return {'status':'ok'}\n\nprint(health())\n")
        ws.write('test_app.py',"from app import health\nassert health()=={'status':'ok'}\nprint('generated app tests passed')\n")
        ws.write('app_manifest.json',json.dumps({'name':name,'schema':schema,'routes':api,'components':ui},indent=2,sort_keys=True))
        ws.set_manifest({'python':'>=3.12'}); snap=ws.snapshot('generated from spec'); run=ws.run('app.py'); tests=ws.test('test_app.py')
        return {'app_id':ws.id,'schema':schema,'ui_components':ui,'api_routes':api,'files':copy.deepcopy(ws.files),'preview':run,'tests':tests,'snapshot_id':snap.id,'revision':0,'workspace':ws}
    def revise(self,build:dict[str,Any],changes:list[dict[str,str]])->dict[str,Any]:
        ws=build['workspace']; before=ws.snapshot('before revision')
        for change in changes:
            path=_path(change.get('path','')); old=change.get('old',''); new=change.get('new','')
            if path not in ws.files: raise CapabilityError(f'revision file not found: {path}')
            if not old or old not in ws.files[path]: raise CapabilityError(f'revision target not found: {path}')
            ws.write(path,ws.files[path].replace(old,new,1))
        test=ws.test('test_app.py')
        if not test['passed']:
            ws.rollback(before.id); raise CapabilityError('revision failed tests and was rolled back')
        after=ws.snapshot('validated revision'); build.update(files=copy.deepcopy(ws.files),tests=test,snapshot_id=after.id,revision=build['revision']+1)
        return build

class ResearchAgent:
    def answer(self,question:str,sources:list[dict[str,Any]],tool_calls:list[dict[str,Any]]|None=None)->dict[str,Any]:
        if not question.strip(): raise CapabilityError('question is required')
        usable=[]
        for i,s in enumerate(sources):
            url=s.get('url',''); text=s.get('text','').strip(); observed=s.get('observed_at')
            if urlparse(url).scheme not in {'http','https'} or not text or not observed: continue
            usable.append({'id':s.get('id') or f's{i+1}','title':s.get('title') or urlparse(url).netloc,'url':url,'text':text,'observed_at':observed})
        if not usable: raise CapabilityError('at least one current, cited source with observed_at is required')
        claims=[{'text':re.split(r'(?<=[.!?])\s+',s['text'])[0][:500],'citation_ids':[s['id']]} for s in usable]
        conflicts=len({c['text'].lower() for c in claims})>1
        confidence=max(.2,min(.95,.45+.12*len(usable)-(.2 if conflicts else 0)))
        return {'question':question,'answer':' '.join(f"{c['text']} [{c['citation_ids'][0]}]" for c in claims),'claims':claims,'citations':[{k:s[k] for k in ('id','title','url','observed_at')} for s in usable],'tool_calls':tool_calls or [],'reasoning_summary':f'Used {len(usable)} current source(s); '+('sources differ, so confidence was reduced.' if conflicts else 'source excerpts were directly cited.'),'confidence':round(confidence,2),'provider_parity_claim':False}

class LiveAssistant:
    KINDS={'image':{'mime_prefix':'image/','observation':'visual'},'audio':{'mime_prefix':'audio/','observation':'transcript'},'document':{'mime_prefix':'','observation':'document_text'}}
    def normalize(self,event:dict[str,Any])->dict[str,Any]:
        kind=event.get('kind'); mime=event.get('mime_type',''); content=event.get('content')
        if kind not in self.KINDS: raise CapabilityError('kind must be image, audio, or document')
        if kind!='document' and not mime.startswith(self.KINDS[kind]['mime_prefix']): raise CapabilityError('mime type does not match event kind')
        if not isinstance(content,str) or not content.strip(): raise CapabilityError('extracted content is required; raw media is not hallucinated')
        observation={'type':self.KINDS[kind]['observation'],'text':content.strip(),'grounded_in':event.get('source_id') or _id('event',content),'mime_type':mime,'occurred_at':event.get('occurred_at')}
        return {'event_id':_id('evt',json.dumps(event,sort_keys=True)),'kind':kind,'observation':observation,'uncertainties':event.get('uncertainties',[]),'normalized':True}
    def propose_action(self,normalized:dict[str,Any],action:str,args:dict[str,Any],risk:str='low')->dict[str,Any]:
        if not normalized.get('normalized'): raise CapabilityError('normalized event required')
        bounded={'summarize','extract_fields','create_draft','classify'}
        approved=risk=='low' and action in bounded
        return {'action_id':_id('action',action+json.dumps(args,sort_keys=True)),'action':action,'arguments':args,'status':'ready' if approved else 'awaiting_human_approval','approval_required':not approved,'executed':False,'grounded_in':normalized['event_id']}

class DiscoveryPipeline:
    def manifest(self,name:str,sources:list[dict[str,Any]],capabilities:list[str],license_name:str,permissions:list[str])->dict[str,Any]:
        official=[]
        for s in sources:
            if s.get('official') and urlparse(s.get('url','')).scheme in {'http','https'} and s.get('observed_at'): official.append({k:s.get(k) for k in ('title','url','observed_at')})
        if not official: raise CapabilityError('official current source required')
        risks=[]
        if not license_name or license_name.lower() in {'unknown','proprietary-unlicensed'}: risks.append('license_unresolved')
        sensitive={'shell','filesystem_write','network','secrets','payments'} & set(permissions)
        risks += [f'sensitive_permission:{p}' for p in sorted(sensitive)]
        return {'manifest_id':_id('manifest',name+json.dumps(capabilities)),'name':name,'capabilities':sorted(set(capabilities)),'official_sources':official,'license':license_name,'permissions':sorted(set(permissions)),'threat_findings':risks,'review_status':'blocked' if 'license_unresolved' in risks else 'needs_human_review'}
    def generate_adapter(self,manifest:dict[str,Any])->dict[str,Any]:
        code="def invoke(capability, payload):\n    allowed="+repr(manifest['capabilities'])+"\n    if capability not in allowed: raise ValueError('capability not allowed')\n    return {'capability': capability, 'payload': payload, 'native_atlas_adapter': True}\n"
        return {'adapter_id':_id('adapter',manifest['manifest_id']),'code':code,'source_manifest_id':manifest['manifest_id'],'copied_vendor_code':False}
    def sandbox_test(self,adapter:dict[str,Any],capability:str)->dict[str,Any]:
        _validate_python(adapter['code']); scope={}; exec(compile(adapter['code'],'<adapter>','exec'),{'__builtins__':{'ValueError':ValueError}},scope)
        output=scope['invoke'](capability,{'probe':True}); return {'passed':output['native_atlas_adapter'] is True,'output':output}
    def install_plan(self,manifest:dict[str,Any],adapter:dict[str,Any],test:dict[str,Any],approved:bool=False)->dict[str,Any]:
        blocked=manifest['review_status']=='blocked' or not test.get('passed'); state='installed' if approved and not blocked else ('blocked' if blocked else 'awaiting_human_approval')
        return {'installation_id':_id('install',adapter['adapter_id']),'state':state,'approval_required':state!='installed','rollback':{'operation':'remove_adapter','adapter_id':adapter['adapter_id'],'restore_previous_snapshot':True},'human_review':{'license':manifest['license'],'permissions':manifest['permissions'],'threat_findings':manifest['threat_findings']}}

def native_capabilities()->list[dict[str,str]]:
    return [{'id':'spec-to-app','description':'Generate schema, UI/API plan, runnable preview, tests, and revisions'}, {'id':'code-workspace','description':'Multi-file bounded run/test workspace with logs, manifests, snapshots and rollback'}, {'id':'cited-research','description':'Current-source cited conversation with tool-call trace and confidence'}, {'id':'multimodal-assistant','description':'Normalize extracted image/audio/document events and gate actions'}, {'id':'discovery-install','description':'Official-source manifest, threat/license review, adapter test, approval and rollback'}]
