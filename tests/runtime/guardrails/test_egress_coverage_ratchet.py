"""Egress-coverage ratchet (instinct-doc groups 134-142, honest coverage number).

Static AST scan of backend/app for modules that import a network/effect client.
A module counts as gated only if it imports app.runtime.guardrails. UNGATED_BASELINE
is the known ungated set at the time this test was written: the test fails if a NEW
ungated egress module appears (ratchet) or if a baseline module became gated/removed
and the baseline was not shrunk. It proves nothing about gate correctness and does
not claim the baseline modules are safe; it only measures wiring.
"""
import ast
import pathlib

def _find_app():
    for parent in pathlib.Path(__file__).resolve().parents:
        if (parent / "backend" / "app").is_dir():
            return parent / "backend" / "app"
    raise RuntimeError("backend/app not found above " + __file__)


APP = _find_app()
EGRESS = {"httpx", "requests", "aiohttp", "smtplib", "urllib.request", "playwright", "selenium", "imaplib", "socket", "stripe"}


def _imports(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            yield n.module
            for a in n.names:
                yield f"{n.module}.{a.name}"


def scan():
    egress, gated = set(), set()
    for p in sorted(APP.rglob("*.py")):
        rel = p.relative_to(APP).as_posix()
        if rel.startswith("runtime/guardrails/"):
            continue
        try:
            names = set(_imports(ast.parse(p.read_text(encoding="utf-8"))))
        except SyntaxError:
            continue
        if any(n == e or n.startswith(e + ".") for n in names for e in EGRESS):
            egress.add(rel)
            if any(n.startswith("app.runtime.guardrails") for n in names):
                gated.add(rel)
    return egress, gated


def test_ratchet():
    egress, gated = scan()
    ungated = egress - gated
    baseline = set(pathlib.Path(__file__).with_name("egress_ungated_baseline.txt").read_text().split())
    assert not (ungated - baseline), f"new ungated egress modules: {sorted(ungated - baseline)}"
    assert not (baseline - ungated), f"baseline stale, shrink it: {sorted(baseline - ungated)}"


def test_report_number(capsys):
    egress, gated = scan()
    assert len(egress) > 0, "scan root resolved wrongly: zero egress modules"
    print(f"EGRESS_COVERAGE gated={len(gated)} of egress_modules={len(egress)}")
