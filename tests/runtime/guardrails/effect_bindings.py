"""Effect-path binding computation (instinct-doc rows 137 + 142).

Every module under backend/app that imports a network/effect client is bound to exactly one status,
COMPUTED from code evidence (AST scan + file/test existence), never declared:

  GATED              direct guardrail import, OR every call of a declared gated write method in
                     non-test app code sits in a declared gated-caller file whose source contains the
                     gate call, and the named refusal test file exists
  EXEMPT-BY-DESIGN   no write-method / browser-action call found by the scan, AND a named reason from
                     EXEMPT_REASONS (by path prefix). Read-only by STATIC SCAN, not certified
  UNGATED            everything else; a gap (DEFECT-class). Includes read-only modules with no named reason

Limits (by construction): the scan is import- and call-name-based. It misses dynamic imports, aliasing,
helper indirection and side-effecting GET requests. Counts are declared by the computation, not certified.
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "backend" / "app").is_dir())
APP = ROOT / "backend" / "app"
EGRESS = ("httpx", "requests", "aiohttp", "smtplib", "urllib.request", "playwright", "selenium", "imaplib", "socket", "stripe")
WRITE_CALLS = {"post", "put", "patch", "delete", "request", "send", "sendmail", "send_message", "publish", "submit",
               "stream", "click", "send_keys", "fill", "type", "press", "check", "select_option", "evaluate", "execute_script"}
SOCKET_LOOKUP_ONLY = {"getaddrinfo", "gaierror", "gethostname", "timeout"}

# Files whose source contains the gate call, with the test that shows a refusal on that path.
GATED_CALLERS = {
    "modules/m06_social_media_manager/scheduler.py": ("dispatch_outbound", "tests/modules/test_m06_publish_guardrail.py"),
    "workers/tasks.py": ("dispatch_outbound", "tests/modules/test_worker_outbound_gate.py"),
    "runtime/approved_execution.py": ("dispatch_outbound", "tests/runtime/test_approved_execution.py"),
}
# egress module -> write method that must be reachable only from GATED_CALLERS
GATED_WRITE_METHODS = {"modules/m06_social_media_manager/adapters.py": "publish"}

# Named reasons for read-only classification, by path prefix (first match wins).
EXEMPT_REASONS = (
    ("modules/m01_opportunity_discovery/", "public opportunity-source reads"),
    ("modules/m05_outreach_manager/discovery.py", "public contact-source reads"),
    ("modules/m05_outreach_manager/enrichment.py", "public enrichment reads"),
    ("modules/m07_brand_collaboration/", "public brand-source reads"),
    ("modules/m18_side_hustle_scraper/", "public listing reads"),
    ("modules/m19_idea_incubator/", "public research-source reads"),
    ("modules/m22_tools_hub/", "public tool-registry reads"),
    ("modules/m23_study_abroad/", "public admissions-source reads"),
    ("modules/c30/", "public-source read helper with address validation"),
    ("modules/instinct_doc/g67_76/", "feed read with address validation"),
    ("modules/m13_browser_agent/security.py", "address validation (DNS lookup only)"),
    ("modules/m21_claire/meemee_webhook_security.py", "webhook address validation (DNS lookup only)"),
    ("modules/m12_ai_research_lab/checkpoint_loop.py", "local hostname lookup only"),
    ("market/sources.py", "public market-data reads"),
    ("collectors/", "collector base: reads"),
    ("core/model_catalog.py", "model catalog read"),
    ("integrations/google_grounding.py", "grounding read"),
    ("auth/context.py", "auth key-set read"),
    ("platform/vault_dev_adapter.py", "dev vault read"),
    ("modules/m24_billing/reconciliation.py", "provider lookup reads (reconciliation evidence)"),
)


def _imports(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            yield n.module


def _rel(p):
    return p.relative_to(APP).as_posix()


def _files():
    for p in sorted(APP.rglob("*.py")):
        rel = _rel(p)
        if rel.startswith("runtime/guardrails/"):
            continue
        try:
            yield rel, p.read_text(encoding="utf-8"), ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue


def classify():
    egress, direct, calls, sockattrs, src = {}, set(), {}, {}, {}
    attr_sites = {}  # method -> set(files calling it)
    for rel, text, tree in _files():
        names = set(_imports(tree))
        libs = sorted({n for n in names for e in EGRESS if n == e or n.startswith(e + ".")})
        meth = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                attr_sites.setdefault(n.func.attr, set()).add(rel)
                if n.func.attr in WRITE_CALLS:
                    meth.add(n.func.attr)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"POST|PUT|PATCH|DELETE", n.value):
                meth.add("method:" + n.value)
        if libs:
            egress[rel] = libs
            calls[rel] = sorted(meth)
            sockattrs[rel] = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                              and isinstance(n.value, ast.Name) and n.value.id == "socket"}
            if any(n.startswith("app.runtime.guardrails") for n in names):
                direct.add(rel)
        src[rel] = text
    result = {}
    for rel, libs in egress.items():
        status, evidence = "UNGATED", "no gate evidence"
        write_calls = calls[rel]
        if rel in direct:
            status, evidence = "GATED", "imports app.runtime.guardrails"
        elif rel in GATED_WRITE_METHODS:
            m = GATED_WRITE_METHODS[rel]
            pkg = rel.rsplit('/', 1)[0] + '/'
            sites = sorted(x for x in attr_sites.get(m, set()) if x.startswith(pkg))  # same package only: generic method names collide elsewhere
            ok = True
            why = []
            for site in sites:
                if site == rel:
                    continue  # the definition's own file (defs are not call sites we gate)
                caller = GATED_CALLERS.get(site)
                if caller is None or caller[0] not in src[site] or not (ROOT / caller[1]).is_file():
                    ok = False
                    why.append(site)
            if ok:
                status = "GATED"
                evidence = f"write method .{m}( called only from gated callers {[s for s in sites if s in GATED_CALLERS]}; refusal tests exist (package-scoped check; other adapter methods, e.g. fetch_metrics, are reads)"
            else:
                evidence = f".{m}( also called from ungated files {why}"
        if status != "GATED" and not evidence.startswith("."):
            only_lookup = (set(libs) <= {"socket"} and sockattrs[rel] <= SOCKET_LOOKUP_ONLY)
            if not write_calls or only_lookup:
                reason = next((r for pfx, r in EXEMPT_REASONS if rel.startswith(pfx)), None)
                if reason:
                    status, evidence = "EXEMPT-BY-DESIGN", f"{reason}; no write-method call found by static scan (not certified)"
                else:
                    evidence = "read-only by static scan but NO named reason: unreviewed"
            else:
                evidence = f"write-capable calls found: {write_calls}"
        result[rel] = {"status": status, "evidence": evidence, "libs": libs, "write_calls": write_calls}
    return result


def counts(result=None):
    result = result or classify()
    out = {"GATED": 0, "EXEMPT-BY-DESIGN": 0, "UNGATED": 0}
    for v in result.values():
        out[v["status"]] += 1
    return out
