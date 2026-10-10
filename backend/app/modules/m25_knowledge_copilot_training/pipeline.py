"""Local-first, consent-bound knowledge ingestion with deterministic offline primitives."""
from __future__ import annotations
import hashlib,json,math,re,shutil
from dataclasses import dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Protocol
from .schemas import *

class KnowledgeError(ValueError): pass
class ManifestOversizeError(KnowledgeError): pass
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
    # Upper bound for an on-disk manifest.json; see register().
    MANIFEST_MAX_BYTES=1_000_000
    # application/pdf was removed: extraction was a UTF-8 paragraph split, not
    # genuine PDF decoding; accepting it as PDF would overstate the evidence.
    def __init__(self,root:Path,tenant_id:str,actor_id:str,*,embedder:Embedder|None=None,transcriber:Transcriber|None=None,clock=lambda:datetime.now(timezone.utc)):
        self.root=root.resolve(); self.tenant_id=tenant_id; self.actor_id=actor_id; self.embedder=embedder or DeterministicEmbedder(); self.transcriber=transcriber or UnavailableTranscriber(); self.clock=clock
        self.records:dict[str,Record]={}; self.chunks:list[Chunk]=[]; self.edges:list[dict]=[]
        self.workspace=(self.root/tenant_id).resolve()
        if self.root not in self.workspace.parents: raise KnowledgeError('workspace escapes mounted boundary')
        self.workspace.mkdir(parents=True,exist_ok=True)
    def restore_verified(self,*,source_ids=None,same_adapters_attested=False):
        """Explicit startup restore. Deployment must attest original adapter identity.

        Does not infer source consent authority or allow custom network adapters.
        No default route auto-restore, migration, or permission grant.
        """
        from .recovery import rehydrate,RecoveryError
        if same_adapters_attested is not True:
            raise RecoveryError('original offline adapters must be explicitly attested',check='adapter-identity')
        return rehydrate(self,source_ids=source_ids)

    def _contained(self,*parts:str)->Path:
        # Containment is checked BEFORE any write or state mutation; '..' and
        # '.' segments cannot escape the tenant workspace.
        if any(part in ('.','..') for part in parts): raise KnowledgeError('dot-segment source ids are not valid paths')
        # Reject symlinked components inside the workspace before resolving:
        # a pre-existing symlink (dangling, or pointing at a sibling record)
        # must never redirect a write or delete into another directory.
        # Residual, code-grounded: a component swapped to a symlink AFTER
        # this check but before the write (TOCTOU) is not closed here.
        cursor=self.workspace
        for part in parts:
            cursor=cursor/part
            if cursor.is_symlink(): raise KnowledgeError('symlinked path component inside workspace; refusing')
        p=self.workspace.joinpath(*parts).resolve()
        # Strict child: the workspace root itself is never a valid write or
        # delete target, however a part resolves.
        if p==self.workspace or self.workspace not in p.parents: raise KnowledgeError('path escapes tenant workspace')
        return p
    @staticmethod
    def _validate_disk_manifest(disk)->list:
        # Exact schema: dict; tenant_id str; source dict with source_id str;
        # versions a list of {number:int (not bool), hash:64-hex-lowercase}
        # numbered exactly 1..N with no gaps or duplicates. Anything else
        # fails closed - [], null, dict-shaped or missing versions are never
        # treated as zero versions.
        bad=KnowledgeError('invalid on-disk manifest schema; refusing to overwrite prior state')
        if not isinstance(disk,dict): raise bad
        if not isinstance(disk.get('tenant_id'),str): raise bad
        source=disk.get('source')
        if not isinstance(source,dict) or not isinstance(source.get('source_id'),str): raise bad
        versions=disk.get('versions')
        if not isinstance(versions,list): raise bad
        hexdigits=set('0123456789abcdef')
        for i,entry in enumerate(versions,1):
            number=entry.get('number') if isinstance(entry,dict) else None
            digest=entry.get('hash') if isinstance(entry,dict) else None
            if not isinstance(number,int) or isinstance(number,bool): raise bad
            if number!=i: raise bad
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in hexdigits for c in digest): raise bad
        return versions

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
        manifest=self._contained(source.source_id,'manifest.json')
        if manifest.exists():
            # The disk may record state from a prior process or another actor
            # of this tenant. Validate the manifest schema exactly, then
            # require equivalence with what this pipeline is about to write;
            # anything else fails closed rather than silently overwriting.
            # The read itself is bounded: a manifest records roughly 120
            # bytes per version, so MANIFEST_MAX_BYTES admits on the order of
            # 8000 recorded versions; larger refuses instead of reading
            # unbounded.
            raw=self._read_bounded_file(manifest,self.MANIFEST_MAX_BYTES,'refusing to overwrite prior state','on-disk manifest','exceed the manifest bound')
            try: disk=json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise KnowledgeError('unreadable on-disk manifest; refusing to overwrite prior state') from exc
            dv=self._validate_disk_manifest(disk)
            if disk.get('tenant_id')!=self.tenant_id: raise KnowledgeError('on-disk manifest tenant differs; refusing to overwrite prior state')
            disk_source=disk['source']
            if disk_source.get('source_id')!=source.source_id: raise KnowledgeError('on-disk manifest source_id differs; refusing to overwrite prior state')
            mem_versions=old.versions if old else []
            # Exact state equality, both directions: a disk record with fewer
            # versions than memory (e.g. versions=[]) is divergence too, not
            # a writable base.
            if len(dv)!=len(mem_versions): raise KnowledgeError('on-disk manifest version count diverges from loaded state; refusing to overwrite prior state')
            for i,entry in enumerate(dv):
                if entry['number']!=mem_versions[i].number or entry['hash']!=mem_versions[i].content_hash:
                    raise KnowledgeError('on-disk manifest diverges from loaded version state; refusing to overwrite prior state')
            # Manifest-vs-bytes: every version the on-disk manifest records
            # must still have source.bin bytes hashing to the recorded
            # content hash. Establishes byte-equivalence of manifest-recorded
            # versions at register time ONLY - segments.json is not verified
            # and untracked files or directories are neither collected nor
            # claimed; this is not a whole-persistence guarantee. Cost is
            # O(recorded versions) bounded-content hashing per register.
            for entry in dv:
                on_disk=self._read_source_bytes(source.source_id,entry['number'],'refusing to overwrite prior state')
                if hashlib.sha256(on_disk).hexdigest()!=entry['hash']:
                    raise KnowledgeError(f"on-disk source bytes for version {entry['number']} diverge from the recorded hash; refusing to overwrite prior state")
            # Registration equivalence guards overwrite only; it is not
            # consent authority and treats no metadata field as verified.
            expected=source.model_dump(mode='json')
            for field_name in ('kind','canonical_url','title','author','published_at','metadata'):
                if disk_source.get(field_name)!=expected.get(field_name):
                    raise KnowledgeError(f'on-disk registration identity differs on {field_name}; refusing to overwrite prior state')
            disk_consent=disk_source.get('consent') if isinstance(disk_source.get('consent'),dict) else {}
            expected_consent=expected.get('consent',{})
            for field_name in ('granted_by','granted_at','purposes','expires_at','evidence'):
                if disk_consent.get(field_name)!=expected_consent.get(field_name):
                    raise KnowledgeError(f'on-disk consent record differs on {field_name}; refusing to overwrite prior state')
        rec=old or Record(source,self.tenant_id); self.records[source.source_id]=rec
        try: self._persist_manifest(rec)
        except (OSError, ManifestOversizeError):
            # A brand-new registration must not linger in memory when its
            # manifest never reached disk. An oversize refusal happens
            # before any manifest mutation, so prior disk bytes are intact.
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
        if prior and prior.versions and prior.versions[-1].content_hash==digest:
            # Dedup serves the recorded version only while the on-disk source
            # bytes still hash to it. Establishes last-version source-bytes
            # equivalence at serve time; older versions and segments.json are
            # not re-validated here - whole-store byte integrity stays carried.
            last=prior.versions[-1]
            on_disk=self._read_source_bytes(request.source.source_id,last.number,'dedup validation failed')
            if hashlib.sha256(on_disk).hexdigest()!=last.content_hash:
                raise KnowledgeError('dedup validation failed: on-disk source bytes diverge from the recorded hash; refusing to serve unverified content')
            return last
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
        import os as _os
        dfd=None
        # ONE unconditional finally owns the held descriptor's lifecycle:
        # whatever fails between acquisition and outcome - OSError or any
        # unexpected exception - cannot leak it. The handlers keep the error
        # state truthful: memory never claims a version the manifest does
        # not record, and every cleanup attempt is ownership-checked and
        # best-effort, never a completed rollback of on-disk state. Close
        # errors remain ambiguous (carried).
        try:
            renamed=False
            try:
                # Build the version in a private temp dir, then rename it into
                # place. After open, the attempt HOLDS that dir: the descriptor
                # pins its inode (a deleted-then-recreated replacement cannot
                # reuse it) and anchors both the exclusive writes and the
                # ownership check every destructive cleanup must pass - the
                # pathname must still denote the SAME (dev,ino), a real
                # directory, not a link; anything else is LEFT in place rather
                # than deleted by mistake. The mkdir-to-open acquisition gap
                # remains: a different real directory swapped in BEFORE open
                # can be adopted. After-open replacement checks narrow the
                # race, but do not atomically close check-to-rmtree (carried).
                # Once the rename lands, failure cleanup must remove the
                # RENAMED target - tmp no longer denotes anything, and the
                # held dirfd pins the same inode now living at target.
                tmp.mkdir(parents=True)
                dfd=_os.open(tmp,_os.O_RDONLY|_os.O_NOFOLLOW|_os.O_DIRECTORY)
                segments_blob=json.dumps([s.model_dump(mode='json') for s in segments],sort_keys=True).encode('utf-8')
                self._write_version_files(dfd,raw,segments_blob)
                # Durability ORDERING, not a general durability guarantee:
                # the file data is already fsynced; fsync the held dirfd so
                # the files' directory entries are durable before the rename
                # moves them, then fsync the parent dir after the rename so
                # the version's final name is durable BEFORE the manifest
                # can record it. A crash can still orphan a v*.tmp-* dir
                # (carried; no startup sweep), and fsync semantics depend on
                # the filesystem/mount (carried). fsync errors are OSErrors
                # and join the ordinary failure lifecycle below.
                _os.fsync(dfd)
                _os.rename(tmp,target)
                renamed=True
                parent_fd=_os.open(target.parent,_os.O_RDONLY|_os.O_NOFOLLOW|_os.O_DIRECTORY)
                try: _os.fsync(parent_fd)
                finally: _os.close(parent_fd)
            except OSError:
                # Post-rename the only object this attempt still owns on
                # disk is the renamed target; cleaning tmp would do nothing
                # and would leave a complete version dir no manifest
                # records. Pre-claim, no live manifest references these
                # bytes, so owned-target removal is truthful.
                self._cleanup_attempt(target if renamed else tmp,dfd)
                raise
            except BaseException:
                # Unexpected failure while the attempt holds its tmp dir and
                # BEFORE any memory version claim exists: attempt the same
                # ownership-checked cleanup (a replaced object is preserved,
                # never deleted) and propagate. Best-effort, not a completed
                # rollback; the cleanup wrapper can never mask the original
                # failure, so the exception reaching the caller is always
                # the one that actually failed.
                self._cleanup_attempt(target if renamed else tmp,dfd)
                raise
            # The memory claim and the manifest persist are guarded as ONE
            # region. Rollback removes exactly the OBJECTS this attempt
            # appended: each is deleted only while identity still matches at
            # its captured base, so an unrelated append interleaved in the
            # failure window is preserved and a base that no longer holds
            # our object is left untouched (no foreign deletes). These
            # bounds assume append-only interleaving within this process;
            # this is NOT a concurrency or multi-statement transaction
            # guarantee. A deletion that itself raises (exotic list
            # behavior) can still mask the original exception, and a failed
            # identity check can leave this attempt's claim in place - both
            # carried, not hidden.
            vbase=len(rec.versions); cbase=len(self.chunks); ebase=len(self.edges)
            edge={'from':request.source.source_id,'to':digest,'relation':'has_version','version':version.number}
            try:
                rec.versions.append(version); self.chunks.extend(new_chunks); self.edges.append(edge)
                self._persist_manifest(rec)
            except (OSError, ManifestOversizeError) as persist_exc:
                # Persist failed AFTER memory mutation: roll the version state
                # back so memory never claims a version the manifest does not
                # record. The durable registration (its own manifest was written
                # before any version file) is PRESERVED. The version dir is
                # removed only while the pathname still denotes the object this
                # attempt created (ownership check; the replace race is
                # narrowed, not atomically closed); a replaced object or a
                # failed removal leaves unresolved on-disk state with no new
                # memory version claim. An oversize refusal
                # happens before any manifest mutation, so the recorded
                # manifest bytes survive.
                self._rollback_claim(rec,version,new_chunks,edge,vbase,cbase,ebase)
                # Restore BEFORE delete: persist_exc may have escaped AFTER
                # os.replace (e.g. the post-replace directory fsync), so the
                # live manifest can already RECORD this version. The
                # version's bytes are removed only once the pre-claim
                # manifest is CONFIRMED rewritten; while the restore is
                # unconfirmed the bytes are LEFT in place - deleting bytes a
                # live manifest still references would strand a recorded
                # hash with no content behind it. The restore rewrite never
                # masks the original failure. This is still not a completed
                # rollback: an unconfirmed restore leaves the version dir
                # behind (carried), and a crash mid-sequence can leave
                # either artifact (carried).
                restore_ok=self._restore_manifest_confirmed(rec)
                if restore_ok: self._cleanup_attempt(target,dfd)
                if restore_ok and isinstance(persist_exc, ManifestOversizeError): raise persist_exc
                if restore_ok:
                    raise KnowledgeError('manifest persistence failed; version rolled back, registration preserved')
                raise KnowledgeError('manifest persistence failed and the pre-claim manifest could not be confirmed restored; the memory claim was removed but the on-disk manifest may still record the version, whose bytes were left in place')
            except BaseException as persist_exc:
                # Unexpected failure AFTER the memory version claim: roll the
                # claim back so memory stays truthful (no version the manifest
                # does not record), then restore-before-delete exactly as in
                # the OSError path: the renamed dir is removed only once the
                # pre-claim manifest is confirmed rewritten, because this
                # failure may also have escaped after os.replace. A replaced
                # object or an unconfirmed restore leaves the bytes in place.
                # Best-effort, not a completed rollback.
                self._rollback_claim(rec,version,new_chunks,edge,vbase,cbase,ebase)
                restore_ok=self._restore_manifest_confirmed(rec)
                if restore_ok: self._cleanup_attempt(target,dfd)
                else:
                    raise KnowledgeError('manifest persistence failed and the pre-claim manifest could not be confirmed restored; the memory claim was removed but the on-disk manifest may still record the version, whose bytes were left in place') from persist_exc
                raise
        finally:
            # Close errors of ANY type are swallowed: a close that fails
            # while another exception is in flight must never replace it,
            # and on success a close failure does not convert a recorded
            # version into a raised error. The close outcome itself stays
            # ambiguous (carried).
            if dfd is not None:
                try: _os.close(dfd)
                except BaseException: pass
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
    def _read_source_bytes(self,source_id:str,number:int,refusal:str)->bytes:
        # The filename is part of the containment check (symlinked source.bin
        # rejected). The bound is the largest ENCODED size of any accepted
        # ingest: text content is bounded at MAX_INGEST_CONTENT characters
        # (up to 4 UTF-8 bytes each), byte content at MAX_INGEST_CONTENT
        # bytes. A larger on-disk file is divergence.
        blob=self._contained(source_id,f'v{number}','source.bin')
        return self._read_bounded_file(blob,4*MAX_INGEST_CONTENT,refusal,
                                       f'on-disk source bytes for version {number}','exceed the ingest bound')

    @staticmethod
    def _read_bounded_file(blob:Path,limit:int,refusal:str,what:str,over:str)->bytes:
        # Bounded, swap-resistant read of a regular file. O_NOFOLLOW refuses
        # a symlink swapped in as the FINAL component between containment and
        # open, and O_NONBLOCK is requested on the open (scoped hardening
        # pinned by mock-driven flag capture; no universal device no-block
        # guarantee is claimed). The type contract is fstat on the OPENED
        # descriptor: the
        # file actually opened is what gets judged, so a stat-then-open swap
        # cannot launder a non-regular node through a stale stat verdict. At
        # most limit+1 bytes are ever pulled into memory, so growth after
        # any earlier stat cannot drive an unbounded allocation. Every OS
        # failure maps to the refusal contract, and the descriptor is closed
        # on every path, including a failing fdopen. Carried residuals,
        # explicitly NOT claimed: a swap of a PARENT component between
        # containment and open (TOCTOU), content drift after open (the
        # fd-stable read may differ from any earlier stat), and durability
        # or fsync guarantees for bytes on disk.
        import os as _os, stat as _stat
        try: fd=_os.open(blob,_os.O_RDONLY|_os.O_NOFOLLOW|_os.O_NONBLOCK)
        except OSError as exc: raise KnowledgeError(f'{refusal}: {what} unreadable') from exc
        try:
            try: mode=_os.fstat(fd).st_mode
            except OSError as exc: raise KnowledgeError(f'{refusal}: {what} unreadable') from exc
            if not _stat.S_ISREG(mode): raise KnowledgeError(f'{refusal}: {what} is not a regular file')
            try:
                with _os.fdopen(fd,'rb') as fh:
                    fd=None  # ownership moves to the file object
                    data=fh.read(limit+1)
            except OSError as exc: raise KnowledgeError(f'{refusal}: {what} unreadable') from exc
        finally:
            if fd is not None:
                try: _os.close(fd)
                except OSError: pass
        if len(data)>limit: raise KnowledgeError(f'{refusal}: {what} {over}')
        return data
    @staticmethod
    def _write_version_files(dfd:int,raw:bytes,segments_blob:bytes)->None:
        # Version files get the same exclusive-write contract as manifests:
        # O_EXCL|O_NOFOLLOW never writes through a preexisting link or file,
        # and the writes are anchored at the caller-held OPENED tmp dirfd
        # (opened O_RDONLY|O_NOFOLLOW|O_DIRECTORY by the caller, which
        # refuses a tmp swapped to a symlink after mkdir), so a swap cannot
        # redirect source.bin or segments.json outside the workspace, and a
        # link planted inside tmp between mkdir and write is refused. The
        # caller owns the descriptor's lifecycle; the held fd also pins the
        # created dir's inode for the ownership-checked cleanups. Carried,
        # NOT closed: a swap of a component above tmp, the rename-into-place
        # TOCTOU, and fsync/durability beyond rename.
        import os as _os
        for name,data in (('source.bin',raw),('segments.json',segments_blob)):
            fd=_os.open(name,_os.O_WRONLY|_os.O_CREAT|_os.O_EXCL|_os.O_NOFOLLOW,0o600,dir_fd=dfd)
            try:
                view=memoryview(data)
                while view:
                    written=_os.write(fd,view)
                    if written<=0: raise OSError(f'short write persisting {name}')
                    view=view[written:]
                # Data durability is ordered BEFORE the file's directory
                # entry is made durable (the caller fsyncs the holding dirfd
                # after these writes) and long before any manifest records
                # the version. An fsync failure is an OSError and joins the
                # ordinary failure lifecycle (ownership-checked cleanup,
                # original error propagates).
                _os.fsync(fd)
            finally:_os.close(fd)
    def _rollback_claim(self,rec,version,new_chunks,edge,vbase,cbase,ebase)->None:
        # Undo exactly THIS attempt's memory claim. The version and edge are
        # single objects, deleted only while identity still matches at the
        # captured base. Chunks are deleted as the contiguous PREFIX of
        # positions still holding this attempt's own objects: an extend that
        # raised partway (some of our chunks appended, none foreign) is
        # still rolled back, and foreign objects after the prefix are
        # preserved. The prefix stops at the first position that no longer
        # holds our object - any of our objects left beyond a mismatch are
        # NOT removed (carried: non-append-only interleaving can leave
        # non-contiguous own survivors). Correct for append-only
        # interleaving within this process; NOT a concurrency guarantee.
        # A deletion that itself raises propagates and can mask the
        # original failure (carried); a failed identity match can leave
        # this attempt's claim in place (carried).
        if len(rec.versions)>vbase and rec.versions[vbase] is version:
            del rec.versions[vbase]
        k=0
        while k<len(new_chunks) and len(self.chunks)>cbase+k and self.chunks[cbase+k] is new_chunks[k]:
            k+=1
        if k:
            del self.chunks[cbase:cbase+k]
        if len(self.edges)>ebase and self.edges[ebase] is edge:
            del self.edges[ebase]
    def _cleanup_attempt(self,path,dfd)->None:
        # Best-effort wrapper around the ownership-checked cleanup: cleanup
        # runs during failure handling, so it must NEVER replace the failure
        # it serves. Any error from the cleanup itself - OSError or an
        # unexpected exception - is swallowed, leaving the original
        # exception to reach the caller unchanged. The cleanup stays
        # ownership-checked and best-effort, never a completed rollback.
        try: self._rmtree_if_owned(path,dfd)
        except BaseException: pass
    @staticmethod
    def _rmtree_if_owned(path:Path,dfd)->None:
        # Destructive cleanup only while the pathname still denotes the
        # attempt's OWN object: fstat on the HELD dirfd (which pins the
        # created dir's inode against delete-then-recreate reuse) must
        # match lstat of the path on (dev,ino), and the path must be a
        # real directory - a symlink or a replaced object is LEFT in place.
        # This matches the held descriptor, not proof of mkdir authorship:
        # the mkdir-to-open acquisition gap remains. Errors from stat
        # checks leave the path untouched; the check
        # narrows but does not atomically close the replace race (carried).
        import os as _os, stat as _stat
        if dfd is None: return
        try: want=_os.fstat(dfd)
        except OSError: return
        try: st=_os.lstat(path)
        except OSError: return
        if not _stat.S_ISDIR(st.st_mode): return
        if (st.st_dev,st.st_ino)!=(want.st_dev,want.st_ino): return
        shutil.rmtree(path,ignore_errors=True)
    def _restore_manifest_confirmed(self,rec:Record)->bool:
        # A normal persist return is not confirmation. Read through the same
        # bounded regular-file reader and require the exact expected claims.
        # This is a point-in-time check, not a concurrent-writer transaction
        # or crash recovery guarantee. Failure keeps potentially referenced bytes.
        expected=[{'number':v.number,'hash':v.content_hash} for v in rec.versions]
        try:
            self._persist_manifest(rec)
            raw=self._read_bounded_file(
                self._contained(rec.source.source_id,'manifest.json'),
                self.MANIFEST_MAX_BYTES,'restore confirmation failed',
                'on-disk manifest','exceeds the manifest bound')
            restored=json.loads(raw.decode('utf-8'))
            return isinstance(restored,dict) and restored.get('versions')==expected
        except BaseException:
            return False

    def _persist_manifest(self,rec:Record):
        p=self._contained(rec.source.source_id); p.mkdir(parents=True,exist_ok=True)
        import os as _os, uuid as _uuid
        tmp=p/f'manifest.json.tmp-{_uuid.uuid4().hex}'
        # O_EXCL|O_NOFOLLOW: never write through a preexisting link or file,
        # uuid or not; a collision fails instead of truncating anything.
        blob=json.dumps({'tenant_id':self.tenant_id,'source':rec.source.model_dump(mode='json'),'versions':[{'number':v.number,'hash':v.content_hash} for v in rec.versions]},sort_keys=True).encode('utf-8')
        # Write/read contract: the writer is bound by the same
        # MANIFEST_MAX_BYTES the bounded reader enforces, so this pipeline
        # never persists a manifest it would later refuse. The check runs
        # BEFORE any mutation - no tmp file, no replace - so a refused write
        # preserves the prior manifest bytes exactly. Unbounded metadata or
        # version growth fails closed here instead of writing state the
        # reader must reject. Durability is ordered: the manifest bytes are
        # fsynced before close, os.replace renames them into place, and the
        # holding directory is fsynced after the replace so the manifest
        # name is durable before this call returns. Still NOT claimed:
        # durability under filesystems/mounts with weak fsync semantics, or
        # any guarantee for state written by a call that FAILS partway
        # (carried).
        if len(blob)>self.MANIFEST_MAX_BYTES:
            raise ManifestOversizeError(f'refusing to persist manifest: serialized manifest would exceed the manifest bound ({len(blob)} bytes)')
        fd=_os.open(tmp,_os.O_WRONLY|_os.O_CREAT|_os.O_EXCL|_os.O_NOFOLLOW,0o600)
        try:
            view=memoryview(blob)
            while view:
                written=_os.write(fd,view)
                if written<=0: raise OSError('short write persisting manifest')
                view=view[written:]
            _os.fsync(fd)
        finally:_os.close(fd)
        _os.replace(tmp,p/'manifest.json')
        dir_fd=_os.open(p,_os.O_RDONLY|_os.O_NOFOLLOW|_os.O_DIRECTORY)
        try: _os.fsync(dir_fd)
        finally: _os.close(dir_fd)
