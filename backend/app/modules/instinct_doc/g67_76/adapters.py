"""Groups 70/75: generate tool adapters and trial them in a child process.

An adapter spec is {name, kind: "cli"|"http_json", command|url}. generate()
emits Python source defining run(payload, transport=None). trial() never execs
that source in this process: it writes it to a temp dir and runs it in a
separate `python -I` child with a stripped environment, CPU/memory/file-size
rlimits and a wall-clock timeout. This is process isolation with resource
limits, not a security boundary: no namespace, seccomp or network isolation.
HTTP adapters may only target hosts on an explicit allowlist.

Limits stated plainly:
- "paid" is caller-declared. Nothing here can detect that a tool costs money.
- CLI commands must be an absolute path that is itself on the allowlist
  (no interpreters, no PATH lookup, no shell).
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile, textwrap, urllib.parse

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
DEFAULT_CLI_ALLOWLIST = frozenset({"/bin/echo", "/usr/bin/echo", "/bin/ls", "/usr/bin/ls",
                                   "/usr/bin/wc", "/bin/wc"})
RUNNER = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import adapter
req = json.load(sys.stdin)
stub = req.get("stub_response")
transport = None
if stub is not None:
    transport = lambda url, data: (stub["status"], json.dumps(stub["body"]).encode())
print(json.dumps(adapter.run(req["payload"], transport)))
'''


def validate(spec, cli_allowlist=DEFAULT_CLI_ALLOWLIST, allowed_hosts=frozenset()):
    if not isinstance(spec, dict):
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:spec")
    name = spec.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError("ADAPTER_REFUSED_BAD_NAME")
    if spec.get("paid"):  # caller-declared flag only
        raise ValueError("ADAPTER_REFUSED_SPEND:" + name)
    kind = spec.get("kind")
    if kind == "cli":
        cmd = spec.get("command")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
            raise ValueError("ADAPTER_REFUSED_BAD_TYPE:command")
        if not os.path.isabs(cmd[0]) or cmd[0] not in cli_allowlist:
            raise ValueError("ADAPTER_REFUSED_NOT_ALLOWLISTED:" + cmd[0])
    elif kind == "http_json":
        url = spec.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("ADAPTER_REFUSED_BAD_URL")
        host = urllib.parse.urlparse(url).hostname
        if not host or host not in allowed_hosts:
            raise ValueError("ADAPTER_REFUSED_HOST_NOT_ALLOWLISTED:%s" % host)
    else:
        raise ValueError("ADAPTER_REFUSED_BAD_KIND")
    return name, kind


def generate(spec, cli_allowlist=DEFAULT_CLI_ALLOWLIST, allowed_hosts=frozenset()):
    name, kind = validate(spec, cli_allowlist, allowed_hosts)
    if kind == "cli":
        body = textwrap.dedent('''
            import subprocess
            COMMAND = %r
            def run(payload, transport=None):
                args = [str(a) for a in payload.get("args", [])]
                p = subprocess.run(COMMAND + args, capture_output=True, text=True,
                                   timeout=payload.get("timeout", 10), shell=False)
                return {"ok": p.returncode == 0, "code": p.returncode,
                        "stdout": p.stdout, "stderr": p.stderr}
        ''') % (list(spec["command"]),)
    else:
        body = textwrap.dedent('''
            import json
            URL = %r
            def run(payload, transport=None):
                if transport is None:
                    import urllib.request
                    def transport(url, data):
                        req = urllib.request.Request(url, data=data,
                              headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            return r.status, r.read()
                status, raw = transport(URL, json.dumps(payload).encode())
                try:
                    data = json.loads(raw)
                except ValueError:
                    data = {"raw": raw.decode("utf-8", "replace")}
                return {"ok": 200 <= status < 300, "status": status, "data": data}
        ''') % (spec["url"],)
    return '"""generated adapter: %s"""\n' % name + body


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    resource.setrlimit(resource.RLIMIT_AS, (1 << 29, 1 << 29))


def trial(spec, sample_payload, stub_response=None, cli_allowlist=DEFAULT_CLI_ALLOWLIST,
          allowed_hosts=frozenset(), timeout=20):
    """Run the generated adapter in a child process; stub_response={"status":int,"body":obj}
    makes an http_json trial offline. Failures are recorded, not hidden."""
    name, kind = validate(spec, cli_allowlist, allowed_hosts)
    src = generate(spec, cli_allowlist, allowed_hosts)
    result = err = None
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "adapter.py"), "w") as f:
            f.write(src)
        with open(os.path.join(d, "runner.py"), "w") as f:
            f.write(RUNNER)
        try:
            p = subprocess.run([sys.executable, "-I", os.path.join(d, "runner.py"), d],
                               input=json.dumps({"payload": sample_payload, "stub_response": stub_response}),
                               capture_output=True, text=True, timeout=timeout, env={},
                               cwd=d, preexec_fn=_limits)
            if p.returncode == 0:
                result = json.loads(p.stdout)
            else:
                err = "child exit %d: %s" % (p.returncode, p.stderr.strip()[-300:])
        except subprocess.TimeoutExpired:
            err = "timeout"
    ok = bool(result and result.get("ok"))
    return {"name": name, "kind": kind, "source": src, "result": result, "error": err,
            "passed": ok,
            "isolation": "child process, env stripped, rlimits, timeout (not a security boundary)",
            "owner_notification": "Tool %s trial %s%s" % (
                name, "passed" if ok else "FAILED", "" if ok else " (%s)" % (err or result))}


def write_adapter(spec, directory, cli_allowlist=DEFAULT_CLI_ALLOWLIST, allowed_hosts=frozenset()):
    name, _ = validate(spec, cli_allowlist, allowed_hosts)
    path = os.path.join(directory, name + "_adapter.py")
    with open(path, "w") as f:
        f.write(generate(spec, cli_allowlist, allowed_hosts))
    return path
