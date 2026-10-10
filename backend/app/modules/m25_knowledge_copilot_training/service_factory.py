"""Single-process, explicit-root, owner-pinned offline knowledge factory."""
from contextlib import contextmanager
import hashlib,json,os,re
from pathlib import Path
from threading import RLock,Lock
from .pipeline import LocalKnowledgePipeline,DeterministicEmbedder,UnavailableTranscriber,KnowledgeError
PROFILE='deterministic-embedder-v1+unavailable-transcriber-v1'
UNAVAILABLE='knowledge service unavailable'
class ServiceUnavailable(KnowledgeError):pass
class OwnerMismatch(KnowledgeError):pass

def _segment(value):
    if type(value) is not str or not 1<=len(value)<=120 or value in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',value):raise ServiceUnavailable(UNAVAILABLE)
    return value

def _root(value,allow_test_scratch):
    if not value:raise ServiceUnavailable(UNAVAILABLE)
    p=Path(value)
    try:
        if not p.is_absolute() or any(x.is_symlink() for x in (p,*p.parents)):raise ServiceUnavailable(UNAVAILABLE)
        p=p.resolve(strict=True)
        if any(x.is_symlink() for x in (p,*p.parents)) or not p.is_dir() or p.stat().st_mode & 0o077:raise ServiceUnavailable(UNAVAILABLE)
    except OSError:raise ServiceUnavailable(UNAVAILABLE) from None
    if not allow_test_scratch and any(p==base or base in p.parents for base in map(Path,('/tmp','/var/tmp','/dev/shm','/run'))):raise ServiceUnavailable(UNAVAILABLE)
    return p

def _registry(root,tenant):return root/('.m25-owner-'+hashlib.sha256(tenant.encode()).hexdigest()+'.json')

def provision(root,tenant_id,owner_actor,*,known_new=False,profile=PROFILE,allow_test_scratch=False):
    """Administrative known-new decision only. Crash residue is never auto-reset."""
    root=_root(root,allow_test_scratch);tenant=_segment(tenant_id)
    if known_new is not True or type(owner_actor) is not str or not 1<=len(owner_actor)<=120 or profile!=PROFILE:raise ServiceUnavailable(UNAVAILABLE)
    registry=_registry(root,tenant);workspace=root/tenant
    if os.path.lexists(registry) or os.path.lexists(workspace):raise ServiceUnavailable(UNAVAILABLE)
    workspace.mkdir(mode=0o700)
    data=json.dumps({'version':1,'tenant_id':tenant,'owner_actor':owner_actor,'profile':profile},sort_keys=True).encode()
    fd=os.open(registry,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

class KnowledgeServiceFactory:
    def __init__(self,root,*,allow_test_scratch=False):
        self.root=_root(root,allow_test_scratch);self._lock=RLock();self._services={};self._locks={}
    def _owner(self,tenant):
        try:
            def unique(pairs):
                out={}
                for k,v in pairs:
                    if k in out:raise ValueError()
                    out[k]=v
                return out
            raw=LocalKnowledgePipeline._read_bounded_file(_registry(self.root,tenant),4096,UNAVAILABLE,'registry','exceeds bound')
            data=json.loads(raw,object_pairs_hook=unique)
            if type(data) is not dict or set(data)!={'version','tenant_id','owner_actor','profile'}:raise ValueError()
            if type(data['version']) is not int or data['version']!=1 or data['tenant_id']!=tenant or data['profile']!=PROFILE:raise ValueError()
            if type(data['owner_actor']) is not str or not 1<=len(data['owner_actor'])<=120:raise ValueError()
            workspace=self.root/tenant
            if workspace.is_symlink() or not workspace.is_dir() or workspace.stat().st_mode & 0o077:raise ValueError()
            return data['owner_actor']
        except (KnowledgeError,OSError,ValueError,TypeError,RecursionError):raise ServiceUnavailable(UNAVAILABLE) from None
    @contextmanager
    def service(self,tenant_id,actor_id):
        tenant=_segment(tenant_id)
        with self._lock:
            owner=self._owner(tenant)
            if actor_id!=owner:raise OwnerMismatch('knowledge owner access required')
            lock=self._locks.setdefault(tenant,Lock())
        with lock:
            try:
                with self._lock:
                    service=self._services.get(tenant)
                    if service is None:
                        service=LocalKnowledgePipeline(self.root,tenant,owner,embedder=DeterministicEmbedder(),transcriber=UnavailableTranscriber())
                        service.restore_verified(same_adapters_attested=True)
                        self._services[tenant]=service
                for record in service.records.values():service._check_consent(record.source)
            except (KnowledgeError,OSError,ValueError):raise ServiceUnavailable(UNAVAILABLE) from None
            yield service
