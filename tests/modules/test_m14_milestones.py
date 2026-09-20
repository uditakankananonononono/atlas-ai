"""Tests for the Module 14 milestone engine."""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m14_project_builder.milestones import (
    CycleError,
    DependencyError,
    Milestone,
    MilestoneStatus,
    TransitionError,
    advance_status,
    can_complete,
    compute_progress,
    detect_slippage,
    evaluate_acceptance,
    instantiate_template,
    list_template_kinds,
    replan,
    schedule_milestones,
    topological_order,
    validate_dependencies,
)

UTC = timezone.utc
T0 = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)


def ms(mid, deps=(), effort=8.0, status=MilestoneStatus.PENDING, progress=0.0,
       phase="build", criteria=()):
    return Milestone(
        milestone_id=mid,
        project_id="p1",
        title=f"Milestone {mid}",
        phase=phase,
        depends_on=tuple(deps),
        estimated_effort_hours=effort,
        status=status,
        progress=progress,
        acceptance_criteria=tuple(criteria),
    )


class TestMilestoneValidation:
    def test_rejects_self_dependency(self):
        with pytest.raises(DependencyError):
            ms("a", deps=("a",))

    def test_rejects_duplicate_dependency(self):
        with pytest.raises(DependencyError):
            ms("a", deps=("b", "b"))

    def test_rejects_negative_effort(self):
        with pytest.raises(ValueError):
            ms("a", effort=-1)

    def test_rejects_progress_out_of_range(self):
        with pytest.raises(ValueError):
            ms("a", progress=1.5)

    def test_rejects_naive_planned_start(self):
        with pytest.raises(ValueError):
            Milestone(
                milestone_id="a", project_id="p1", title="t", phase="p",
                planned_start=datetime(2026, 9, 21, 9, 0),
            )

    def test_rejects_end_before_start(self):
        with pytest.raises(ValueError):
            Milestone(
                milestone_id="a", project_id="p1", title="t", phase="p",
                planned_start=T0, planned_end=T0 - timedelta(hours=1),
            )

    def test_unknown_dependency_reference(self):
        with pytest.raises(DependencyError):
            validate_dependencies([ms("a", deps=("ghost",))])

    def test_duplicate_ids_rejected(self):
        with pytest.raises(DependencyError):
            validate_dependencies([ms("a"), ms("a")])


class TestTopologicalOrder:
    def test_linear_chain(self):
        order = topological_order([ms("c", deps=("b",)), ms("a"), ms("b", deps=("a",))])
        assert order == ["a", "b", "c"]

    def test_diamond(self):
        order = topological_order([
            ms("d", deps=("b", "c")), ms("b", deps=("a",)),
            ms("c", deps=("a",)), ms("a"),
        ])
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_cycle_detected(self):
        with pytest.raises(CycleError) as exc:
            topological_order([ms("a", deps=("b",)), ms("b", deps=("a",))])
        assert set(exc.value.remaining_ids) == {"a", "b"}


class TestScheduling:
    def test_chain_schedules_sequentially(self):
        scheduled = schedule_milestones(
            [ms("a", effort=8), ms("b", deps=("a",), effort=16)], T0, hours_per_day=8
        )
        a, b = scheduled
        assert a.planned_start == T0
        assert a.planned_end == T0 + timedelta(days=1)
        assert b.planned_start == a.planned_end
        assert b.planned_end == a.planned_end + timedelta(days=2)

    def test_independent_milestones_share_start(self):
        scheduled = schedule_milestones([ms("a"), ms("b")], T0)
        assert all(m.planned_start == T0 for m in scheduled)

    def test_zero_effort_gate(self):
        scheduled = schedule_milestones(
            [ms("a", effort=8), ms("gate", deps=("a",), effort=0)], T0
        )
        gate = next(m for m in scheduled if m.milestone_id == "gate")
        assert gate.planned_start == gate.planned_end

    def test_join_waits_for_latest_dependency(self):
        scheduled = schedule_milestones(
            [ms("a", effort=8), ms("b", effort=24), ms("c", deps=("a", "b"))], T0
        )
        b = next(m for m in scheduled if m.milestone_id == "b")
        c = next(m for m in scheduled if m.milestone_id == "c")
        assert c.planned_start == b.planned_end

    def test_rejects_naive_start(self):
        with pytest.raises(ValueError):
            schedule_milestones([ms("a")], datetime(2026, 9, 21))

    def test_rejects_nonpositive_hours_per_day(self):
        with pytest.raises(ValueError):
            schedule_milestones([ms("a")], T0, hours_per_day=0)


class TestStatusTransitions:
    def test_start_stamps_actual_start(self):
        m = advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0)
        assert m.status == MilestoneStatus.IN_PROGRESS
        assert m.actual_start == T0

    def test_complete_stamps_end_and_full_progress(self):
        m = advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0)
        m = advance_status(m, MilestoneStatus.COMPLETED, T0 + timedelta(hours=8))
        assert m.actual_end == T0 + timedelta(hours=8)
        assert m.progress == 1.0

    def test_illegal_transition_rejected(self):
        with pytest.raises(TransitionError):
            advance_status(ms("a"), MilestoneStatus.COMPLETED, T0)

    def test_terminal_is_final(self):
        done = advance_status(advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0),
                              MilestoneStatus.COMPLETED, T0)
        with pytest.raises(TransitionError):
            advance_status(done, MilestoneStatus.IN_PROGRESS, T0)

    def test_failed_can_retry_to_pending(self):
        m = advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0)
        m = advance_status(m, MilestoneStatus.FAILED, T0)
        m = advance_status(m, MilestoneStatus.PENDING, T0)
        assert m.status == MilestoneStatus.PENDING
        assert m.progress == 0.0

    def test_blocked_releases_to_pending(self):
        m = advance_status(ms("a"), MilestoneStatus.BLOCKED, T0)
        m = advance_status(m, MilestoneStatus.PENDING, T0)
        assert m.status == MilestoneStatus.PENDING


class TestProgress:
    def test_effort_weighted_overall(self):
        report = compute_progress([
            ms("a", effort=8, status=MilestoneStatus.COMPLETED),
            ms("b", effort=8, status=MilestoneStatus.IN_PROGRESS, progress=0.5),
            ms("c", effort=24),
        ])
        # (8*1 + 8*0.5 + 24*0) / 40 = 0.3
        assert report.overall_progress == pytest.approx(0.3)
        assert report.total_effort_hours == 40
        assert report.completed_effort_hours == 8
        assert report.counts_by_status == {
            "completed": 1, "in_progress": 1, "pending": 1,
        }

    def test_zero_effort_falls_back_to_mean(self):
        report = compute_progress([
            ms("a", effort=0, status=MilestoneStatus.COMPLETED),
            ms("b", effort=0),
        ])
        assert report.overall_progress == pytest.approx(0.5)

    def test_per_phase_breakdown(self):
        report = compute_progress([
            ms("a", phase="research", status=MilestoneStatus.COMPLETED),
            ms("b", phase="writing", progress=0.25),
        ])
        assert report.per_phase["research"] == 1.0
        assert report.per_phase["writing"] == pytest.approx(0.25)

    def test_empty_set_rejected(self):
        with pytest.raises(ValueError):
            compute_progress([])

    def test_skipped_counts_as_done(self):
        report = compute_progress([
            ms("a", status=MilestoneStatus.COMPLETED),
            ms("b", status=MilestoneStatus.SKIPPED),
        ])
        assert report.overall_progress == 1.0
        assert report.completed_effort_hours == 16.0


class TestSlippage:
    def test_overdue_detected(self):
        scheduled = schedule_milestones([ms("a", effort=8)], T0)
        findings = detect_slippage(scheduled, T0 + timedelta(days=2))
        assert len(findings) == 1
        assert findings[0].kind == "overdue"
        assert findings[0].overdue_by == timedelta(days=1)

    def test_behind_schedule_detected(self):
        m = schedule_milestones(
            [ms("a", effort=8, status=MilestoneStatus.IN_PROGRESS, progress=0.1)], T0
        )[0]
        halfway = T0 + timedelta(hours=12)  # expected ~50%
        findings = detect_slippage([m], halfway)
        assert len(findings) == 1
        assert findings[0].kind == "behind_schedule"
        assert findings[0].progress_gap == pytest.approx(0.4, abs=0.01)

    def test_on_track_is_quiet(self):
        m = schedule_milestones(
            [ms("a", effort=8, status=MilestoneStatus.IN_PROGRESS, progress=0.5)], T0
        )[0]
        findings = detect_slippage([m], T0 + timedelta(hours=12))
        assert findings == []

    def test_terminal_milestones_ignored(self):
        done = advance_status(advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0),
                              MilestoneStatus.COMPLETED, T0)
        done = schedule_milestones([done], T0)[0]
        assert detect_slippage([done], T0 + timedelta(days=30)) == []


class TestReplan:
    def test_completed_anchor_dependents(self):
        a = advance_status(ms("a", effort=8), MilestoneStatus.IN_PROGRESS, T0)
        a = advance_status(a, MilestoneStatus.COMPLETED, T0 + timedelta(days=3))
        b = ms("b", deps=("a",), effort=8)
        planned = schedule_milestones([a, b], T0)
        result = replan(planned, T0 + timedelta(days=3))
        new_b = next(m for m in result.milestones if m.milestone_id == "b")
        assert new_b.planned_start == T0 + timedelta(days=3)

    def test_shifts_recorded(self):
        planned = schedule_milestones([ms("a", effort=8), ms("b", deps=("a",), effort=8)], T0)
        result = replan(planned, T0 + timedelta(days=1))
        assert result.shifts["a"] == timedelta(days=1)
        assert result.shifts["b"] == timedelta(days=1)

    def test_in_progress_keeps_actual_start_and_remaining_work(self):
        m = ms("a", effort=16, status=MilestoneStatus.IN_PROGRESS, progress=0.5)
        m = advance_status(ms("a", effort=8), MilestoneStatus.IN_PROGRESS, T0)
        m = Milestone(**{**m.__dict__, "estimated_effort_hours": 16, "progress": 0.5})
        planned = schedule_milestones([m], T0)
        result = replan(planned, T0 + timedelta(days=2))
        new_a = result.milestones[0]
        assert new_a.planned_start == T0  # actual start preserved
        # 8h remaining at 8h/day from the anchor (day 2) -> ends day 3
        assert new_a.planned_end == T0 + timedelta(days=3)


class TestAcceptance:
    def test_evaluate_acceptance_splits_satisfied_and_missing(self):
        m = ms("a", criteria=("tests_green", "docs_written"))
        report = evaluate_acceptance(m, {"tests_green": "suite: 42 passed"})
        assert not report.passed
        assert report.satisfied == ("tests_green",)
        assert report.missing == ("docs_written",)

    def test_blank_evidence_does_not_count(self):
        m = ms("a", criteria=("tests_green",))
        assert not evaluate_acceptance(m, {"tests_green": "   "}).passed

    def test_can_complete_requires_dependencies_done(self):
        a = ms("a")
        b = ms("b", deps=("a",))
        ok, reason = can_complete(b, [a, b], {})
        assert not ok and "pending" in reason

    def test_can_complete_requires_acceptance_evidence(self):
        a = advance_status(advance_status(ms("a"), MilestoneStatus.IN_PROGRESS, T0),
                           MilestoneStatus.COMPLETED, T0)
        b = ms("b", deps=("a",), criteria=("tests_green",))
        ok, reason = can_complete(b, [a, b], {})
        assert not ok and "tests_green" in reason
        ok, reason = can_complete(b, [a, b], {"tests_green": "42 passed"})
        assert ok


class TestTemplates:
    def test_kinds_listed(self):
        kinds = list_template_kinds()
        assert kinds == ("coding_project", "data_analysis", "research_project")

    def test_unknown_kind_raises(self):
        with pytest.raises(KeyError):
            instantiate_template("nope", "p1", T0)

    @pytest.mark.parametrize("kind", list_template_kinds())
    def test_templates_instantiate_valid_schedules(self, kind):
        plan = instantiate_template(kind, "p1", T0, hours_per_day=8)
        assert len(plan) == len({m.milestone_id for m in plan})
        validate_dependencies(plan)
        for m in plan:
            assert m.project_id == "p1"
            assert m.planned_start is not None and m.planned_end is not None
            assert m.planned_end >= m.planned_start
            for dep in m.depends_on:
                d = next(x for x in plan if x.milestone_id == dep)
                assert m.planned_start >= d.planned_end

    def test_research_template_chains_writing_after_analysis(self):
        plan = instantiate_template("research_project", "p1", T0)
        by_key = {m.milestone_id.split(":")[1]: m for m in plan}
        assert by_key["paper_draft"].planned_start >= by_key["analysis"].planned_end
        assert by_key["submission_package"].planned_start >= max(
            by_key["paper_draft"].planned_end, by_key["poster"].planned_end
        )
