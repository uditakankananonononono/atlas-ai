"""S1.7 deploy-1000-builders scheduler tests. Stdlib only, hermetic.

The synthetic 1,000-job proof actually executes every job through the troop
roles (TemplatePlanner -> ActionWorker -> RuleReviewer) under a wave
scheduler with a configured concurrency cap; ledger and audit log integrity
is asserted, and concurrency is reported as numbers, never an "all" claim.
"""
import pytest

from app.troop.s1_7_scheduler import _ConcurrencyProbe, run_scheduler

AOF = {"as_of": "2026-10-11"}


def refuses(code, payload):
    with pytest.raises(ValueError) as exc:
        run_scheduler(payload)
    assert str(exc.value) == code


def scope_ok(result):
    scope = result["scope"]
    assert set(scope) == {"implemented", "not_implemented", "data_source", "as_of"}
    assert scope["data_source"] == "supplied+synthetic"
    assert scope["as_of"] == "2026-10-11"


class TestSynthetic1000Proof:
    P = dict(AOF, synthetic_jobs=1000, concurrency_cap=8, per_job_budget=4, global_budget=2000)

    def test_run_executes_1000_to_completion(self):
        r = run_scheduler(self.P)
        assert r["jobs_total"] == 1000
        assert r["completed"] == 1000 and r["failed"] == 0 and r["over_budget"] == 0
        assert r["waves"] == 125
        assert r["concurrency_cap"] == 8
        assert r["builder_slots_used"] == 8
        assert 1 <= r["measured_max_concurrent"] <= 8
        assert "configured_cap" in r["concurrency_basis"]
        assert r["proof"] == "synthetic_stub_execution"
        scope_ok(r)

    def test_ledger_and_audit_integrity(self):
        r = run_scheduler(self.P)
        ledger = r["ledger"]
        assert len(ledger) == 1000
        assert [row["job_id"] for row in ledger] == ["syn-%04d" % i for i in range(1000)]
        assert all(row["status"] == "completed" and row["attempts"] == 1 and row["cost"] == 1
                   for row in ledger)
        assert r["budget"] == {"per_job": 4, "global": 2000, "spent": 1000, "remaining": 1000}
        audit = r["audit_log"]
        assert len(audit) == 8
        assert sum(a["jobs_run"] for a in audit) == 1000
        assert all(a["completed"] == 125 and a["cost"] == 125 for a in audit)
        assert r["integrity"] == {"ledger_rows": 1000, "audit_jobs_sum": 1000,
                                  "spent_matches_ledger": True, "consistent": True}

    def test_outputs_are_real_role_results(self):
        r = run_scheduler(dict(AOF, synthetic_jobs=3, concurrency_cap=2,
                               per_job_budget=4, global_budget=10))
        assert r["outputs"]["syn-0000"] == {"totals": {"a": 0, "b": 2}}
        assert r["outputs"]["syn-0002"] == {"totals": {"a": 2, "b": 2}}

    def test_deterministic_except_instrumented_concurrency(self):
        a = run_scheduler(self.P)
        b = run_scheduler(self.P)
        a.pop("measured_max_concurrent")
        b.pop("measured_max_concurrent")
        assert a == b


class TestExplicitJobs:
    def test_wave_slot_assignment(self):
        r = run_scheduler(dict(AOF, concurrency_cap=2, per_job_budget=4, global_budget=10, jobs=[
            {"id": "j1", "kind": "sum_table", "rows": [{"a": 1}]},
            {"id": "j2", "kind": "sum_table", "rows": [{"a": 2}]},
            {"id": "j3", "kind": "sum_table", "rows": [{"a": 3}]}]))
        assert r["waves"] == 2
        assert [(row["job_id"], row["agent"], row["wave"]) for row in r["ledger"]] == [
            ("j1", "builder-000", 0), ("j2", "builder-001", 0), ("j3", "builder-000", 1)]
        assert r["outputs"]["j3"] == {"totals": {"a": 3}}
        scope_ok(r)

    def test_failed_job_retries_and_is_data(self):
        r = run_scheduler(dict(AOF, concurrency_cap=1, per_job_budget=4, global_budget=10,
                               jobs=[{"id": "bad", "kind": "text_stats", "text": "   "},
                                     {"id": "ok", "kind": "sum_table", "rows": [{"x": 5}]}]))
        by_id = {row["job_id"]: row for row in r["ledger"]}
        assert by_id["bad"]["status"] == "failed" and by_id["bad"]["attempts"] == 2
        assert by_id["ok"]["status"] == "completed"
        assert r["completed"] == 1 and r["failed"] == 1

    def test_per_job_budget_marks_over_budget(self):
        r = run_scheduler(dict(AOF, concurrency_cap=2, per_job_budget=1, global_budget=10, jobs=[
            {"id": "cheap", "kind": "sum_table", "rows": [{"a": 1}], "cost": 1},
            {"id": "pricey", "kind": "sum_table", "rows": [{"a": 1}], "cost": 4}]))
        by_id = {row["job_id"]: row for row in r["ledger"]}
        assert by_id["pricey"]["status"] == "over_budget" and by_id["pricey"]["attempts"] == 0
        assert by_id["cheap"]["status"] == "completed"
        assert r["budget"]["spent"] == 1


class TestRefusals:
    def test_overcap_synthetic_and_explicit(self):
        refuses("FLEET_REFUSED_OVERCAP:queue_capacity_is_1000",
                dict(AOF, synthetic_jobs=1001, concurrency_cap=8, per_job_budget=1, global_budget=10**6))
        refuses("FLEET_REFUSED_OVERCAP:queue_capacity_is_1000",
                dict(AOF, concurrency_cap=8, per_job_budget=1, global_budget=10**6,
                     jobs=[{"id": "j%d" % i, "kind": "sum_table", "rows": [{"a": 1}]}
                           for i in range(1001)]))

    def test_global_budget_refusal(self):
        refuses("FLEET_REFUSED_BUDGET:global_budget_exceeded",
                dict(AOF, synthetic_jobs=5, concurrency_cap=2, per_job_budget=4, global_budget=3))

    def test_spend_refused(self):
        for key in ("purchase", "spend", "real_llm", "live_api", "outreach", "live_accounts"):
            refuses("FLEET_REFUSED_SPEND:synthetic_stubs_only_no_live_accounts_outreach_or_spend",
                    dict(AOF, synthetic_jobs=1, concurrency_cap=1, per_job_budget=1,
                         global_budget=1, **{key: True}))

    def test_job_source_exactly_one(self):
        code = "FLEET_REFUSED_JOB_SOURCE:choose_exactly_one_of_jobs_or_synthetic_jobs"
        refuses(code, dict(AOF, concurrency_cap=1, per_job_budget=1, global_budget=1))
        refuses(code, dict(AOF, concurrency_cap=1, per_job_budget=1, global_budget=1,
                           jobs=[], synthetic_jobs=0))

    def test_validation(self):
        refuses("FLEET_REFUSED_BAD_TYPE:payload", "nope")
        refuses("FLEET_REFUSED_UNKNOWN_FIELDS:payload",
                dict(AOF, synthetic_jobs=1, concurrency_cap=1, per_job_budget=1,
                     global_budget=1, mystery=1))
        refuses("FLEET_REFUSED_EMPTY_FIELD:concurrency_cap",
                dict(AOF, synthetic_jobs=1, per_job_budget=1, global_budget=1))
        refuses("FLEET_REFUSED_UNSAFE_CHARS:as_of",
                dict(as_of="2026-10-11\u2028", synthetic_jobs=1, concurrency_cap=1,
                     per_job_budget=1, global_budget=1))
        refuses("FLEET_REFUSED_OUT_OF_RANGE:concurrency_cap",
                dict(AOF, synthetic_jobs=1, concurrency_cap=257, per_job_budget=1, global_budget=1))
        refuses("FLEET_REFUSED_BAD_TYPE:concurrency_cap",
                dict(AOF, synthetic_jobs=1, concurrency_cap=True, per_job_budget=1, global_budget=1))
        refuses("FLEET_REFUSED_DUPLICATE:dup",
                dict(AOF, concurrency_cap=1, per_job_budget=1, global_budget=9,
                     jobs=[{"id": "dup", "kind": "sum_table", "rows": [{"a": 1}]},
                           {"id": "dup", "kind": "sum_table", "rows": [{"a": 2}]}]))
        refuses("FLEET_REFUSED_BAD_KIND:weird",
                dict(AOF, concurrency_cap=1, per_job_budget=1, global_budget=9,
                     jobs=[{"id": "j", "kind": "weird"}]))


class TestBoundaries:
    def test_hi_bounds_accepted(self):
        r = run_scheduler(dict(AOF, synthetic_jobs=2, concurrency_cap=256,
                               per_job_budget=10**6, global_budget=10**12))
        assert r["completed"] == 2 and r["concurrency_cap"] == 256

    def test_cost_hi_bound_accepted(self):
        r = run_scheduler(dict(AOF, concurrency_cap=1, per_job_budget=10**6, global_budget=10**12,
                               jobs=[{"id": "j1", "kind": "sum_table", "rows": [{"a": 1}],
                                      "cost": 1000}]))
        assert r["completed"] == 1 and r["budget"]["spent"] == 1000

    def test_cost_zero_accepted(self):
        r = run_scheduler(dict(AOF, concurrency_cap=1, per_job_budget=0, global_budget=0,
                               jobs=[{"id": "j1", "kind": "sum_table", "rows": [{"a": 1}],
                                      "cost": 0}]))
        assert r["completed"] == 1 and r["budget"]["spent"] == 0

    def test_global_budget_exact_equality_runs(self):
        r = run_scheduler(dict(AOF, synthetic_jobs=5, concurrency_cap=2,
                               per_job_budget=4, global_budget=5))
        assert r["completed"] == 5 and r["budget"]["spent"] == 5

    def test_ledger_canonical_sort(self):
        r = run_scheduler(dict(AOF, concurrency_cap=1, per_job_budget=4, global_budget=10, jobs=[
            {"id": "j2", "kind": "sum_table", "rows": [{"a": 2}]},
            {"id": "j1", "kind": "sum_table", "rows": [{"a": 1}]}]))
        assert [row["job_id"] for row in r["ledger"]] == ["j1", "j2"]
        assert [row["wave"] for row in r["ledger"]] == [0, 1]

    def test_failed_job_spend_is_debited(self):
        r = run_scheduler(dict(AOF, concurrency_cap=1, per_job_budget=4, global_budget=10, jobs=[
            {"id": "bad", "kind": "text_stats", "text": "  ", "cost": 2},
            {"id": "ok", "kind": "sum_table", "rows": [{"a": 1}], "cost": 1}]))
        assert r["budget"]["spent"] == 3 and r["budget"]["remaining"] == 7

    def test_probe_tracks_max_seen(self):
        probe = _ConcurrencyProbe()
        probe.tick(); probe.tick(); probe.tock()
        assert probe.max_seen == 2 and probe.in_flight == 1
        probe.tock()
        assert probe.max_seen == 2 and probe.in_flight == 0
        probe.tick()
        assert probe.max_seen == 2 and probe.in_flight == 1
