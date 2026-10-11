"""Gate for per-module self-improvement changes (C6). See docs/SELF_IMPROVE_GATE.md.

Stdlib only. Authorizes a change to exist on a self-improve branch only when
real test and mutation evidence is attached. It never merges, never touches
git, and never writes outside its own state directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .self_eval import SelfEvalError, run_pytest

CODES = ("PLAN_REFUSED_UNGATED", "PLAN_REFUSED_REGRESSION", "PLAN_REFUSED_BUDGET",
         "PLAN_REFUSED_BAD_PLAN", "PLAN_REFUSED_SELF_MERGE", "PLAN_REFUSED_OUTSIDE_SANDBOX")
_MAIN_NAMES = {"main", "master", "origin/main", "origin/master", "refs/heads/main", "refs/heads/master", "HEAD"}
BRANCH_PREFIX = "selfimprove/"


class PlanRefused(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class GateLedgerError(ValueError):
    pass


@dataclass(frozen=True)
class ChangePlan:
    module_slug: str
    feature: str
    branch: str
    files: tuple
    target: str = "branch"

    def digest(self) -> str:
        body = json.dumps({"module": self.module_slug, "feature": self.feature, "branch": self.branch,
                           "files": sorted(self.files), "target": self.target}, sort_keys=True)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MutationRun:
    total: int
    killed: int
    survived: int
    nomatch: int
    timeouts: int
    results: tuple


@dataclass(frozen=True)
class GateEvidence:
    plan_digest: str
    tests: object
    mutation: object
    baseline_passed: int | None = None
    equivalent_declared: int = 0


@dataclass(frozen=True)
class Authorization:
    plan: ChangePlan
    digest: str
    at: float

    @property
    def merge_allowed(self) -> bool:
        return False


def _blank(v) -> bool:
    return not isinstance(v, str) or not v.strip()


class ImprovementGate:
    def __init__(self, module_slug: str, state_dir, *, sandbox_roots, max_changes_per_window: int = 3,
                 window_s: float = 86400, max_files_per_change: int = 10, now=time.time) -> None:
        safe = "".join(c for c in str(module_slug) if c.isalnum() or c in "-_")
        if not module_slug or safe != module_slug:
            raise ValueError(f"unsafe module slug {module_slug!r}")
        roots = tuple(sandbox_roots)
        if not roots or any((not isinstance(r, str)) or not r.endswith("/") or r.startswith("/") for r in roots):
            raise ValueError("sandbox_roots must be non-empty relative prefixes ending in '/'")
        if max_changes_per_window < 1 or window_s <= 0 or max_files_per_change < 1:
            raise ValueError("budget values must be positive")
        self.module_slug = module_slug
        self._roots = roots
        self._max_changes = max_changes_per_window
        self._window = window_s
        self._max_files = max_files_per_change
        self._now = now
        d = Path(state_dir)
        d.mkdir(parents=True, exist_ok=True)
        self._ledger_path = d / f"{module_slug}.improvement-ledger.jsonl"
        self._changelog_path = d / f"{module_slug}.changelog.md"

    def ledger(self) -> list:
        if not self._ledger_path.exists():
            return []
        out = []
        for n, line in enumerate(self._ledger_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise GateLedgerError(f"corrupt ledger line {n}: {exc}") from exc
        return out

    def changelog(self) -> str:
        return self._changelog_path.read_text(encoding="utf-8") if self._changelog_path.exists() else ""

    def _append(self, rec: dict) -> None:
        with self._ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def _validate_plan(self, plan) -> None:
        if not isinstance(plan, ChangePlan):
            raise PlanRefused("PLAN_REFUSED_BAD_PLAN", "plan is not a ChangePlan")
        if (_blank(plan.feature) or _blank(plan.module_slug) or _blank(plan.branch) or len(plan.files) == 0
                or any(_blank(f) for f in plan.files)):
            raise PlanRefused("PLAN_REFUSED_BAD_PLAN", "feature, module, branch and files must be non-empty")
        if plan.module_slug != self.module_slug:
            raise PlanRefused("PLAN_REFUSED_BAD_PLAN", "plan module does not match this gate")
        if plan.target == "main":
            raise PlanRefused("PLAN_REFUSED_SELF_MERGE", "a change may not target main")
        if plan.target != "branch":
            raise PlanRefused("PLAN_REFUSED_BAD_PLAN", "target must be 'branch'")
        if plan.branch in _MAIN_NAMES:
            raise PlanRefused("PLAN_REFUSED_SELF_MERGE", "a change may not use the main branch")
        if not plan.branch.startswith(BRANCH_PREFIX):
            raise PlanRefused("PLAN_REFUSED_BAD_PLAN", f"branch must start with {BRANCH_PREFIX!r}")
        for f in plan.files:
            parts = f.split("/")
            if ("\\" in f or f.startswith("/") or f.startswith("~") or ".." in parts or "." in parts
                    or not any(f.startswith(r) and len(f) > len(r) for r in self._roots)):
                raise PlanRefused("PLAN_REFUSED_OUTSIDE_SANDBOX", f"file outside sandbox: {f!r}")
        if len(plan.files) > self._max_files:
            raise PlanRefused("PLAN_REFUSED_BUDGET", f"more than {self._max_files} files in one change")

    def _check_evidence(self, plan: ChangePlan, ev) -> None:
        if ev is None or ev.tests is None or ev.mutation is None:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "tests and mutation evidence are both required")
        if ev.plan_digest != plan.digest():
            raise PlanRefused("PLAN_REFUSED_UNGATED", "evidence is not for this plan")
        m, t = ev.mutation, ev.tests
        if m.total <= 0:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "no mutants were run")
        if m.killed + m.survived + m.nomatch + m.timeouts != m.total:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "mutation counts do not add up")
        if m.nomatch > 0:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "some mutants did not apply")
        if ev.equivalent_declared < 0 or ev.equivalent_declared > m.survived:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "declared equivalents exceed survivors")
        if t.returncode != 0 or (t.failed or 0) > 0 or (t.errors or 0) > 0:
            raise PlanRefused("PLAN_REFUSED_REGRESSION", "tests are failing")
        if not t.passed:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "no passing tests were counted")
        if ev.baseline_passed is not None and t.passed < ev.baseline_passed:
            raise PlanRefused("PLAN_REFUSED_REGRESSION", "passing test count fell below the baseline")
        if m.survived - ev.equivalent_declared > 0:
            raise PlanRefused("PLAN_REFUSED_REGRESSION", "mutants survived beyond declared equivalents")

    def authorize(self, plan, evidence) -> Authorization:
        history = self.ledger()
        now = self._now()
        digest = plan.digest() if isinstance(plan, ChangePlan) else None
        try:
            self._validate_plan(plan)
            self._check_evidence(plan, evidence)
            used = sum(1 for e in history if e.get("event") == "authorized" and e["at"] > now - self._window)
            if used >= self._max_changes:
                raise PlanRefused("PLAN_REFUSED_BUDGET", f"{used} changes already authorized in the window")
        except PlanRefused as exc:
            self._append({"event": "refused", "at": now, "code": exc.code, "detail": exc.detail,
                          "digest": digest, "module": self.module_slug})
            raise
        t, m = evidence.tests, evidence.mutation
        self._append({"event": "authorized", "at": now, "module": self.module_slug, "feature": plan.feature,
                      "branch": plan.branch, "files": sorted(plan.files), "digest": digest,
                      "tests_passed": t.passed, "mutants_total": m.total, "mutants_killed": m.killed + m.timeouts,
                      "mutants_survived": m.survived, "equivalent_declared": evidence.equivalent_declared,
                      "merge_allowed": False})
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        with self._changelog_path.open("a", encoding="utf-8") as fh:
            fh.write(f"- {stamp} {self.module_slug}: {plan.feature} on branch {plan.branch} "
                     f"(digest {digest[:12]}): {t.passed} tests passed, {m.killed + m.timeouts}/{m.total} mutants killed "
                     f"({m.survived} survived, {evidence.equivalent_declared} declared equivalent). "
                     "Merge to main still needs human approval.\n")
        return Authorization(plan, digest, now)


def _pytest_nobytecode(paths, **kw):
    """run_pytest with PYTHONDONTWRITEBYTECODE=1 (same effect as python -B) so a same-size
    same-second mutant can never be hidden by a stale .pyc. Restores the environment."""
    old = os.environ.get("PYTHONDONTWRITEBYTECODE")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return run_pytest(paths, **kw)
    finally:
        if old is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = old


def run_mutations(target_rel: str, mutants, pytest_paths, *, cwd, python: str = sys.executable,
                  timeout: float = 120) -> MutationRun:
    mutants = list(mutants)
    if not mutants or any(not (isinstance(x, tuple) and len(x) == 2 and all(isinstance(y, str) for y in x) and x[0])
                          for x in mutants):
        raise ValueError("mutants must be a non-empty list of (old, new) string pairs with non-empty old")
    root = Path(cwd)
    if (not isinstance(target_rel, str) or target_rel.startswith("/") or ".." in target_rel.split("/")
            or not (root / target_rel).is_file()):
        raise ValueError("target must be an existing relative file under cwd")
    with tempfile.TemporaryDirectory(prefix="gate_mut_") as tmp:
        work = Path(tmp) / "proj"
        shutil.copytree(root, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        target = work / target_rel
        original = target.read_text(encoding="utf-8")
        base = _pytest_nobytecode(pytest_paths, cwd=work, python=python, timeout=timeout)
        if base.returncode != 0:
            raise PlanRefused("PLAN_REFUSED_UNGATED", "baseline tests fail before any mutation")
        results, counts = [], {"killed": 0, "survived": 0, "nomatch": 0, "timeout": 0}
        for i, (old, new) in enumerate(mutants):
            if original.count(old) == 0:
                outcome = "nomatch"
            else:
                target.write_text(original.replace(old, new, 1), encoding="utf-8")
                try:
                    r = _pytest_nobytecode(pytest_paths, cwd=work, python=python, timeout=timeout)
                    outcome = "killed" if r.returncode != 0 else "survived"
                except SelfEvalError:
                    outcome = "timeout"
                finally:
                    target.write_text(original, encoding="utf-8")
            counts[outcome] += 1
            results.append({"index": i, "outcome": outcome, "old": old[:60], "new": new[:60]})
    return MutationRun(len(mutants), counts["killed"], counts["survived"], counts["nomatch"],
                       counts["timeout"], tuple(results))
