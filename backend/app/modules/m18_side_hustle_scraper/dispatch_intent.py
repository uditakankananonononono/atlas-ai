"""Single-writer opt-in dispatch-intent WAL. No automatic replay/reconciliation.

Trusted private POSIX root, exactly one live writer; checksum not authenticity.
No remote lease, exactly-once, hostile rollback protection or RetryAfter WAL.
"""
from datetime import timezone
import hashlib,json,os,stat,tempfile,uuid
from pathlib import Path
from threading import RLock
from .durable_rate_limiter import DurableHostRateLimiter
from .lane_rate_limit_state import StateRejected

MAX_BYTES=16384

class DispatchIntentWAL:
    def __init__(self,root:Path,tenant_id:str):
        root=Path(root).absolute()
        if not isinstance(tenant_id,str) or not tenant_id or len(tenant_id)>256:raise StateRejected('trusted tenant required')
        if not root.is_dir() or any(p.is_symlink() for p in [root,*root.parents]):raise StateRejected('trusted private root required')
        self.tenant=hashlib.sha256(tenant_id.encode()).hexdigest()
        self.path=root/('m18-intent-'+self.tenant+'.json')
        self._lock=RLock()

    @staticmethod
    def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

    def _validate(self,state):
        if type(state) is not dict or set(state)!={'version','tenant','revision','pending'}:raise StateRejected('invalid intent state')
        if type(state['version']) is not int or state['version']!=1 or state['tenant']!=self.tenant:raise StateRejected('intent version or tenant mismatch')
        if type(state['revision']) is not int or not 0<=state['revision']<2**63:raise StateRejected('invalid intent revision')
        p=state['pending']
        if p is not None:
            if type(p) is not dict or set(p)!={'id','host','requested_at'}:raise StateRejected('invalid pending intent')
            if type(p['id']) is not str or len(p['id'])!=32 or any(x not in '0123456789abcdef' for x in p['id']):raise StateRejected('invalid intent id')
            if type(p['host']) is not str or not 1<=len(p['host'])<=253:raise StateRejected('invalid host')
            from datetime import datetime
            try:
                if type(p['requested_at']) is not str:raise ValueError()
                stamp=datetime.fromisoformat(p['requested_at'])
                if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.astimezone(timezone.utc).isoformat()!=p['requested_at']:raise ValueError()
            except (ValueError,OverflowError):raise StateRejected('invalid intent timestamp') from None
        return state

    def read(self):
        with self._lock:
            try:
                fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise StateRejected('intent not regular file')
                    raw=stream.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:raise StateRejected('intent exceeds bound')
                def unique(pairs):
                    out={}
                    for key,value in pairs:
                        if key in out:raise ValueError()
                        out[key]=value
                    return out
                envelope=json.loads(raw,object_pairs_hook=unique)
                if type(envelope) is not dict or set(envelope)!={'state','sha256'}:raise StateRejected('invalid intent envelope')
                state=self._validate(envelope['state'])
                if envelope['sha256']!=hashlib.sha256(self._canonical(state)).hexdigest():raise StateRejected('intent checksum mismatch')
                return state
            except (OSError,ValueError,TypeError,RecursionError):raise StateRejected('intent read refused') from None

    def _write(self,state):
        self._validate(state)
        raw=self._canonical({'state':state,'sha256':hashlib.sha256(self._canonical(state)).hexdigest()})
        if len(raw)>MAX_BYTES:raise StateRejected('intent exceeds bound')
        temporary=None
        try:
            fd,temporary=tempfile.mkstemp(prefix='.m18-intent-',dir=self.path.parent)
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path);temporary=None
            fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
            if self.read()!=state:raise StateRejected('intent readback mismatch')
        except OSError:raise StateRejected('intent commit unverified; inspect before retry') from None
        finally:
            if temporary is not None:
                try:os.unlink(temporary)
                except OSError:pass

    def provision(self):
        with self._lock:
            if os.path.lexists(self.path):raise StateRejected('intent state exists')
            self._write({'version':1,'tenant':self.tenant,'revision':0,'pending':None})

    def begin(self,host,requested_at):
        with self._lock:
            state=self.read()
            if state['pending'] is not None:raise StateRejected('pending intent; operator inspection required')
            from datetime import datetime
            if not isinstance(requested_at,datetime) or requested_at.tzinfo is None or requested_at.utcoffset() is None:raise StateRejected('aware request time required')
            intent={'id':uuid.uuid4().hex,'host':host,'requested_at':requested_at.astimezone(timezone.utc).isoformat()}
            state['pending']=intent;state['revision']+=1
            self._write(state)
            return intent.copy()

    def _complete(self,intent):
        with self._lock:
            state=self.read()
            if state['pending']!=intent:raise StateRejected('exact pending intent required')
            state['pending']=None;state['revision']+=1;self._write(state)

    def acknowledge_inspected(self,intent,*,operator_inspected=False):
        """Trusted caller acknowledgment, not authenticated human-role enforcement.

        Never retries a fetch or reconstructs permission for a pending intent.
        Operator must inspect snapshot/effects independently before using it.
        """
        if operator_inspected is not True:raise StateRejected('explicit operator inspection required')
        self._complete(intent)

class IntentBoundHostRateLimiter(DurableHostRateLimiter):
    """Explicit paired WAL+snapshot provisioning; no legacy collector wiring."""
    def __init__(self,private_root,tenant_id,**kwargs):
        if 'bootstrap' in kwargs:raise StateRejected('preprovision both stores; bootstrap kwarg refused')
        self.intent_wal=DispatchIntentWAL(private_root,tenant_id)
        # Both stores must be explicitly provisioned separately for known-new tenant.
        self.intent_wal.read()
        self._dispatch_failed=False
        super().__init__(private_root,tenant_id,**kwargs)

    def _guard(self):
        if self._dispatch_failed:raise StateRejected('dispatch persistence failed; operator inspection required')
        if self.intent_wal.read()['pending'] is not None:raise StateRejected('pending intent; operator inspection required')
        super()._guard()

    def begin_request(self,host):
        with self._lock:
            self._guard()
            # Use parent check, not overridden guard once the intent is pending.
            from .lane_rate_limit import HostRateLimiter
            wait=HostRateLimiter.check(self,host)
            if wait>0:return wait
            try:
                intent=self.intent_wal.begin(host,self._clock())
                HostRateLimiter.record_request(self,host)
                self._save() # request timestamp readback BEFORE permission
                self.intent_wal._complete(intent) # failure leaves pending or denied current instance
                return 0.0
            except Exception:
                self._dispatch_failed=True
                raise

    def record_request(self,host):
        raise StateRejected('use begin_request for dispatch-intent ordering')
