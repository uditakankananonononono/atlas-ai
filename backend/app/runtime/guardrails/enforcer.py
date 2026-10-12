"""Guardrail enforcer: the single runtime choke point for instinct-doc groups
134-142.

Holds one hash-chained ledger per gate and exposes the guarded operations as
one surface, so a caller wiring runtime effects through GuardrailEnforcer
gets every guardrail firing at one place with one audit trail:

- run_bio_work          groups 134+135 (in-silico-only, prohibited bio)
- dispatch_outbound     group 136 (platform terms, rate limits, consent)
- execute_reviewed      group 137 (explicit review for contact/application/
                        submission/account actions, permits + preauthorizations)
- emit_text             group 138 (no false sentience/AGI claims)
- call_service          group 139 (verified owner-account identity)
- claim_research_done   group 140 (evidence-bound research completion)
- require_tool_bar      group 141 (verified per-project tool bar, 200 strict)
- emit_report           group 142 (no unlabeled/unsupported claims)

The enforcer performs no effect itself: callers pass effect callables, and
each gate runs the effect only after its admission decision is ledgered.
approval_check / review_check hooks supplied at construction are how the
bio and outbound gates validate approval references (wire them to the review
gate or Module 0); unset hooks fail closed. Pure stdlib composition; each
gate keeps its own contract and LIMITS.
"""
from __future__ import annotations

import json

from . import (bio_gate, claim_lint_gate, ledger as _ledger, outbound_gate,
               owner_account_gate, report_gate, research_gate, review_gate,
               tool_usage_bar)
from ._fields import make_fail
from .errors import GuardrailRefusal

PREFIX = "ENFORCER"
_fail = make_fail(PREFIX)

LEDGERS = ("bio", "outbound", "review", "claims", "accounts", "research", "tools", "reports")
_GATES = {
    "bio": bio_gate,
    "outbound": outbound_gate,
    "review": review_gate,
    "claims": claim_lint_gate,
    "accounts": owner_account_gate,
    "research": research_gate,
    "tools": tool_usage_bar,
    "reports": report_gate,
}
MAX_SERIALIZED = 8 * _ledger.MAX_SERIALIZED


class GuardrailEnforcer:
    """One instance holds all eight gate ledgers plus the approval hooks."""

    def __init__(self, *, ledgers=None, approval_check=None, review_check=None) -> None:
        if approval_check is not None and not callable(approval_check):
            _fail("bad_type:approval_check")
        if review_check is not None and not callable(review_check):
            _fail("bad_type:review_check")
        self.approval_check = approval_check
        self.review_check = review_check
        if ledgers is None:
            ledgers = {name: [] for name in LEDGERS}
        if type(ledgers) is not dict or set(ledgers) != set(LEDGERS):
            _fail("ledgers must map exactly the eight gate names")
        for name, gate in _GATES.items():
            gate.check_ledger(ledgers[name])
        self._ledgers = {name: list(ledgers[name]) for name in LEDGERS}

    def ledger(self, name):
        if name not in _GATES:
            _fail(f"unknown ledger {name!r}")
        return list(self._ledgers[name])

    def _capture(self, name, call):
        """Run one gate's guarded operation, persisting its ledger whether the
        gate admits or refuses: a GuardrailRefusal carries the ledger with the
        refusal verdict appended, so refused attempts stay durable evidence."""
        try:
            ledger, result = call(self._ledgers[name])
        except GuardrailRefusal as refusal:
            if refusal.ledger is not None:
                _GATES[name].check_ledger(refusal.ledger)
                self._ledgers[name] = refusal.ledger
            raise
        self._ledgers[name] = ledger
        return result

    # ---- groups 134 + 135 -------------------------------------------------
    def run_bio_work(self, effect, item, *, now):
        return self._capture("bio", lambda led: bio_gate.run_guarded(
            effect, item, now=now, ledger=led, approval_check=self.approval_check))

    def admit_bio_work(self, item, *, now):
        ledger, record = bio_gate.admit(
            item, now=now, ledger=self._ledgers["bio"], approval_check=self.approval_check)
        self._ledgers["bio"] = ledger
        return record

    # ---- group 136 --------------------------------------------------------
    def dispatch_outbound(self, action, declarations, *, effect, now):
        return self._capture("outbound", lambda led: outbound_gate.dispatch(
            action, declarations, effect=effect, now=now, ledger=led,
            review_check=self.review_check))

    # ---- group 137 --------------------------------------------------------
    def open_review(self, action, *, review_id, reviewer, now, valid_hours=24):
        self._ledgers["review"] = review_gate.open_review(
            self._ledgers["review"], action, review_id=review_id, reviewer=reviewer,
            now=now, valid_hours=valid_hours)

    def record_decision(self, *, review_id, decision, reviewer, rationale, now):
        self._ledgers["review"] = review_gate.record_decision(
            self._ledgers["review"], review_id=review_id, decision=decision,
            reviewer=reviewer, rationale=rationale, now=now)

    def issue_permit(self, action, *, review_id, now):
        ledger, permit = review_gate.issue_permit(
            self._ledgers["review"], action, review_id=review_id, now=now)
        self._ledgers["review"] = ledger
        return permit

    def grant_preauthorization(self, action, *, preauth_id, granted_by, now, valid_hours, scope_note):
        self._ledgers["review"] = review_gate.grant_preauthorization(
            self._ledgers["review"], action, preauth_id=preauth_id, granted_by=granted_by,
            now=now, valid_hours=valid_hours, scope_note=scope_note)

    def revoke_preauthorization(self, *, preauth_id, revoked_by, rationale, now):
        self._ledgers["review"] = review_gate.revoke_preauthorization(
            self._ledgers["review"], preauth_id=preauth_id, revoked_by=revoked_by,
            rationale=rationale, now=now)

    def execute_reviewed(self, action, *, effect, now, permit_id=None):
        return self._capture("review", lambda led: review_gate.execute(
            led, action, effect=effect, now=now, permit_id=permit_id))

    # ---- group 138 --------------------------------------------------------
    def emit_text(self, emission_id, body, *, channel, now):
        return self._capture("claims", lambda led: claim_lint_gate.emit(
            emission_id, body, channel=channel, now=now, ledger=led))

    # ---- group 139 --------------------------------------------------------
    def register_account(self, service, account_identity, *, registered_by, now, evidence_ref=""):
        self._ledgers["accounts"] = owner_account_gate.register_binding(
            self._ledgers["accounts"], service, account_identity,
            registered_by=registered_by, now=now, evidence_ref=evidence_ref)

    def verify_account(self, service, account_identity, *, verified_by, now, evidence_ref=""):
        self._ledgers["accounts"] = owner_account_gate.verify_binding(
            self._ledgers["accounts"], service, account_identity,
            verified_by=verified_by, now=now, evidence_ref=evidence_ref)

    def revoke_account(self, service, account_identity, *, revoked_by, rationale, now):
        self._ledgers["accounts"] = owner_account_gate.revoke_binding(
            self._ledgers["accounts"], service, account_identity,
            revoked_by=revoked_by, rationale=rationale, now=now)

    def call_service(self, call_id, service, account_identity, *, effect, now):
        return self._capture("accounts", lambda led: owner_account_gate.call(
            led, call_id, service, account_identity, effect=effect, now=now))

    # ---- group 140 --------------------------------------------------------
    def register_dataset(self, project_id, dataset_id, *, name, source_ref="", now):
        self._ledgers["research"] = research_gate.register_dataset(
            self._ledgers["research"], project_id, dataset_id, name=name,
            source_ref=source_ref, now=now)

    def record_run(self, project_id, run_id, *, started_at, ended_at, result_sha256, summary):
        self._ledgers["research"] = research_gate.record_run(
            self._ledgers["research"], project_id, run_id, started_at=started_at,
            ended_at=ended_at, result_sha256=result_sha256, summary=summary)

    def record_result(self, project_id, result_id, *, finding, result_sha256, now):
        self._ledgers["research"] = research_gate.record_result(
            self._ledgers["research"], project_id, result_id, finding=finding,
            result_sha256=result_sha256, now=now)

    def claim_research_done(self, project_id, claim_id, *, statement, now):
        return self._capture("research", lambda led: research_gate.claim_conducted(
            led, project_id, claim_id, statement=statement, now=now))

    # ---- group 141 --------------------------------------------------------
    def record_tool_use(self, project_id, tool, *, used_at, evidence_ref, verified_by):
        self._ledgers["tools"] = tool_usage_bar.record_use(
            self._ledgers["tools"], project_id, tool, used_at=used_at,
            evidence_ref=evidence_ref, verified_by=verified_by)

    def evaluate_tool_bar(self, project_id, *, bar=tool_usage_bar.DEFAULT_BAR, now):
        ledger, record = tool_usage_bar.evaluate(
            self._ledgers["tools"], project_id, bar=bar, now=now)
        self._ledgers["tools"] = ledger
        return record

    def require_tool_bar(self, project_id, *, bar=tool_usage_bar.DEFAULT_BAR, now):
        return self._capture("tools", lambda led: tool_usage_bar.require_bar(
            led, project_id, bar=bar, now=now))

    # ---- group 142 --------------------------------------------------------
    def emit_report(self, report_id, body, *, now):
        return self._capture("reports", lambda led: report_gate.emit_report(
            report_id, body, now=now, ledger=led))

    # ---- audit + persistence ----------------------------------------------
    def audit(self):
        """Chain-verified digest of every gate ledger: counts and tip hashes."""
        out = {}
        for name in LEDGERS:
            ledger = self._ledgers[name]
            _GATES[name].check_ledger(ledger)
            refusals = sum(
                1 for entry in ledger
                if str(entry["record"].get("verdict", "")).startswith("refused:")
                or entry["record"].get("kind") == "execution_refused"
                or (entry["record"].get("kind") == "bar_evaluated"
                    and entry["record"].get("verdict") == "unmet"))
            out[name] = {
                "records": len(ledger),
                "refusals": refusals,
                "tip_hash": ledger[-1]["record_hash"] if ledger else _ledger.GENESIS_HASH,
            }
        return out

    def dumps(self):
        """Serialize all ledgers as one canonical JSON document."""
        return json.dumps({name: json.loads(_ledger.dumps(self._ledgers[name]))
                           for name in LEDGERS}, sort_keys=True, separators=(",", ":"))

    @classmethod
    def loads(cls, text_, *, approval_check=None, review_check=None):
        """Restore from dumps(); every ledger's chain and content is re-verified."""
        if type(text_) is not str or len(text_) > MAX_SERIALIZED:
            _fail(f"serialized state must be text at most {MAX_SERIALIZED} characters")
        try:
            raw = json.loads(text_)
        except ValueError:
            _fail("serialized state is not valid JSON")
        if type(raw) is not dict or set(raw) != set(LEDGERS):
            _fail("serialized state must map exactly the eight gate names")
        ledgers = {}
        for name, gate in _GATES.items():
            ledgers[name] = gate.loads(json.dumps(raw[name], sort_keys=True, separators=(",", ":")))
        return cls(ledgers=ledgers, approval_check=approval_check, review_check=review_check)


__all__ = ["GuardrailEnforcer", "GuardrailRefusal", "LEDGERS"]
