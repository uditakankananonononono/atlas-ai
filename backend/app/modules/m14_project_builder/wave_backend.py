"""M14 one-process Bubblewrap: fixed writable files, no tmp writes, seccomp fork deny."""
import ctypes,ctypes.util,errno,os,resource,shutil,signal,subprocess,tempfile,time
from pathlib import Path
from app.modules.m04_research_scientist.approved_sandbox import BubblewrapBackend,SandboxRun,BackendUnavailableError,_now,_read_capped

class WaveBubblewrapBackend(BubblewrapBackend):
    name='bubblewrap-single-process-fixed-output-v1'
    def command(self,language,input_dir,output_dir):
        args=super().command(language,input_dir,output_dir)
        pos=args.index('--tmpfs');args[pos:pos+2]=['--ro-bind',str(input_dir/'empty-tmp'),'/tmp']
        pos=args.index('--bind');args[pos:pos+3]=['--ro-bind',str(output_dir),'/output']
        for path in sorted(output_dir.iterdir()):
            args[-4:-4]=['--bind',str(path),'/output/'+path.name]
        args[-4:-4]=['--remount-ro','/','--remount-ro','/dev']
        return args

    def _filter(self,handle):
        lib=ctypes.CDLL(ctypes.util.find_library('seccomp') or 'libseccomp.so.2')
        lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
        lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
        lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
        lib.seccomp_export_bpf.argtypes=[ctypes.c_void_p,ctypes.c_int]
        lib.seccomp_release.argtypes=[ctypes.c_void_p]
        ctx=lib.seccomp_init(0x7fff0000) # SCMP_ACT_ALLOW
        if not ctx:raise BackendUnavailableError('seccomp init unavailable')
        try:
            for name in ('clone','clone3','fork','vfork','unshare','setns','mount','umount2','ptrace'):
                syscall=lib.seccomp_syscall_resolve_name(name.encode())
                if syscall<0 or lib.seccomp_rule_add(ctx,0x00050000|errno.EPERM,syscall,0)!=0:raise BackendUnavailableError('seccomp deny unavailable')
            if lib.seccomp_export_bpf(ctx,handle.fileno())!=0:raise BackendUnavailableError('seccomp export unavailable')
            handle.seek(0)
        finally:lib.seccomp_release(ctx)

    def run(self,*,language,input_dir,output_dir,limits):
        if not self.available(language):raise BackendUnavailableError('Bubblewrap unavailable')
        (input_dir/'empty-tmp').mkdir(exist_ok=True)
        paths=list(output_dir.iterdir())
        if len(paths)>20 or any(not x.is_file() or x.is_symlink() for x in paths):raise BackendUnavailableError('fixed output slots invalid')
        logs=Path(tempfile.mkdtemp(prefix='wave-logs-'));started=_now();t0=time.monotonic()
        def preexec():
            resource.setrlimit(resource.RLIMIT_AS,(limits.memory_mb*1048576,)*2)
            resource.setrlimit(resource.RLIMIT_CPU,(limits.timeout_seconds,)*2)
            resource.setrlimit(resource.RLIMIT_FSIZE,(50000,)*2) # 20 fixed files <=1MB, each log <=50k
            resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
        try:
            with tempfile.TemporaryFile() as bpf,(logs/'stdout').open('wb') as out,(logs/'stderr').open('wb') as err:
                self._filter(bpf)
                args=self.command(language,input_dir,output_dir)
                args[1:1]=['--seccomp',str(bpf.fileno())]
                proc=subprocess.Popen(args,stdout=out,stderr=err,stdin=subprocess.DEVNULL,start_new_session=True,close_fds=True,pass_fds=(bpf.fileno(),),preexec_fn=preexec)
                timed_out=False
                try:code=proc.wait(timeout=limits.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out=True
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait();code=None
            stdout,stdout_cut=_read_capped(logs/'stdout',limits.max_log_bytes);stderr,stderr_cut=_read_capped(logs/'stderr',limits.max_log_bytes)
        finally:shutil.rmtree(logs,ignore_errors=True)
        return SandboxRun(self.name,{'network':'none','filesystem':'readonly system/input/tmp/output-dir; predeclared files writable','processes':'fork/clone/vfork denied by seccomp','rlimits':{'memory_mb':limits.memory_mb,'file_bytes':50000,'open_fds':64},'output':'<=20 predeclared files <=1MB aggregate'},code,timed_out,stdout,stderr,stdout_cut,stderr_cut,started,_now(),round(time.monotonic()-t0,3))
