"""Local-first, consent-bound knowledge ingestion with deterministic offline primitives."""
from __future__ import annotations
import hashlib,json,math,re,shutil
from dataclasses import dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Protocol
from .schemas import *

class KnowledgeError(ValueError): pass
class ConsentError(KnowledgeError): pass
class UnsupportedSourceError(KnowledgeError): pass
class DimensionMismatch(KnowledgeError): pass
class UnsupportedClaim(KnowledgeError): pass
class AdapterUnavailable(RuntimeError): pass

class Embedder(Protocol):
    dimension:int
    def embed(self,text:str)->list[float]:...
class DeterministicEmbedder:
    dimension=16
    def embed(self,text:str)->list[float]:
        out=[0.0]*self.dimension
        for token in re.findall(r"[a-z0-9]+",text.lower()): out[int(hashlib.sha256(token.encode()).hexdigest(),16)%self.dimension]+=1
        n=math.sqrt(sum(x*x for x in out)); return [x/n for x in out] if n else out
class Transcriber(Protocol):
    def transcribe(self,audio:bytes)->list[Segment]:...
class UnavailableTranscriber:
    def transcribe(self,audio:bytes)->list[Segment]: raise AdapterUnavailable('transcription adapter unavailable')

@dataclass
class Version:
    number:int; content_hash:str; segments:list[Segment]; created_at:datetime; mime_type:str
@dataclass
class Record:
    source:SourceRegistration; tenant_id:str; versions:list[Version]=field(default_factory=list)
@dataclass
class Chunk:
    tenant_id:str; source_id:str; version:int; chunk_id:str; text:str; anchors:list[str]; vector:list[float]; created_at:datetime

class LocalKnowledgePipeline:
    SUPPORTED={'text/plain','text/html','text/markdown','application/json','audio/wav'}
    # application/pdf was removed: extraction was a UTF-8 paragraph split, not
    # genuine PDF decoding; accepting it as PDF would overstate the evidence.
    def __init__(self,root:Path,tenant_id:str,actor_id:str,*,embedder:Embedder|None=None,transcriber:Transcriber|None=None,clock=lambda:datetime.now(timezone.utc)):
        self.root=root.resolve(); self.tenant_id=tenant_id; self.actor_id=actor_id; self.embedder=embedder or DeterministicEmbedder(); self.transcriber=transcriber or UnavailableTranscriber(); self.clock=clock
        self.records:dict[str,Record]={}; self.chunks:list[Chunk]=[]; self.edges:list[dict]=[]
        self.workspace=(self.root/tenant_id).resolve()
        if self.root not in self.workspace.parents: raise KnowledgeError('workspace escapes mounted boundary')
        self.workspace.mkdir(parents=True,exist_ok=True)
    def _contained(self,*parts:str)->Path:
        # Containment is resolved-path based and checked BEFORE any write or
        # state mutation; '..' and '.' segments cannot escape the tenant
        # workspace. Residual, code-grounded: a pre-existing symlink inside
        # the workspace is followed by resolve() - symlink swap attacks are
        # not closed by this check.
        if any(part in ('.','..') for part in parts): raise KnowledgeError('dot-segment source ids are not valid paths')
        p=self.workspace.joinpath(*parts).resolve()
        # Strict child: the workspace root itself is never a valid write or
        # delete target, however a part resolves.
        if p==self.workspace or self.workspace not in p.parents: raise KnowledgeError('path escapes tenant workspace')
        return p
    def _check_consent(self,source:SourceRegistration)->None:
        # Caller-supplied consent metadata is a claimed record, not
        # authenticated authority; identity/evidence verification is a held
        # boundary outside this pipeline.
        exp=source.consent.expires_at
        if exp is not None:
            if exp.tzinfo is None: raise ConsentError('consent expiry must be timezone-aware')
            if exp<=self.clock(): raise ConsentError('consent is expired')
        if 'knowledge_ingestion' not in source.consent.purposes: raise ConsentError('missing knowledge_ingestion consent')
    def register(self,source:SourceRegistration)->Record:
        self._contained(source.source_id)
        self._check_consent(source)
        old=self.records.get(source.source_id)
        if old and old.tenant_id!=self.tenant_id: raise KnowledgeError('cross-tenant source access denied')
        manifest=self._contained(source.source_id)/'manifest.json'
        if manifest.exists():
            # The disk may record versions from a prior process that this
            # pipeline never loaded. Persisting now would silently erase
            # them, so refuse instead; restart state recovery is a carried
            # gap, not accepted.
            try: disk_versions=len(json.loads(manifest.read_text(encoding='utf-8')).get('versions',[]))
            except (OSError,json.JSONDecodeError) as exc: raise KnowledgeError('unreadable on-disk manifest; refusing to overwrite prior state') from exc
            if disk_versions>len(old.versions if old else ()): raise KnowledgeError('on-disk manifest records versions not loaded in this pipeline; refusing to overwrite prior state')
        rec=old or Record(source,self.tenant_id); self.records[source.source_id]=rec
        try: self._persist_manifest(rec)
        except OSError:
            # A brand-new registration must not linger in memory when its
            # manifest never reached disk.
            if old is None: self.records.pop(source.source_id,None)
            raise
        return rec
    def ingest(self,request:IngestRequest)->Version:
        if request.actor_id!=self.actor_id: raise KnowledgeError('actor is not authorized for this workspace')
        self._check_consent(request.source)
        if request.mime_type not in self.SUPPORTED: raise UnsupportedSourceError(f'unsupported mime type: {request.mime_type}')
        raw=request.content.encode() if isinstance(request.content,str) else request.content
        if not raw: raise KnowledgeError('malformed or empty source')
        digest=hashlib.sha256(raw).hexdigest()
        prior=self.records.get(request.source.source_id)
        if prior and prior.tenant_id!=self.tenant_id: raise KnowledgeError('cross-tenant source access denied')
        if prior and prior.versions and prior.versions[-1].content_hash==digest:return prior.versions[-1]
        # All validation and extraction happen BEFORE any state mutation or
        # write, so a failed ingest leaves no registered record behind.
        segments=self._extract(raw,request.mime_type,request.source.kind)
        version=Version((len(prior.versions) if prior else 0)+1,digest,segments,self.clock(),request.mime_type)
        new_chunks=self._chunk(prior or Record(request.source,self.tenant_id),version)
        # Registration is durable before any version file is written: a later
        # failure leaves a truthful registered record with no new version,
        # never a false version claim.
        rec=self.register(request.source)
        target=self._contained(request.source.source_id,f'v{version.number}')
        if target.exists():
            # In-memory versions are lost on restart while disk persists, so a
            # fresh pipeline can recompute a version number whose directory
            # already holds prior data. Refuse rather than overwrite, and never
            # let failure cleanup remove data this attempt did not create.
            raise KnowledgeError('version target already exists on disk; refusing to overwrite')
        import uuid as _uuid
        tmp=target.with_name(target.name+f'.tmp-{_uuid.uuid4().hex}')
        try:
            # Build the version in a private temp dir, then rename it into
            # place. Cleanup only ever removes the temp dir this attempt
            # created; preexisting version contents are never touched.
            tmp.mkdir(parents=True); (tmp/'source.bin').write_bytes(raw)
            (tmp/'segments.json').write_text(json.dumps([s.model_dump(mode='json') for s in segments],sort_keys=True),encoding='utf-8')
            import os as _os; _os.rename(tmp,target)
        except OSError:
            shutil.rmtree(tmp,ignore_errors=True); raise
        rec.versions.append(version); self.chunks.extend(new_chunks); self.edges.append({'from':request.source.source_id,'to':digest,'relation':'has_version','version':version.number})
        try:
            self._persist_manifest(rec)
        except OSError:
            # Persist failed AFTER memory mutation: roll the version state
            # back so memory never claims a version the manifest does not
            # record. The durable registration (its own manifest was written
            # before any version file) is PRESERVED. The version dir was
            # created by this attempt (rename from tmp), so removing it
            # cannot touch preexisting data; if that removal itself fails,
            # an untracked but complete version dir remains on disk with no
            # false memory claim.
            rec.versions.pop(); del self.chunks[len(self.chunks)-len(new_chunks):]; self.edges.pop()
            shutil.rmtree(target,ignore_errors=True)
            try: self._persist_manifest(rec)
            except OSError: pass
            raise KnowledgeError('manifest persistence failed; version rolled back, registration preserved')
        return version
    def _extract(self,raw:bytes,mime:str,kind:str)->list[Segment]:
        if mime=='audio/wav':
            segments=self.transcriber.transcribe(raw)
            for s in segments:
                if s.start_seconds is None or s.end_seconds is None: raise KnowledgeError('transcription must be time-aligned')
                if s.speaker is None: s.speaker='unknown'
                if '[inaudible]' in s.text.lower(): s.text=re.sub(r'(?i)\[inaudible\].*','[inaudible]',s.text)
            return segments
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError as exc:raise KnowledgeError('malformed text encoding') from exc
        if mime=='application/json':
            try:text=json.dumps(json.loads(text),sort_keys=True)
            except json.JSONDecodeError as exc:raise KnowledgeError('malformed JSON source') from exc
        text=re.sub(r'<[^>]+>',' ',text) if mime=='text/html' else text
        blocks=[x.strip() for x in re.split(r'\n\s*\n',text) if x.strip()]
        if not blocks:raise KnowledgeError('source contains no extractable text')
        anchor_kind='post' if kind=='forum' else ('page' if kind=='book' or mime=='application/pdf' else 'paragraph')
        return [Segment(text=x,anchors=[Anchor(anchor_id=f'{anchor_kind}-{i}',kind=anchor_kind,value=str(i))]) for i,x in enumerate(blocks,1)]
    def _chunk(self,rec:Record,v:Version)->list[Chunk]:
        out=[]
        for i,s in enumerate(v.segments,1):
            for j in range(0,len(s.text),800):
                text=s.text[j:j+800]; vector=self.embedder.embed(text)
                if len(vector)!=self.embedder.dimension:raise DimensionMismatch('embedding dimension mismatch')
                out.append(Chunk(self.tenant_id,rec.source.source_id,v.number,f'{rec.source.source_id}:v{v.number}:c{i}.{j//800+1}',text,[a.anchor_id for a in s.anchors],vector,v.created_at))
        return out
    def search(self,query:str,limit=10,*,tenant_id:str|None=None)->list[dict]:
        if tenant_id and tenant_id!=self.tenant_id:raise KnowledgeError('cross-tenant retrieval denied')
        qv=self.embedder.embed(query)
        if len(qv)!=self.embedder.dimension:raise DimensionMismatch('embedding dimension mismatch')
        terms=set(re.findall(r'[a-z0-9]+',query.lower()))
        def score(c):
            lexical=len(terms & set(re.findall(r'[a-z0-9]+',c.text.lower())))/max(1,len(terms)); vector=sum(a*b for a,b in zip(qv,c.vector)); return .5*lexical+.5*vector
        return [{'source_id':c.source_id,'version':c.version,'chunk_id':c.chunk_id,'text':c.text,'anchor_ids':c.anchors,'score':score(c)} for c in sorted(self.chunks,key=score,reverse=True)[:limit] if score(c)>0]
    def substantiate(self,claims:list[Claim])->list[Claim]:
        # Contract, exactly: every citation anchor must exist in stored chunks
        # AND quote_hash must equal sha256 of the stored segment text carrying
        # that anchor. This verifies the citation binds to bytes this pipeline
        # stored - it does NOT verify that the quote entails the claim or that
        # the claim is factually true.
        segments={(r.source.source_id,v.number,a.anchor_id):seg.text
                  for r in self.records.values() for v in r.versions
                  for seg in v.segments for a in seg.anchors}
        for claim in claims:
            ok=bool(claim.citations) and all(
                (key:=(x.source_id,x.version,a)) in segments
                and hashlib.sha256(segments[key].encode()).hexdigest()==x.quote_hash
                for x in claim.citations for a in x.anchor_ids)
            if not ok:raise UnsupportedClaim(f'unsupported claim withheld: {claim.text}')
        return claims
    def contradictions(self,subject:str)->list[dict]:
        hits=self.search(subject,100); conflicts=[]
        for i,a in enumerate(hits):
            for b in hits[i+1:]:
                neg=lambda x:bool(re.search(r'\b(no|not|never|false|cannot)\b',x.lower()))
                if a['source_id']!=b['source_id'] and neg(a['text'])!=neg(b['text']):
                    ra=self.records[a['source_id']].versions[a['version']-1]; rb=self.records[b['source_id']].versions[b['version']-1]
                    conflicts.append({'subject':subject,'a':a,'b':b,'fresher':'a' if ra.created_at>=rb.created_at else 'b','status':'conflict_requires_review'})
        return conflicts
    def export(self)->dict:
        return {'tenant_id':self.tenant_id,'sources':[{**r.source.model_dump(mode='json'),'versions':[{'number':v.number,'hash':v.content_hash,'segments':[s.model_dump(mode='json') for s in v.segments]} for v in r.versions]} for r in self.records.values()],'provenance_edges':self.edges}
    def delete_verified(self,source_id:str)->dict:
        path=self._contained(source_id)
        if source_id not in self.records:raise KeyError(source_id)
        shutil.rmtree(path,ignore_errors=True)
        verified=not path.exists()
        if verified:
            self.records.pop(source_id); self.chunks=[c for c in self.chunks if c.source_id!=source_id]; self.edges=[e for e in self.edges if e['from']!=source_id]
        # Truthful tracking: when the disk removal did not happen, memory
        # keeps the record and the result says so - never deleted=False with
        # the tracking silently gone.
        return {'source_id':source_id,'deleted':verified,'tracking_retained':not verified,'verified_at':self.clock().isoformat()}
    def _persist_manifest(self,rec:Record):
        p=self._contained(rec.source.source_id); p.mkdir(parents=True,exist_ok=True)
        import os as _os, uuid as _uuid
        tmp=p/f'manifest.json.tmp-{_uuid.uuid4().hex}'
        tmp.write_text(json.dumps({'tenant_id':self.tenant_id,'source':rec.source.model_dump(mode='json'),'versions':[{'number':v.number,'hash':v.content_hash} for v in rec.versions]},sort_keys=True),encoding='utf-8')
        _os.replace(tmp,p/'manifest.json')
