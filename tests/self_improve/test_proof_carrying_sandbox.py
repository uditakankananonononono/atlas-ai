"""Sandboxed proof-carrying checker (direction 6). Fixtures are authored here. Tests that need bwrap skip loudly
with a reason when this host cannot start it; the fail-closed tests run everywhere."""
import os
import sys
import time

import pytest

from app.self_improve import proof_carrying as pc
from app.self_improve.proof_carrying import (
    Conclusion, Limits, Verdict, check_analysis, check_code_change, check_factorization, check_sourced_quote,
    run_sandboxed, sha, verify)

def _host_can_bwrap():
    """Independent of the module under test, so a broken sandbox cannot make its own tests skip."""
    import shutil, subprocess
    b = shutil.which("bwrap")
    if not b:
        return False
    try:
        return subprocess.run([b, "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--", "/usr/bin/true"],
                              capture_output=True, timeout=20).returncode == 0
    except Exception:
        return False


needs_sandbox = pytest.mark.skipif(not _host_can_bwrap(), reason="bwrap cannot start on this host")
SRC = "def add(a, b):\n    return a + b\n"
T1 = "from mod import add\ndef test_a():\n    assert add(1, 2) == 3\n"
FAST = Limits(wall_s=6.0, cpu_s=3)


def cc(src=SRC, tests=T1, n=1, **kw):
    return Conclusion("c", "code_change", dict(source=src, tests=tests, expected_passed=n), **kw)


def an(script, out, **kw):
    return Conclusion("a", "analysis", dict(script=script, output_sha256=sha(out)), **kw)


# ---------------------------------------------------------------- pure kinds (no sandbox needed)
def test_factorization_accept_and_tamper():
    ok = lambda n, f: verify(Conclusion("x", "factorization", dict(n=n, factors=f))).status
    assert ok(91, [7, 13]) == "VERIFIED"
    assert ok(91, [7, 11]) == "UNVERIFIED"
    assert ok(91, [1, 91]) == "UNVERIFIED"
    assert ok(91, []) == "UNVERIFIED"
    assert ok(91, 7) == "UNVERIFIED"
    assert ok(True, [True]) == "UNVERIFIED"                 # bool is an int subclass
    assert ok(91.0, [7, 13]) == "UNVERIFIED"
    assert ok(2 ** 5000, [2, 2 ** 4999]) == "UNVERIFIED"    # size cap
    assert ok(2 ** 65, [2] * 65) == "UNVERIFIED"            # factor-count cap (MAX_FACTORS = 64)
    assert ok(2 ** 64, [2] * 64) == "VERIFIED"              # exactly at the cap is accepted


def test_sourced_quote_accept_and_tamper():
    txt = "Mutation testing injects faults and checks whether tests fail."
    ev = dict(source_text=txt, source_sha256=sha(txt.encode()), quote="injects faults")
    st = lambda **k: verify(Conclusion("q", "sourced_quote", dict(ev, **k))).status
    assert st() == "VERIFIED"
    assert st(quote="guarantees correctness") == "UNVERIFIED"
    assert st(source_sha256="0" * 64) == "UNVERIFIED"
    assert st(source_sha256=sha(txt.encode()).upper()) == "UNVERIFIED"
    assert st(quote="   ") == "UNVERIFIED"
    assert st(quote="") == "UNVERIFIED"
    assert st(quote=None) == "UNVERIFIED"
    assert st(source_text=txt + "x") == "UNVERIFIED"         # text changed, hash did not
    big = "a" * (pc.MAX_TEXT + 1)
    assert verify(Conclusion("q", "sourced_quote", dict(source_text=big, source_sha256=sha(big.encode()), quote="a"))).status == "UNVERIFIED"


def test_confidence_never_changes_status_and_is_reported_separately():
    bad = verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 11]), confidence=0.999))
    good = verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13]), confidence=0.0))
    assert (bad.status, bad.confidence) == ("UNVERIFIED", 0.999)
    assert (good.status, good.confidence) == ("VERIFIED", 0.0)
    nan = verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13]), confidence=float("nan")))
    assert nan.status == "VERIFIED" and nan.confidence is None
    assert verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13]), confidence=True)).confidence is None


def test_kind_without_checker_is_impossible_and_malformed_is_unverified():
    r = verify(Conclusion("wise", "opinion", {}, confidence=0.9))
    assert r.status == "VERIFICATION_IMPOSSIBLE" and "no checker" in r.reason and r.confidence == 0.9
    assert verify("not a conclusion").status == "UNVERIFIED"
    assert verify(Conclusion("x", ["factorization"], {})).status == "UNVERIFIED"
    assert verify(Conclusion("x", "factorization", "nope")).status == "UNVERIFIED"
    assert verify(Conclusion("x", "__import__", {})).status == "VERIFICATION_IMPOSSIBLE"


def test_verdict_dict_access_matches_pcc_keys():
    v = verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13])))
    assert isinstance(v, Verdict) and (v["status"], v["reason"]) == ("VERIFIED", "product of factors equals n")


def test_a_crashing_checker_is_not_a_pass(monkeypatch):
    monkeypatch.setitem(pc.CHECKERS, "factorization", lambda ev, lim: 1 / 0)
    r = verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13])))
    assert r.status == "UNVERIFIED" and "ZeroDivisionError" in r.reason


def test_truthy_but_not_true_checker_result_is_not_a_pass(monkeypatch):
    monkeypatch.setitem(pc.CHECKERS, "factorization", lambda ev, lim: ("yes", "x"))
    assert verify(Conclusion("x", "factorization", {})).status == "UNVERIFIED"


# ---------------------------------------------------------------- fail closed
def _reset_probe():
    pc._PROBE.clear()


@pytest.fixture
def no_bwrap(monkeypatch):
    _reset_probe()
    monkeypatch.setattr(pc, "bwrap_path", lambda: None)
    ran = []
    real = pc.run_sandboxed
    monkeypatch.setattr(pc, "run_sandboxed", lambda *a, **k: ran.append(a) or real(*a, **k))
    yield ran
    _reset_probe()


def test_no_bwrap_binary_fails_closed_and_never_runs_evidence(no_bwrap):
    for c in (an("print(1)", b"1\n"), cc()):
        r = verify(c)
        assert r.status == "UNVERIFIED" and r.reason.startswith("SANDBOX_UNAVAILABLE") and r.sandbox is None
    assert no_bwrap == []                                  # the evidence code was never launched
    assert verify(Conclusion("x", "factorization", dict(n=91, factors=[7, 13]))).status == "VERIFIED"


def test_bwrap_present_but_cannot_start_user_namespaces_fails_closed(monkeypatch, tmp_path):
    """Host without user namespaces: bwrap exists, exits non-zero at start. Simulated with a stub that fails like it."""
    stub = tmp_path / "bwrap"
    stub.write_text("#!/bin/sh\necho 'bwrap: No permissions to create new namespace' >&2\nexit 1\n")
    stub.chmod(0o755)
    marker = tmp_path / "ran"
    _reset_probe()
    monkeypatch.setattr(pc, "bwrap_path", lambda: str(stub))
    assert pc.sandbox_ok(refresh=True) is False
    r = verify(an(f"open({str(marker)!r}, 'w').write('x')\nprint(1)", b"1\n"))
    assert r.status == "UNVERIFIED" and r.reason.startswith("SANDBOX_UNAVAILABLE")
    assert not marker.exists()
    _reset_probe()


def test_run_sandboxed_raises_when_bwrap_missing(monkeypatch):
    monkeypatch.setattr(pc, "bwrap_path", lambda: None)
    with pytest.raises(pc.SandboxUnavailable):
        run_sandboxed(["/usr/bin/true"], {})
    _reset_probe()


def test_run_sandboxed_rejects_path_like_file_names():
    for bad in ("../x", "a/b", ".hidden"):
        with pytest.raises(ValueError):
            run_sandboxed(["/usr/bin/true"], {bad: "x"})


def test_sandbox_probe_is_cached_and_refreshable(monkeypatch):
    _reset_probe()
    calls = []
    monkeypatch.setattr(pc, "bwrap_path", lambda: None)
    assert pc.sandbox_ok() is False
    monkeypatch.undo()
    assert pc.sandbox_ok() is False                        # cached
    assert pc.sandbox_ok(refresh=True) == pc.sandbox_ok(refresh=True)
    _reset_probe()


# ---------------------------------------------------------------- code_change (ported from pcc + hardened)
@needs_sandbox
def test_code_change_needs_real_pass():
    assert verify(cc()).status == "VERIFIED"
    assert verify(cc()).sandbox == "bwrap"
    assert verify(cc(src="def add(a, b):\n    return a - b\n")).status == "UNVERIFIED"
    assert verify(cc(tests="def test_x():\n    pass\n", n=3)).status == "UNVERIFIED"


@needs_sandbox
def test_code_change_exact_count_skip_zero_tests_and_bad_inputs():
    eleven = "from mod import add\n" + "".join(f"def test_{i}():\n    assert add(1, 2) == 3\n" for i in range(11))
    assert verify(cc(tests=eleven, n=11)).status == "VERIFIED"
    assert verify(cc(tests=eleven, n=1)).status == "UNVERIFIED"
    skipped = "import pytest\nfrom mod import add\ndef test_a():\n    assert add(1, 2) == 3\n@pytest.mark.skip\ndef test_b():\n    assert False\n"
    assert verify(cc(tests=skipped, n=1)).status == "UNVERIFIED"
    xfail = "import pytest\nfrom mod import add\ndef test_a():\n    assert add(1, 2) == 3\n@pytest.mark.xfail\ndef test_b():\n    assert False\n"
    assert verify(cc(tests=xfail, n=1)).status == "UNVERIFIED"
    z = verify(cc(tests="def helper():\n    pass\n", n=1))
    assert z.status == "UNVERIFIED" and "exit 5" in z.reason
    for n in (0, -1, True, "1", None):
        assert verify(cc(n=n)).status == "UNVERIFIED"
    assert verify(cc(src="", n=1)).status == "UNVERIFIED"
    assert verify(cc(tests="", n=1)).status == "UNVERIFIED"
    assert verify(cc(src="x" * (pc.MAX_TEXT + 1))).status == "UNVERIFIED"


@needs_sandbox
def test_forged_pytest_summary_with_early_exit_is_rejected():
    forged = "import os\ndef test_a():\n    print('1 passed in 0.01s')\n    os._exit(0)\n"
    r = verify(cc(tests=forged))
    assert r.status == "UNVERIFIED" and "no junit report" in r.reason


@needs_sandbox
def test_test_that_only_prints_a_fake_summary_still_needs_a_real_run():
    t = "def test_a():\n    print('5 passed in 0.01s')\n    assert False\n"
    assert verify(cc(tests=t, n=5)).status == "UNVERIFIED"


@needs_sandbox
def test_conftest_or_plugin_injection_via_evidence_does_not_change_the_verdict():
    # the evidence has only mod.py and test_mod.py; a test that tries to make pytest swallow failures is still judged by junit
    t = ("import pytest\n@pytest.hookimpl(hookwrapper=True)\ndef pytest_runtest_makereport(item, call):\n    yield\n"
         "def test_a():\n    assert False\n")
    assert verify(cc(tests=t)).status == "UNVERIFIED"


@needs_sandbox
def test_documented_limit_in_process_forgery_of_the_junit_file_is_not_defended():
    """KNOWN LIMIT (named, not fixed): code that runs inside the checked pytest process can write /out/junit.xml itself.
    This test pins the current behaviour so nobody claims the checker defends it."""
    xml = '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"/></testsuite>'
    t = (f"import os\ndef test_a():\n    open('/out/junit.xml','w').write({xml!r})\n"
         "    for fd in range(1, 20):\n        try:\n            os.write(fd, b'1 passed in 0.01s\\n')\n        except OSError:\n            pass\n    os._exit(0)\n")
    assert verify(cc(tests=t)).status == "VERIFIED"


# ---------------------------------------------------------------- analysis + sandbox properties
@needs_sandbox
def test_analysis_rerun_accept_and_tamper():
    s = "print(sum(range(10)))\n"
    assert verify(an(s, b"45\n")).status == "VERIFIED"
    assert verify(an(s, b"46\n")).status == "UNVERIFIED"
    assert verify(an("raise SystemExit(3)", b"")).status == "UNVERIFIED"
    assert verify(an("print(1)", b"1\n", confidence=0.0)).status == "VERIFIED"
    assert verify(Conclusion("a", "analysis", dict(script=s, output_sha256=sha(b"45\n").upper()))).status == "UNVERIFIED"
    assert verify(Conclusion("a", "analysis", dict(script="", output_sha256="x"))).status == "UNVERIFIED"
    assert verify(Conclusion("a", "analysis", dict(script=s))).status == "UNVERIFIED"
    assert verify(Conclusion("a", "analysis", dict(script="x" * (pc.MAX_TEXT + 1), output_sha256="x"))).status == "UNVERIFIED"


@needs_sandbox
def test_nondeterministic_script_is_rejected():
    r = verify(an("import os\nprint(os.urandom(8).hex())", b"anything"))
    assert r.status == "UNVERIFIED" and "not deterministic" in r.reason
    r = verify(an("import time\nprint(time.time_ns())", b"x"))
    assert "not deterministic" in r.reason


@needs_sandbox
def test_script_state_does_not_persist_between_reruns():
    s = "import os\nprint(os.path.exists('/work/flag'))\nopen('/work/flag','w').write('x')\n"
    assert verify(an(s, b"False\n")).status == "VERIFIED"


def _out(script, **lim):
    r = run_sandboxed([pc.sys.executable, "-I", "-B", "/work/a.py"], {"a.py": script}, Limits(**{**FAST.__dict__, **lim}))
    return r


@needs_sandbox
def test_network_is_unreachable_from_inside():
    s = ("import socket\ntry:\n    socket.create_connection(('127.0.0.1', 9), 2)\n    print('connected')\n"
         "except OSError:\n    print('blocked')\nprint([n for _, n in socket.if_nameindex()])\n")
    out = _out(s).stdout
    assert out.startswith("blocked") and "'lo'" in out and "eth" not in out and "wlan" not in out


@needs_sandbox
def test_loopback_server_on_host_is_not_reachable(tmp_path):
    import socket, threading
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); port = srv.getsockname()[1]
    hit = []
    srv.settimeout(4)

    def accept():
        try:
            hit.append(srv.accept())
        except OSError:
            pass
    th = threading.Thread(target=accept, daemon=True); th.start()
    out = _out(f"import socket\ntry:\n    socket.create_connection(('127.0.0.1', {port}), 2)\n    print('connected')\nexcept OSError:\n    print('blocked')\n").stdout
    srv.close(); th.join(6)
    assert out.strip() == "blocked" and hit == []


@needs_sandbox
def test_environment_is_cleared(monkeypatch):
    monkeypatch.setenv("PCC_SECRET_TOKEN", "hunter2")
    out = _out("import os\nprint(sorted(os.environ))").stdout
    assert "hunter2" not in out and "PCC_SECRET_TOKEN" not in out
    assert "HOME" in out and "PATH" in out


@needs_sandbox
def test_host_files_are_not_visible_and_system_is_read_only(tmp_path):
    secret = tmp_path / "secret.txt"; secret.write_text("topsecret")
    s = (f"import os\nprint(os.path.exists({str(secret)!r}))\n"
         "try:\n    open('/usr/pcc_probe','w')\n    print('wrote')\nexcept OSError:\n    print('ro')\n"
         "print(os.listdir('/work'))\n")
    out = _out(s).stdout.splitlines()
    assert out[0] == "False" and out[1] == "ro" and out[2] == "['a.py']"


@needs_sandbox
def test_sandbox_writes_do_not_reach_the_host(tmp_path):
    marker = f"pcc_marker_{os.getpid()}"
    _out(f"open('/tmp/{marker}','w').write('x')\nopen('/work/{marker}','w').write('x')\n")
    assert not os.path.exists(f"/tmp/{marker}")


@needs_sandbox
def test_wall_clock_timeout_kills_a_sleeper():
    t0 = time.time()
    r = _out("import time\ntime.sleep(60)", wall_s=2.0)
    assert r.timed_out and time.time() - t0 < 15
    v = verify(an("import time\ntime.sleep(60)", b""), Limits(wall_s=2.0, cpu_s=3))
    assert v.status == "UNVERIFIED" and "timed out" in v.reason


@needs_sandbox
def test_cpu_limit_stops_a_spinner_before_the_wall_clock():
    t0 = time.time()
    r = _out("while True:\n    pass", wall_s=30.0, cpu_s=1)
    assert not r.timed_out and r.returncode != 0 and time.time() - t0 < 15


@needs_sandbox
def test_memory_limit_applies_and_small_allocation_is_fine():
    ok = _out("x = bytearray(50 * 1024 ** 2)\nprint(len(x))", mem_mb=1024)
    assert ok.returncode == 0 and ok.stdout.strip() == str(50 * 1024 ** 2)
    big = _out("x = bytearray(1500 * 1024 ** 2)\nprint(len(x))", mem_mb=1024)
    assert big.returncode != 0 and "MemoryError" in big.stderr


@needs_sandbox
def test_file_size_limit_applies():
    r = _out("f = open('/work/big','wb')\nf.write(b'x' * (3 * 1024 ** 2))\nf.flush()\nprint('wrote')", fsize_mb=1)
    assert "wrote" not in r.stdout and r.returncode != 0


@needs_sandbox
def test_open_file_limit_applies():
    r = _out("fs = []\ntry:\n    for i in range(500):\n        fs.append(open('/work/a.py'))\n    print('ok')\nexcept OSError:\n    print('limited')\n", nofile=64)
    assert r.stdout.strip() == "limited"


@needs_sandbox
def test_process_cap_contains_a_fork_bomb():
    s = ("import os\nn = 0\nfor i in range(400):\n    try:\n        pid = os.fork()\n    except OSError:\n        break\n"
         "    if pid == 0:\n        import time; time.sleep(5); os._exit(0)\n    n += 1\nprint(n)\n")
    r = _out(s, nproc_extra=20)
    assert r.returncode == 0 and int(r.stdout.strip()) < 100
    time.sleep(0.2)
    leftovers = [p for p in os.listdir("/proc") if p.isdigit() and _cmd(p).startswith(pc.sys.executable) and "/work/a.py" in _cmd(p)]
    assert leftovers == []


def _cmd(pid):
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode()
    except OSError:
        return ""


@needs_sandbox
def test_output_flood_is_capped_and_not_a_pass():
    r = _out("import sys\nsys.stdout.write('a' * 3_000_000)", max_out=1000, fsize_mb=8)
    assert r.truncated and len(r.stdout) == 1000
    s = "import sys\nsys.stdout.write('a' * 300000)"
    v = verify(an(s, b"a" * 300000), Limits(wall_s=10.0, cpu_s=5, max_out=1000))
    assert v.status == "UNVERIFIED" and "exceeded cap" in v.reason


@needs_sandbox
def test_orphan_background_process_is_reaped():
    s = ("import os, time\nif os.fork() == 0:\n    time.sleep(30)\n    os._exit(0)\nprint('parent done')\n")
    r = _out(s)
    assert r.returncode == 0
    time.sleep(0.3)
    assert not [p for p in os.listdir("/proc") if p.isdigit() and "/work/a.py" in _cmd(p)]


# ---------------------------------------------------------------- added to kill mutation survivors
import shutil
from types import SimpleNamespace


def test_limits_defaults_and_constants_are_pinned():
    d = Limits()
    assert (d.wall_s, d.cpu_s, d.mem_mb, d.fsize_mb, d.nofile, d.max_out, d.nproc_extra) == (20.0, 10, 1024, 8, 128, 200_000, 48)
    assert (pc.MAX_BITS, pc.MAX_FACTORS, pc.MAX_TEXT) == (4096, 64, 1_000_000)


def test_factorization_bit_boundary():
    ok = lambda n, f: verify(Conclusion("x", "factorization", dict(n=n, factors=f))).status
    assert ok(2 ** 4095, [2, 2 ** 4094]) == "VERIFIED"      # 4096 bits
    assert ok(2 ** 4096, [2, 2 ** 4095]) == "UNVERIFIED"    # 4097 bits


def test_bwrap_path_is_which_bwrap(monkeypatch):
    assert pc.bwrap_path() == shutil.which("bwrap")
    monkeypatch.setattr(pc.shutil, "which", lambda n: "/x/bwrap" if n == "bwrap" else None)
    assert pc.bwrap_path() == "/x/bwrap"


def test_sandbox_probe_logic(monkeypatch):
    monkeypatch.setattr(pc, "bwrap_path", lambda: "/x/bwrap")
    cases = [(0, "42\n", True), (1, "42\n", False), (0, "41\n", False), (2, "41\n", False), (0, "", False)]
    for rc, out, want in cases:
        monkeypatch.setattr(pc, "run_sandboxed", lambda *a, **k: pc.RunResult(rc, out, "", False, False))
        assert pc.sandbox_ok(refresh=True) is want, (rc, out)
    def boom(*a, **k):
        raise OSError("x")
    monkeypatch.setattr(pc, "run_sandboxed", boom)
    assert pc.sandbox_ok(refresh=True) is False
    pc._PROBE.clear()


def test_uid_proc_count_and_mounts_shape():
    n = pc._count_uid_procs()
    assert n >= 1 and isinstance(n, int)
    m = pc._py_mounts()
    assert isinstance(m, list) and m and sys.prefix in m and all(os.path.isdir(x) for x in m)
    assert not {"/", "/usr", "/home"} & set(m) and not any(x.startswith("/usr/") for x in m)





def test_bwrap_argv_structure(monkeypatch):
    monkeypatch.setattr(pc, "bwrap_path", lambda: "/x/bwrap")
    a = pc._bwrap_argv("/w", "/o", ["prog", "arg"])
    assert a[0] == "/x/bwrap" and a[-3:] == ["--", "prog", "arg"]
    for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--proc", "--dev"):
        assert flag in a
    j = " ".join(a)
    assert "--ro-bind /usr /usr" in j and "--bind /w /work" in j and "--bind /o /out" in j and "--tmpfs /tmp" in j
    assert "--chdir /work" in j and "--symlink usr/bin /bin" in j
    assert "--setenv PATH /usr/bin:/bin" in j and "--setenv HOME /work" in j and "--setenv LANG C.UTF-8" in j
    assert "--setenv PYTHONDONTWRITEBYTECODE 1" in j and "--setenv PYTEST_DISABLE_PLUGIN_AUTOLOAD 1" in j
    for m in pc._py_mounts():
        assert f"--ro-bind {m} {m}" in j
    assert a.index("--unshare-all") < a.index("--")


@needs_sandbox
def test_rlimits_are_set_exactly_inside_the_sandbox():
    import resource as r
    lim = Limits(wall_s=8.0, cpu_s=3, mem_mb=700, fsize_mb=2, nofile=77, nproc_extra=40)
    out = _out("import resource as r\nfor n in ('CPU','AS','FSIZE','NOFILE','CORE','NPROC'):\n    print(n, r.getrlimit(getattr(r,'RLIMIT_'+n)))",
               cpu_s=3, mem_mb=700, fsize_mb=2, nofile=77, nproc_extra=40).stdout.splitlines()
    d = {l.split(" ", 1)[0]: eval(l.split(" ", 1)[1]) for l in out}
    assert d["CPU"] == (3, 3) and d["AS"] == (700 << 20, 700 << 20) and d["FSIZE"] == (2 << 20, 2 << 20)
    assert d["NOFILE"] == (77, 77) and d["CORE"] == (0, 0)
    assert d["NPROC"][0] == d["NPROC"][1] and d["NPROC"][0] >= 40


@needs_sandbox
def test_output_cap_boundary_and_invalid_utf8_decoding():
    exact = _out("import sys\nsys.stdout.write('a' * 100)", max_out=100)
    assert exact.stdout == "a" * 100 and exact.truncated is False
    over = _out("import sys\nsys.stdout.write('a' * 101)", max_out=100)
    assert over.truncated is True and len(over.stdout) == 100
    bad = _out("import sys\nsys.stdout.buffer.write(b'x\\xffy')")
    assert bad.stdout == "x\ufffdy"
    assert exact.junit is None


def test_quote_and_text_limits_and_reasons():
    big = "a" * pc.MAX_TEXT
    r = verify(Conclusion("q", "sourced_quote", dict(source_text=big, source_sha256=sha(big.encode()), quote="a")))
    assert r.status == "VERIFIED"                                    # exactly MAX_TEXT is allowed
    assert check_sourced_quote(dict(source_text="t", source_sha256="h", quote=None))[1] == "missing source text, hash or quote"
    assert check_sourced_quote(dict(source_text="", source_sha256="h", quote="q"))[1] == "missing source text, hash or quote"
    assert check_sourced_quote(dict(source_text="t" * (pc.MAX_TEXT + 1), source_sha256="h", quote="t"))[1] == "evidence too large"
    assert check_sourced_quote(dict(source_text="t", source_sha256="h", quote="t" * (pc.MAX_TEXT + 1)))[1] == "evidence too large"


def _fake(monkeypatch, **kw):
    calls = []
    base = dict(returncode=0, stdout="", stderr="", timed_out=False, truncated=False, junit=None)
    base.update(kw)
    monkeypatch.setattr(pc, "run_sandboxed", lambda *a, **k: calls.append(1) or pc.RunResult(**base))
    return calls


GOOD_XML = '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"/></testsuite>'


def test_analysis_reasons_and_exactly_two_runs(monkeypatch):
    assert check_analysis(dict(script=123, output_sha256="x"))[1] == "missing script or output hash"
    assert check_analysis(dict(script="", output_sha256="x"))[1] == "missing script or output hash"
    assert check_analysis(dict(script="x", output_sha256=""))[1] == "missing script or output hash"
    assert check_analysis(dict(script="x", output_sha256=5))[1] == "missing script or output hash"
    assert check_analysis(dict(script="x" * (pc.MAX_TEXT + 1), output_sha256="x"))[1] == "evidence too large"
    calls = _fake(monkeypatch, stdout="1\n")
    assert check_analysis(dict(script="x", output_sha256=sha(b"1\n"))) == (True, "re-run output hash matches")
    assert len(calls) == 2
    _fake(monkeypatch, stdout="1\n")
    assert check_analysis(dict(script="x", output_sha256=sha(b"2\n"))) == (False, "re-run output hash differs")
    _fake(monkeypatch, returncode=3)
    assert check_analysis(dict(script="x", output_sha256="x")) == (False, "script exit 3")
    _fake(monkeypatch, timed_out=True)
    assert check_analysis(dict(script="x", output_sha256="x")) == (False, "script timed out")
    _fake(monkeypatch, truncated=True)
    assert check_analysis(dict(script="x", output_sha256="x")) == (False, "script output exceeded cap")


def test_code_change_branch_reasons(monkeypatch):
    ev = dict(source="s", tests="t", expected_passed=1)
    miss = "missing source, tests or expected count"
    assert check_code_change(dict(ev, source=5))[1] == miss
    assert check_code_change(dict(ev, tests=5))[1] == miss
    assert check_code_change(dict(ev, source=""))[1] == miss
    assert check_code_change(dict(ev, tests=""))[1] == miss
    assert check_code_change(dict(ev, expected_passed=0))[1] == miss
    assert check_code_change(dict(ev, source="s" * (pc.MAX_TEXT + 1)))[1] == "evidence too large"
    assert check_code_change(dict(ev, tests="t" * (pc.MAX_TEXT + 1)))[1] == "evidence too large"
    _fake(monkeypatch, timed_out=True)
    assert check_code_change(ev) == (False, "tests timed out")
    _fake(monkeypatch, returncode=2)
    assert check_code_change(ev) == (False, "tests did not reproduce (exit 2)")
    _fake(monkeypatch, junit=None)
    assert check_code_change(ev) == (False, "no junit report")
    _fake(monkeypatch, junit="<testsuite")
    assert check_code_change(ev) == (False, "unparseable junit report")
    _fake(monkeypatch, junit='<testsuites><testsuite tests="1"/><testsuite tests="1"/></testsuites>', stdout="1 passed in 0.1s")
    assert check_code_change(ev)[0] is False
    _fake(monkeypatch, junit=GOOD_XML.replace('tests="1"', 'tests="2"'), stdout="1 passed in 0.1s")
    assert check_code_change(ev)[1].startswith("junit counts do not match expected 1")
    _fake(monkeypatch, junit=GOOD_XML.replace('skipped="0"', 'skipped="1"'), stdout="1 passed in 0.1s")
    assert check_code_change(ev)[0] is False
    _fake(monkeypatch, junit=GOOD_XML.replace('<testcase name="a"/>', '<testcase name="a"><failure/></testcase>'), stdout="1 passed in 0.1s")
    assert check_code_change(ev)[0] is False
    _fake(monkeypatch, junit=GOOD_XML, stdout="2 passed in 0.1s")
    assert check_code_change(ev) == (False, "stdout summary disagrees with junit")
    _fake(monkeypatch, junit=GOOD_XML, stdout="")
    assert check_code_change(ev) == (False, "stdout summary disagrees with junit")
    _fake(monkeypatch, junit=GOOD_XML, stdout="1 passed in 0.1s")
    assert check_code_change(ev) == (True, "tests re-run in sandbox and pass")
