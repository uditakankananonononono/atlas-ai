"""Row 86 / module function ledger: per-module count of public functions
added between two git revisions (AST based).

Source excerpt (supplied text): "add 20 new features/capabilities to every
module". This computes ADDED PUBLIC FUNCTIONS per module directory between a
base and head revision, and compares each count with the target. A function
count is a proxy for features, not proof of working capability, and a module
below target is reported as BELOW_TARGET, never rounded up. Read-only git
calls, stdlib only.
"""
from __future__ import annotations

import ast
import subprocess

TARGET = 20


def _git(repo, *args):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True,
                       timeout=60, check=False)
    if p.returncode != 0:
        raise ValueError("LEDGER_REFUSED_GIT:" + p.stderr.decode("utf-8", "replace")[:200])
    return p.stdout


def _funcs(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    out = set()

    def walk(body, prefix):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not n.name.startswith("_"):
                    out.add(prefix + n.name)
            elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                walk(n.body, prefix + n.name + ".")
    walk(tree.body, "")
    return out


def _snapshot(repo, rev, root):
    names = _git(repo, "ls-tree", "-r", "--name-only", rev, "--", root).decode().splitlines()
    snap, unparsed = {}, []
    for path in names:
        if not path.endswith(".py"):
            continue
        funcs = _funcs(_git(repo, "show", "%s:%s" % (rev, path)).decode("utf-8", "replace"))
        if funcs is None:
            unparsed.append(path)
        else:
            snap[path] = funcs
    return snap, unparsed


def _module_of(path, root):
    rest = path[len(root):].lstrip("/")
    return rest.split("/", 1)[0] if "/" in rest else "(root)"


def build(repo, base, head, root, target=TARGET):
    """Return the ledger. root is a repo-relative modules directory."""
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise ValueError("LEDGER_REFUSED_BAD_TYPE:target")
    old, bad_old = _snapshot(repo, base, root)
    new, bad_new = _snapshot(repo, head, root)
    mods = {}
    for path, funcs in new.items():
        added = funcs - old.get(path, set())
        mods.setdefault(_module_of(path, root), set()).update(path + "::" + f for f in added)
    for path in old:
        mods.setdefault(_module_of(path, root), set())
    rows = []
    for mod in sorted(mods):
        n = len(mods[mod])
        rows.append({"module": mod, "added_public_functions": n,
                     "verdict": "AT_OR_ABOVE_TARGET" if n >= target else "BELOW_TARGET",
                     "shortfall": max(0, target - n)})
    empty = sorted(r["module"] for r in rows if r["added_public_functions"] == 0
                   and not any(p for p in new if _module_of(p, root) == r["module"]))
    coverage_known = bool(rows) and not (bad_old or bad_new) and not empty
    below = [r["module"] for r in rows if r["verdict"] == "BELOW_TARGET"]
    return {"base": base, "head": head, "root": root, "target": target, "rows": rows,
            "modules": len(rows), "below_target": len(below), "below_target_modules": below,
            "unparsed_files": sorted(bad_old + bad_new),
            "modules_absent_at_head": empty,
            "coverage_known": coverage_known,
            "complete": coverage_known and not below,
            "scope": {"implemented": ["AST count of added public functions per module"],
                      "not_implemented": ["proof that an added function is a working feature",
                                          "independent per-feature acceptance",
                                          "Sugarcode modules (separate repo)"],
                      "data_source": "git revisions " + base + ".." + head}}
