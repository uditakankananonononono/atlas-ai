"""Owner-pinned authenticated collector workflow; explicit admin provisioning."""
from contextlib import contextmanager
from pathlib import Path
from threading import RLock,Lock
import hashlib,json,os,re,sqlite3,time
from .dispatch_intent import DispatchIntentWAL,IntentBoundHostRateLimiter
from .durable_rate_limiter import DurableHostRateLimiter
from .lane_rate_limit_state import StateRejected
from .lane_models import FetchPolicy
from .lane_http import UrllibHttpClient,HttpError
from .lane_sources import BaseCollector
from .lane_repository import SQLiteDocumentRepository,_SCHEMA
from .lane_pipeline import CollectionPipeline
from .lane_validation import DocumentValidator
from .lane_ranking import BlueprintRanker
from .lane_freshness import FreshnessMonitor
from .wiring import build_collectors,build_refetcher
from .service import Service

UNAVAILABLE='collector service unavailable'
PROFILE='m18-owner-wal-public-http-v1'
class FactoryUnavailable(RuntimeError):pass
class OwnerMismatch(RuntimeError):pass

def root_path(value):
    try:
        if not value:raise ValueError()
        p=Path(value)
        if not p.is_absolute() or any(x.is_symlink() for x in [p,*p.parents]):raise ValueError()
        p=p.resolve(strict=True)
        if not p.is_dir() or p.stat().st_mode & 0o077 or any(p==b or b in p.parents for b in map(Path,('/tmp','/var/tmp','/dev/shm','/run'))):raise ValueError()
        return p
    except (ValueError,OSError):raise FactoryUnavailable(UNAVAILABLE) from None

def paths(root,tenant):
    if type(tenant) is not str or not 1<=len(tenant)<=120:raise FactoryUnavailable(UNAVAILABLE)
    key=hashlib.sha256(tenant.encode()).hexdigest()
    return root/('m18-owner-'+key+'.json'),root/('m18-workspace-'+key)

def read_registry(path):
    import stat
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError()
            raw=f.read(4097)
        if len(raw)>4096:raise ValueError()
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d:raise ValueError()
                d[k]=v
            return d
        return json.loads(raw,object_pairs_hook=unique)
    except Exception:raise FactoryUnavailable(UNAVAILABLE) from None

def provision(root,tenant,actor,*,known_new=False):
    root=root_path(root);registry,work=paths(root,tenant)
    if known_new is not True or type(actor) is not str or not 1<=len(actor)<=120 or os.path.lexists(registry) or os.path.lexists(work):raise FactoryUnavailable(UNAVAILABLE)
    work.mkdir(mode=0o700) # Crash residue deliberately not auto-adopted.
    DispatchIntentWAL(work,tenant).provision()
    DurableHostRateLimiter(work,tenant,bootstrap=True)
    db=sqlite3.connect(work/'documents.sqlite3');db.executescript(_SCHEMA);db.close()
    (work/'documents.sqlite3').chmod(0o600)
    fd=os.open(registry,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(json.dumps({'version':1,'tenant':tenant,'actor':actor,'profile':PROFILE},sort_keys=True).encode());f.flush();os.fsync(f.fileno())
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class GatedHttp:
    """Robots-only transport through the SAME limiter as page/API requests."""
    def __init__(self,http,limiter,sleeper):self.http=http;self.limiter=limiter;self.sleeper=sleeper
    def fetch(self,url,*,policy,headers=None,etag=None,last_modified=None):
        from dataclasses import replace
        policy=replace(policy,max_redirects=0)
        c=BaseCollector(self.http,policy=policy,limiter=self.limiter,sleeper=self.sleeper)
        response,error=c._get(url,headers=headers,etag=etag,last_modified=last_modified)
        if error:raise HttpError(url,None,'dispatch_state_unavailable')
        return response

class CollectorServiceFactory:
    def __init__(self,root,*,http=None,generate=None,sleeper=time.sleep,clock=None):
        self.root=root_path(root);self.http=http or UrllibHttpClient();self.sleeper=sleeper;self.clock=clock
        if generate is None:
            from app.core.providers import generate
        self.generate=generate;self._lock=RLock();self._services={};self._locks={};self._database_identity={}

    def _validate(self,tenant,actor):
        root_path(str(self.root));registry,work=paths(self.root,tenant);data=read_registry(registry)
        if type(data) is not dict or set(data)!={'version','tenant','actor','profile'} or type(data['version']) is not int or data['version']!=1 or data['tenant']!=tenant or data['profile']!=PROFILE or type(data['actor']) is not str:raise FactoryUnavailable(UNAVAILABLE)
        if data['actor']!=actor:raise OwnerMismatch('collector owner access required')
        try:
            if work.is_symlink() or not work.is_dir() or work.stat().st_mode & 0o077:raise ValueError()
            path=work/'documents.sqlite3'
            if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:raise ValueError()
            with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError()
                actual={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {'documents','events','freshness_state'}<=actual:raise ValueError()
                required={'documents':{'tenant_id','doc_id','content_hash','title','text'},'events':{'tenant_id','kind','payload'},'freshness_state':{'tenant_id','url','kind','status'}}
                for table,columns in required.items():
                    if not columns<={r[1] for r in db.execute('PRAGMA table_info('+table+')')}:raise ValueError()
            identity=(path.stat().st_dev,path.stat().st_ino)
            if tenant in self._database_identity and self._database_identity[tenant]!=identity:raise ValueError()
            if DispatchIntentWAL(work,tenant).read()['pending'] is not None:raise ValueError()
        except Exception:raise FactoryUnavailable(UNAVAILABLE) from None
        return work

    @contextmanager
    def service(self,tenant,actor):
        with self._lock:
            work=self._validate(tenant,actor);lock=self._locks.setdefault(tenant,Lock())
        with lock:
            work=self._validate(tenant,actor)
            try:
                with self._lock:
                    if tenant not in self._services:
                        kwargs={'clock':self.clock} if self.clock else {}
                        limiter=IntentBoundHostRateLimiter(work,tenant,policy=FetchPolicy(),**kwargs)
                        repository=SQLiteDocumentRepository(str(work/'documents.sqlite3'))
                        collectors=build_collectors(http=self.http,limiter=limiter,sleeper=self.sleeper,robots_http=GatedHttp(self.http,limiter,self.sleeper),policy=FetchPolicy(max_redirects=0))
                        pipeline=CollectionPipeline(repository=repository,validator=DocumentValidator(),ranker=BlueprintRanker(),monitor=FreshnessMonitor(repository),collectors=collectors)
                        service=Service(generate=self.generate,collectors=collectors,pipeline=pipeline,tenant_id=tenant)
                        service._bound_refetcher=build_refetcher(http=self.http,limiter=limiter,sleeper=self.sleeper)
                        service._bound_limiter=limiter
                        path=work/'documents.sqlite3'
                        self._database_identity[tenant]=(path.stat().st_dev,path.stat().st_ino)
                        self._services[tenant]=service
                    service=self._services[tenant];service._bound_limiter._guard()
                yield service
            except StateRejected:raise FactoryUnavailable(UNAVAILABLE) from None
