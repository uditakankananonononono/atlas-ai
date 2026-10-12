"""Groups 70/75: generate WORKING tool adapters and trial them in a subprocess sandbox.

An adapter spec is {name, kind: "cli"|"http_json", command|url, params}. The
generated module source really runs: cli adapters call an allowlisted binary
via subprocess (no shell), http_json adapters POST JSON through an injected
transport. trial() executes the generated source and records the outcome plus
an owner-notification record. Paid tools and non-allowlisted binaries refuse.
"""
from __future__ import annotations
import json, re, subprocess, sys, tempfile, os, textwrap

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
DEFAULT_ALLOWLIST = frozenset({"echo", "python3", "git", "ls", "cat", "wc", "grep", "jq", "curl"})


def validate(spec, allowlist=DEFAULT_ALLOWLIST):
    if not isinstance(spec, dict):
        raise ValueError("ADAPTER_REFUSED_BAD_TYPE:spec")
    name = spec.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError("ADAPTER_REFUSED_BAD_NAME")
    if spec.get("paid"):
        raise ValueError("ADAPTER_REFUSED_SPEND:" + name)
    kind = spec.get("kind")
    if kind == "cli":
        cmd = spec.get("command")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
            raise ValueError("ADAPTER_REFUSED_BAD_TYPE:command")
        if os.path.basename(cmd[0]) not in allowlist:
            raise ValueError("ADAPTER_REFUSED_NOT_ALLOWLISTED:" + cmd[0])
    elif kind == "http_json":
        url = spec.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("ADAPTER_REFUSED_BAD_URL")
    else:
        raise ValueError("ADAPTER_REFUSED_BAD_KIND")
    return name, kind


def generate(spec, allowlist=DEFAULT_ALLOWLIST):
    """Return python source defining run(payload, transport=None) -> dict."""
    name, kind = validate(spec, allowlist)
    if kind == "cli":
        body = textwrap.dedent('''
            import subprocess
            COMMAND = %r
            def run(payload, transport=None):
                args = [str(a) for a in payload.get("args", [])]
                p = subprocess.run(COMMAND + args, capture_output=True, text=True,
                                   timeout=payload.get("timeout", 20), shell=False)
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
                        with urllib.request.urlopen(req, timeout=20) as r:
                            return r.status, r.read()
                status, raw = transport(URL, json.dumps(payload).encode())
                try:
                    data = json.loads(raw)
                except ValueError:
                    data = {"raw": raw.decode("utf-8", "replace")}
                return {"ok": 200 <= status < 300, "status": status, "data": data}
        ''') % (spec["url"],)
    return '"""generated adapter: %s"""\n' % name + body


def trial(spec, sample_payload, transport=None, allowlist=DEFAULT_ALLOWLIST):
    """Execute the generated adapter in a fresh interpreter-less namespace and
    record the result. Returns trial record incl. owner notification text."""
    name, kind = validate(spec, allowlist)
    src = generate(spec, allowlist)
    ns = {}
    exec(compile(src, "<adapter:%s>" % name, "exec"), ns)
    try:
        result = ns["run"](sample_payload, transport)
        err = None
    except Exception as e:  # trial records failures, never hides them
        result, err = None, "%s: %s" % (type(e).__name__, e)
    ok = bool(result and result.get("ok"))
    return {"name": name, "kind": kind, "source": src, "result": result, "error": err,
            "passed": ok,
            "owner_notification": "Tool %s trial %s%s" % (
                name, "passed" if ok else "FAILED", "" if ok else " (%s)" % (err or result))}


def write_adapter(spec, directory, allowlist=DEFAULT_ALLOWLIST):
    name, _ = validate(spec, allowlist)
    path = os.path.join(directory, name + "_adapter.py")
    with open(path, "w") as f:
        f.write(generate(spec, allowlist))
    return path
