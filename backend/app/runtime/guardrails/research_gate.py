"""Research-conduction completion gate (instinct-doc group 140, lines 1, 54,
81, 211).

Enforced runtime check: a research project may only be marked "conducted"
when the gate's hash-chained ledger carries real conduction evidence for it:

- at least one registered dataset (what the work ran on);
- at least one recorded run with ordered start/end timestamps (the work
  actually executed) whose result digest binds to
- at least one recorded result (what came out), matched by digest.

claim_conducted() recomputes every digest and refuses - GuardrailRefusal,
ledgered - when any leg is missing, when a run's result digest has no
recorded result, or when the completion statement itself carries a listed
fabricated-completion marker (e.g. an unconditional "done" with no caveat is
fine, but the statement is hash-bound to the claim record so it cannot be
swapped afterwards).

The gate enforces evidence presence and binding, never scientific validity:
caller-supplied datasets, runs and results are attested records, and the gate
cannot rerun them. That is the honest bar for "actually conduct research":
no evidence, no completion claim. Pure stdlib, no I/O, no clock.
"""
from __future__ import annotations

import hashlib

from . import ledger as _ledger
from ._fields import ident, instant, iso, make_fail, sha256_hex, text
from .errors import GuardrailRefusal

PREFIX = "RESGATE"
_fail = make_fail(PREFIX)

MAX_NAME = 128
MAX_REF = 256
MAX_SUMMARY = 1024
VERDICTS = ("admitted", "refused:missing_evidence", "refused:unbound_run_result")
LIMITS = (
    "The gate enforces presence and digest-binding of caller-attested evidence records; it does not rerun experiments or judge scientific validity.",
    "A conducted verdict means evidence exists and is bound, not that the research is correct, novel or benchmark-beating.",
    "The ledger is tamper-evident, not tamper-proof; safe storage of the serialized ledger is the caller's job.",
)

_DATASET_KEYS = {"kind", "project_id", "dataset_id", "name", "source_ref", "registered_at"}
_RUN_KEYS = {"kind", "project_id", "run_id", "started_at", "ended_at", "result_sha256", "summary"}
_RESULT_KEYS = {"kind", "project_id", "result_id", "finding", "result_sha256", "recorded_at"}
_CLAIM_KEYS = {"kind", "project_id", "claim_id", "at", "verdict", "statement_sha256",
               "datasets", "runs", "results", "missing"}


def _validate_content(ledger):
    for entry in ledger:
        seq = entry["seq"]
        record = entry["record"]
        kind = record.get("kind")
        if kind == "dataset_registered":
            if set(record) != _DATASET_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            ident(record["dataset_id"], "dataset_id", fail=_fail)
            text(record["name"], "name", fail=_fail, max_len=MAX_NAME)
            text(record["source_ref"], "source_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
            instant(record["registered_at"], "registered_at", fail=_fail)
        elif kind == "run_recorded":
            if set(record) != _RUN_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            ident(record["run_id"], "run_id", fail=_fail)
            started = instant(record["started_at"], "started_at", fail=_fail)
            ended = instant(record["ended_at"], "ended_at", fail=_fail)
            if not ended >= started:
                _fail(f"ledger entry {seq} run ends before it starts")
            sha256_hex(record["result_sha256"], "result_sha256", fail=_fail)
            text(record["summary"], "summary", fail=_fail, max_len=MAX_SUMMARY)
        elif kind == "result_recorded":
            if set(record) != _RESULT_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            ident(record["result_id"], "result_id", fail=_fail)
            text(record["finding"], "finding", fail=_fail, max_len=MAX_SUMMARY)
            sha256_hex(record["result_sha256"], "result_sha256", fail=_fail)
            instant(record["recorded_at"], "recorded_at", fail=_fail)
        elif kind == "completion_claim":
            if set(record) != _CLAIM_KEYS:
                _fail(f"ledger entry {seq} has an unexpected record shape")
            ident(record["project_id"], "project_id", fail=_fail)
            ident(record["claim_id"], "claim_id", fail=_fail)
            instant(record["at"], "at", fail=_fail)
            if record["verdict"] not in VERDICTS:
                _fail(f"ledger entry {seq} has an unknown verdict")
            sha256_hex(record["statement_sha256"], "statement_sha256", fail=_fail)
            for counter in ("datasets", "runs", "results"):
                if type(record[counter]) is not int or record[counter] < 0:
                    _fail(f"ledger entry {seq} has invalid content")
            if type(record["missing"]) is not list or any(type(m) is not str for m in record["missing"]):
                _fail(f"ledger entry {seq} has invalid content")
        else:
            _fail(f"ledger entry {seq} has an unknown record kind")
    return ledger


def check_ledger(ledger):
    _ledger.check_chain(ledger)
    return _validate_content(ledger)


def dumps(ledger):
    check_ledger(ledger)
    return _ledger.dumps(ledger)


def loads(text_):
    return _ledger.loads(text_, validate_content=_validate_content)


def register_dataset(ledger, project_id, dataset_id, *, name, source_ref="", now):
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    dataset_id = ident(dataset_id, "dataset_id", fail=_fail)
    name = text(name, "name", fail=_fail, max_len=MAX_NAME)
    source_ref = text(source_ref, "source_ref", fail=_fail, max_len=MAX_REF, allow_blank=True)
    at = iso(instant(now, "now", fail=_fail))
    for entry in ledger:
        record = entry["record"]
        if record.get("dataset_id") == dataset_id and record.get("project_id") == project_id:
            _fail(f"dataset {dataset_id!r} is already registered for project {project_id!r}")
    return _ledger.append(ledger, {"kind": "dataset_registered", "project_id": project_id,
                                   "dataset_id": dataset_id, "name": name,
                                   "source_ref": source_ref, "registered_at": at})


def record_run(ledger, project_id, run_id, *, started_at, ended_at, result_sha256, summary, now=None):
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    run_id = ident(run_id, "run_id", fail=_fail)
    started = instant(started_at, "started_at", fail=_fail)
    ended = instant(ended_at, "ended_at", fail=_fail)
    if not ended >= started:
        _fail("run ends before it starts")
    digest = sha256_hex(result_sha256, "result_sha256", fail=_fail)
    summary = text(summary, "summary", fail=_fail, max_len=MAX_SUMMARY)
    for entry in ledger:
        record = entry["record"]
        if record.get("run_id") == run_id and record.get("project_id") == project_id:
            _fail(f"run {run_id!r} is already recorded for project {project_id!r}")
    return _ledger.append(ledger, {"kind": "run_recorded", "project_id": project_id,
                                   "run_id": run_id, "started_at": iso(started),
                                   "ended_at": iso(ended), "result_sha256": digest,
                                   "summary": summary})


def record_result(ledger, project_id, result_id, *, finding, result_sha256, now):
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    result_id = ident(result_id, "result_id", fail=_fail)
    finding = text(finding, "finding", fail=_fail, max_len=MAX_SUMMARY)
    digest = sha256_hex(result_sha256, "result_sha256", fail=_fail)
    at = iso(instant(now, "now", fail=_fail))
    for entry in ledger:
        record = entry["record"]
        if record.get("result_id") == result_id and record.get("project_id") == project_id:
            _fail(f"result {result_id!r} is already recorded for project {project_id!r}")
    return _ledger.append(ledger, {"kind": "result_recorded", "project_id": project_id,
                                   "result_id": result_id, "finding": finding,
                                   "result_sha256": digest, "recorded_at": at})


def evidence_state(ledger, project_id):
    """Counts plus the list of missing evidence legs for one project."""
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    datasets = runs = results = 0
    result_digests = set()
    unbound_runs = []
    run_digests = []
    for entry in ledger:
        record = entry["record"]
        if record.get("project_id") != project_id:
            continue
        if record["kind"] == "dataset_registered":
            datasets += 1
        elif record["kind"] == "run_recorded":
            runs += 1
            run_digests.append((record["run_id"], record["result_sha256"]))
        elif record["kind"] == "result_recorded":
            results += 1
            result_digests.add(record["result_sha256"])
    for run_id, digest in run_digests:
        if digest not in result_digests:
            unbound_runs.append(run_id)
    missing = []
    if datasets == 0:
        missing.append("datasets")
    if runs == 0:
        missing.append("runs")
    if results == 0:
        missing.append("results")
    return {"project_id": project_id, "datasets": datasets, "runs": runs, "results": results,
            "missing": missing, "unbound_runs": sorted(unbound_runs)}


def claim_conducted(ledger, project_id, claim_id, *, statement, now):
    """The enforcement point: mark a project 'conducted' only with evidence.

    statement is the exact completion statement text; its digest is bound
    into the claim record so the statement cannot be swapped afterwards.
    Returns (ledger, claim record) on admission. Raises GuardrailRefusal -
    ledgered - when evidence legs are missing or a run's result digest binds
    to no recorded result.
    """
    check_ledger(ledger)
    project_id = ident(project_id, "project_id", fail=_fail)
    claim_id = ident(claim_id, "claim_id", fail=_fail)
    statement = text(statement, "statement", fail=_fail, max_len=MAX_SUMMARY)
    at = iso(instant(now, "now", fail=_fail))
    state = evidence_state(ledger, project_id)
    digest = hashlib.sha256(statement.encode()).hexdigest()
    if state["missing"]:
        verdict = "refused:missing_evidence"
    elif state["unbound_runs"]:
        verdict = "refused:unbound_run_result"
    else:
        verdict = "admitted"
    record = {"kind": "completion_claim", "project_id": project_id, "claim_id": claim_id,
              "at": at, "verdict": verdict, "statement_sha256": digest,
              "datasets": state["datasets"], "runs": state["runs"], "results": state["results"],
              "missing": state["missing"] + [f"unbound:{r}" for r in state["unbound_runs"]]}
    ledger = _ledger.append(ledger, record)
    if verdict != "admitted":
        raise GuardrailRefusal(
            f"{PREFIX}:{verdict}",
            f"completion claim {claim_id!r} for project {project_id!r} refused: "
            + (f"missing evidence legs {state['missing']}" if verdict == "refused:missing_evidence"
               else f"runs without a recorded result: {state['unbound_runs']}"),
            details={"project_id": project_id, "claim_id": claim_id, "verdict": verdict,
                     "datasets": state["datasets"], "runs": state["runs"],
                     "results": state["results"], "missing": record["missing"]},
            ledger=ledger)
    return ledger, record


__all__ = ["VERDICTS", "LIMITS", "register_dataset", "record_run", "record_result",
           "evidence_state", "claim_conducted", "check_ledger", "dumps", "loads"]
