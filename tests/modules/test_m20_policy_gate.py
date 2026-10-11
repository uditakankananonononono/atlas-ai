"""M20-POL policy gate: a ToolSpec's declared effect class is mapped onto the
canonical c30.policy standing refusals at dispatch - deny-only, BEFORE the
precondition check. No declared class (or 'none') means no policy call; an
unknown declared class refuses closed. preflight reports refusals inside its
existing issues/missing structure with the row shape unchanged; score_all
scores a refusal as blocked and never raises. The gate can only deny: it
never turns a failed precondition into a pass."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.safety import SafetyGate
from app.modules.m20_general_cognitive_worker.schemas import Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.tools import (
    ToolBlockedError, ToolDispatcher, ToolRegistry,
)
from app.modules.m20_general_cognitive_worker.tool_selection import ToolSelector

EFFECT_CODES = {
    "spend": "POLICY_REFUSED_SPEND",
    "outreach": "POLICY_REFUSED_OUTREACH",
    "account": "POLICY_REFUSED_FAKEACCT",
    "post": "POLICY_REFUSED_AUTOPOST",
    "trade": "POLICY_REFUSED_TRADE",
    "scrape": "POLICY_REFUSED_SCRAPE",
}


async def _handler(args):
    return {"ok": True}


def make_dispatcher(spec_kwargs):
    registry = ToolRegistry()
    registry.register(ToolSpec(name="t", description="t", **spec_kwargs), _handler)
    return ToolDispatcher(registry, SafetyGate())


class TestDispatchGate:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("effect,code", sorted(EFFECT_CODES.items()))
    async def test_effect_classes_blocked_with_policy_codes(self, effect, code):
        dispatcher = make_dispatcher({"effect_class": effect})
        with pytest.raises(ToolBlockedError) as exc:
            await dispatcher.dispatch("t", {})
        assert exc.value.reasons == [code]

    @pytest.mark.asyncio
    async def test_no_declared_effect_unchanged(self):
        dispatcher = make_dispatcher({})
        record = await dispatcher.dispatch("t", {})
        assert record.succeeded

    @pytest.mark.asyncio
    async def test_effect_none_makes_no_policy_call(self):
        dispatcher = make_dispatcher({"effect_class": "none"})
        record = await dispatcher.dispatch("t", {})
        assert record.succeeded

    @pytest.mark.asyncio
    async def test_unknown_declared_class_refused(self):
        dispatcher = make_dispatcher({"effect_class": "quantum"})
        with pytest.raises(ToolBlockedError) as exc:
            await dispatcher.dispatch("t", {})
        assert exc.value.reasons == ["POLICY_REFUSED_UNKNOWN:quantum"]

    @pytest.mark.asyncio
    async def test_gate_runs_before_preconditions(self):
        dispatcher = make_dispatcher({"effect_class": "spend", "preconditions": ["ready"]})
        with pytest.raises(ToolBlockedError) as exc:
            await dispatcher.dispatch("t", {}, context={})
        assert exc.value.reasons == ["POLICY_REFUSED_SPEND"]

    @pytest.mark.asyncio
    async def test_deny_only_never_widens(self):
        # A satisfied context never overrides a policy refusal...
        dispatcher = make_dispatcher({"effect_class": "spend", "preconditions": ["ready"]})
        with pytest.raises(ToolBlockedError) as exc:
            await dispatcher.dispatch("t", {}, context={"ready": True})
        assert exc.value.reasons == ["POLICY_REFUSED_SPEND"]
        # ...and a passing policy gate never fixes a failed precondition.
        dispatcher = make_dispatcher({"preconditions": ["ready"]})
        with pytest.raises(ToolBlockedError) as exc:
            await dispatcher.dispatch("t", {}, context={"ready": 1})
        assert exc.value.reasons == ["missing precondition: ready"]


class TestPreflightReport:
    def _runtime(self):
        engine = create_engine("sqlite:///:memory:",
                               connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        repo = GCWRepository(engine)
        repo.create_schema()
        return GCWRuntime(repo, planner_model=None, approval_gate=None,
                          require_method_review=True)

    def test_preflight_reports_refusal_with_identical_row_shape(self):
        runtime = self._runtime()
        runtime.tools.register(
            ToolSpec(name="spendtool", description="spends", risk=Risk.EXTERNAL,
                     effect_class="spend"), _handler)
        task = runtime.submit_goal("buy the thing", run_immediately=False)
        runtime.prepare_supplied_plan(task.id, steps=[{"title": "buy", "tool": "spendtool"}])
        report = runtime.preflight_task(task.id)
        row = report["steps"][0]
        assert set(row) == {"step_id", "tool", "issues", "missing_preconditions",
                            "argument_check", "effective_risk"}
        assert "POLICY_REFUSED_SPEND" in row["issues"]
        assert report["ready_for_dispatch"] is False
        assert report["external_actions_executed"] is False
        assert report["approval_granted"] is False
        assert not runtime.safety.approvals.requests

    def test_preflight_clean_tool_reports_no_refusal(self):
        runtime = self._runtime()
        runtime.tools.register(
            ToolSpec(name="plain", description="reads", risk=Risk.READ), _handler)
        task = runtime.submit_goal("read the thing", run_immediately=False)
        runtime.prepare_supplied_plan(task.id, steps=[{"title": "read", "tool": "plain"}])
        row = runtime.preflight_task(task.id)["steps"][0]
        assert row["issues"] == []


class TestScoreAll:
    def _selector(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="spendtool", description="buys things",
                                   effect_class="spend"), _handler)
        registry.register(ToolSpec(name="reader", description="reads things"), _handler)
        return ToolSelector(registry)

    def test_refusal_scores_blocked_never_raises(self):
        scores = self._selector().score_all("buy supplies", context={})
        by_name = {s.tool_name: s for s in scores}
        spend = by_name["spendtool"]
        assert spend.preconditions_met is False
        assert spend.missing_preconditions == ["POLICY_REFUSED_SPEND"]
        assert by_name["reader"].preconditions_met is True
        assert by_name["reader"].missing_preconditions == []

    def test_satisfied_context_never_unblocks_policy(self):
        scores = self._selector().score_all("buy supplies", context={"ready": True})
        spend = {s.tool_name: s for s in scores}["spendtool"]
        assert spend.preconditions_met is False
        # the 0.5 blocked penalty is applied: total recomputes from the
        # score's own decomposition with the penalty included
        expected = (0.45 * spend.capability_match
                    + 0.30 * spend.description_similarity
                    + 0.15 * spend.historical_success
                    + 0.10 * (1.0 - spend.risk_penalty) - 0.5)
        assert abs(spend.total - expected) <= 0.001
