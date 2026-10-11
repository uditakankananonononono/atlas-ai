"""Ledger row 696 - Branch by Abstraction ("Enables large changes").

A stdlib-only migration engine. Callers go through one abstraction; an old and a
new implementation sit behind it; traffic is routed old / shadow / canary / new;
behaviour of the two implementations is compared by really calling both; direct
references to the old implementation are found by parsing source with ``ast``;
and removal of the old implementation is refused until every gate is met.

Nothing here is a heuristic score: every gate is a boolean over recorded facts.
"""
from __future__ import annotations

import ast
import hashlib
from typing import Any, Iterable, Mapping, Sequence

ROUTES = ("old", "shadow", "canary", "new")


class BranchAbstractionError(ValueError):
    """Invalid configuration or a refused migration step."""


def _run(fn, args, kwargs):
    try:
        return ("ok", fn(*args, **kwargs)), None
    except Exception as exc:  # parity of failures is part of equivalence
        return ("raises", type(exc).__name__), exc


def _outcome(fn, args, kwargs):
    return _run(fn, args, kwargs)[0]


def _show(outcome) -> str:
    kind, value = outcome
    return repr(value) if kind == "ok" else f"raises {value}"


class BranchByAbstraction:
    def __init__(self, abstraction: str, operations: Sequence[str], old: object,
                 new: object, min_equivalence_cases: int = 1) -> None:
        if not isinstance(abstraction, str) or not abstraction.strip():
            raise BranchAbstractionError("abstraction name is required")
        ops = list(operations or [])
        if not ops or not all(isinstance(o, str) and o for o in ops):
            raise BranchAbstractionError("at least one operation name is required")
        if not isinstance(min_equivalence_cases, int) or isinstance(min_equivalence_cases, bool) or min_equivalence_cases < 1:
            raise BranchAbstractionError("min_equivalence_cases must be an integer >= 1")
        for label, impl in (("old", old), ("new", new)):
            for op in ops:
                if not callable(getattr(impl, op, None)):
                    raise BranchAbstractionError(f"{label} implementation lacks operation {op}")
        self.abstraction = abstraction
        self.operations = tuple(ops)
        self.min_equivalence_cases = min_equivalence_cases
        self._old: object | None = old
        self._new = new
        self._route = "old"
        self._canary_percent = 0
        self._removed = False
        self._callers: dict[str, bool] = {}
        self._equiv: dict[str, dict[str, int]] = {}
        self._scan: list[dict[str, Any]] | None = None
        self.route_log: list[tuple[str, str]] = []
        self.divergences: list[dict[str, str]] = []

    # -- phase -----------------------------------------------------------
    @property
    def phase(self) -> str:
        if self._removed:
            return "old_removed"
        if self._route == "new":
            return "switched"
        if self._route in ("shadow", "canary") or self._equiv:
            return "dual_implementation"
        if self._callers:
            return "migrate_callers"
        return "introduce"

    # -- routing ---------------------------------------------------------
    def set_route(self, mode: str, canary_percent: int = 0) -> None:
        if mode not in ROUTES:
            raise BranchAbstractionError(f"route must be one of {ROUTES}")
        if mode == "canary" and not (isinstance(canary_percent, int) and not isinstance(canary_percent, bool) and 0 <= canary_percent <= 100):
            raise BranchAbstractionError("canary_percent must be an integer 0..100")
        if self._removed and mode != "new":
            raise BranchAbstractionError("old implementation is removed; only route 'new' exists")
        self._route = mode
        self._canary_percent = canary_percent if mode == "canary" else 0

    def rollback(self) -> None:
        self.set_route("new" if self._removed else "old")

    def route_for(self, key: Any) -> str:
        if self._route == "canary":
            if key is None:
                raise BranchAbstractionError("canary routing needs a key")
            digest = hashlib.sha256(f"{self.abstraction}:{key}".encode()).hexdigest()
            return "new" if int(digest[:8], 16) % 100 < self._canary_percent else "old"
        return self._route

    def call(self, operation: str, *args: Any, key: Any = None, **kwargs: Any) -> Any:
        if operation not in self.operations:
            raise BranchAbstractionError(f"unknown operation {operation}")
        route = self.route_for(key)
        if route == "shadow":
            old_res, old_exc = _run(getattr(self._old, operation), args, kwargs)
            new_res = _outcome(getattr(self._new, operation), args, kwargs)
            if old_res != new_res:
                self.divergences.append({"operation": operation, "old": _show(old_res),
                                         "new": _show(new_res)})
            self.route_log.append((operation, "old"))
            if old_exc is not None:
                raise old_exc
            return old_res[1]
        target = self._new if route == "new" else self._old
        self.route_log.append((operation, route))
        return getattr(target, operation)(*args, **kwargs)

    # -- equivalence -----------------------------------------------------
    def verify_equivalence(self, operation: str, cases: Iterable[tuple[tuple, Mapping]]) -> dict[str, Any]:
        if operation not in self.operations:
            raise BranchAbstractionError(f"unknown operation {operation}")
        if self._old is None:
            raise BranchAbstractionError("old implementation is removed")
        cases = list(cases)
        if not cases:
            raise BranchAbstractionError("at least one case is required")
        diffs = []
        for i, (args, kwargs) in enumerate(cases):
            o = _outcome(getattr(self._old, operation), args, dict(kwargs))
            n = _outcome(getattr(self._new, operation), args, dict(kwargs))
            if o != n:
                diffs.append({"case": i, "old": _show(o), "new": _show(n)})
        rec = self._equiv.setdefault(operation, {"cases_compared": 0, "divergent_cases": 0})
        rec["cases_compared"] += len(cases)
        rec["divergent_cases"] += len(diffs)
        return {"operation": operation, "cases": len(cases),
                "matches": len(cases) - len(diffs), "divergences": diffs}

    # -- callers and static scan ----------------------------------------
    def register_caller(self, name: str) -> None:
        if not name or name in self._callers:
            raise BranchAbstractionError(f"caller {name!r} invalid or already registered")
        self._callers[name] = False

    def mark_caller_migrated(self, name: str) -> None:
        if name not in self._callers:
            raise BranchAbstractionError(f"unknown caller {name!r}")
        self._callers[name] = True

    def scan_direct_usage(self, sources: Mapping[str, str], old_symbol: str,
                          allowed_files: Sequence[str] = ()) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for path in sorted(sources):
            if path in allowed_files:
                continue
            try:
                tree = ast.parse(sources[path], filename=path)
            except SyntaxError as exc:
                findings.append({"file": path, "line": exc.lineno or 0, "kind": "unparseable"})
                continue
            aliases: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name == old_symbol or a.name.split(".")[-1] == old_symbol:
                            if a.asname and a.asname != old_symbol:
                                aliases.add(a.asname)
                elif isinstance(node, ast.ImportFrom):
                    for a in node.names:
                        if a.name == old_symbol and a.asname and a.asname != old_symbol:
                            aliases.add(a.asname)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(a.name == old_symbol or a.name.split(".")[-1] == old_symbol for a in node.names):
                        findings.append({"file": path, "line": node.lineno, "kind": "import"})
                elif isinstance(node, ast.ImportFrom):
                    if any(a.name == old_symbol for a in node.names):
                        findings.append({"file": path, "line": node.lineno, "kind": "import"})
                elif isinstance(node, ast.Name) and node.id in aliases:
                    findings.append({"file": path, "line": node.lineno, "kind": "alias"})
                elif isinstance(node, ast.Name) and node.id == old_symbol:
                    findings.append({"file": path, "line": node.lineno, "kind": "name"})
                elif isinstance(node, ast.Attribute) and node.attr == old_symbol:
                    findings.append({"file": path, "line": node.lineno, "kind": "attribute"})
        self._scan = findings
        return findings

    # -- removal gate ----------------------------------------------------
    def can_remove_old(self) -> tuple[bool, list[str]]:
        why: list[str] = []
        if self._removed:
            return (False, ["old implementation already removed"])
        if self._route != "new":
            why.append(f"route is '{self._route}', must be 'new'")
        if not self._callers:
            why.append("no callers registered")
        why += [f"caller {n} not migrated to the abstraction" for n, m in self._callers.items() if not m]
        for op in self.operations:
            rec = self._equiv.get(op)
            if rec is None or rec["cases_compared"] < self.min_equivalence_cases:
                why.append(f"equivalence for {op} below {self.min_equivalence_cases} cases")
            elif rec["divergent_cases"]:
                why.append(f"{rec['divergent_cases']} divergent case(s) recorded for {op}")
        if self.divergences:
            why.append(f"{len(self.divergences)} shadow divergence(s) recorded")
        if self._scan is None:
            why.append("no direct-usage scan recorded")
        elif self._scan:
            why.append(f"direct-usage scan has {len(self._scan)} finding(s)")
        return (not why, why)

    def remove_old(self) -> None:
        ok, why = self.can_remove_old()
        if not ok:
            raise BranchAbstractionError("removal refused: " + "; ".join(why))
        self._old = None
        self._removed = True

    def report(self) -> dict[str, Any]:
        return {
            "abstraction": self.abstraction,
            "phase": self.phase,
            "route": self._route,
            "callers": {"registered": len(self._callers), "migrated": sum(self._callers.values())},
            "equivalence": {k: dict(v) for k, v in self._equiv.items()},
            "shadow_divergences": len(self.divergences),
            "direct_usage_findings": None if self._scan is None else len(self._scan),
            "can_remove_old": self.can_remove_old()[0],
        }
