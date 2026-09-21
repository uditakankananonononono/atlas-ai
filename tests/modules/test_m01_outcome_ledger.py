from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m01_opportunity_discovery.outcome_ledger import (
    OutcomeConsent, OutcomeLedger, OutcomeProvenance, OutcomeStatus, ProvenanceKind,
)

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


def consent(expires=400):
    return OutcomeConsent("application_outcome_history", NOW - timedelta(days=1), NOW + timedelta(days=expires), "owner-consent-1")


def provenance(ref="notice-1"):
    return OutcomeProvenance(ProvenanceKind.OFFICIAL_NOTICE, ref, NOW, "owner")


def record(ledger, status, **extra):
    return ledger.record(owner_id="u1", opportunity_id=f"opp-{status}", sponsor="NIH", mechanism="R01",
                         cycle="2026", geography="US", status=status, provenance=provenance(),
                         consent=consent(), recorded_at=NOW, **extra)


def test_all_explicit_states_and_decline_parity():
    ledger = OutcomeLedger()
    pending = record(ledger, OutcomeStatus.PENDING)
    waitlisted = record(ledger, OutcomeStatus.WAITLISTED)
    awarded = record(ledger, OutcomeStatus.AWARDED, decision_at=NOW, amount=1000, currency="usd")
    declined = record(ledger, OutcomeStatus.DECLINED, decision_at=NOW)
    withdrawn = record(ledger, OutcomeStatus.WITHDRAWN, decision_at=NOW)
    assert {x.status for x in ledger.list("u1", at=NOW)} == set(OutcomeStatus)
    assert declined.provenance == awarded.provenance
    assert awarded.currency == "USD"
    assert all(x.advisory_only and not x.training_enabled for x in (pending, waitlisted, awarded, declined, withdrawn))


def test_terminal_states_require_decision_time_and_provenance_is_mandatory():
    with pytest.raises(ValueError, match="decision_at"):
        record(OutcomeLedger(), OutcomeStatus.DECLINED)
    with pytest.raises(ValueError, match="source_reference"):
        OutcomeProvenance(ProvenanceKind.USER_REPORTED, "", NOW, "owner")


def test_consent_and_retention_boundaries_fail_closed():
    ledger = OutcomeLedger(max_retention_days=30)
    expired = OutcomeConsent("application_outcome_history", NOW - timedelta(days=2), NOW - timedelta(days=1), "old")
    with pytest.raises(PermissionError, match="consent"):
        ledger.record(owner_id="u1", opportunity_id="x", sponsor="s", mechanism="m", cycle="c", geography="g",
                      status=OutcomeStatus.PENDING, provenance=provenance(), consent=expired, recorded_at=NOW)
    with pytest.raises(ValueError, match="between 1 and 30"):
        ledger.record(owner_id="u1", opportunity_id="x", sponsor="s", mechanism="m", cycle="c", geography="g",
                      status=OutcomeStatus.PENDING, provenance=provenance(), consent=consent(), recorded_at=NOW,
                      retention_days=31)


def test_retention_is_capped_by_consent_and_purged():
    ledger = OutcomeLedger()
    short = OutcomeConsent("application_outcome_history", NOW - timedelta(days=1), NOW + timedelta(days=10), "short")
    item = ledger.record(owner_id="u1", opportunity_id="x", sponsor="s", mechanism="m", cycle="c", geography="g",
                         status=OutcomeStatus.PENDING, provenance=provenance(), consent=short, recorded_at=NOW,
                         retention_days=365)
    assert item.retain_until == short.expires_at
    assert ledger.purge_expired(at=short.expires_at) == 1
    assert ledger.list("u1", at=short.expires_at) == ()


def test_owner_isolation_revision_and_revocation_delete_rows():
    ledger = OutcomeLedger()
    item = record(ledger, OutcomeStatus.PENDING)
    with pytest.raises(LookupError):
        ledger.delete("other", item.id)
    revised = ledger.revise_status("u1", item.id, OutcomeStatus.DECLINED, provenance("decline-letter"),
                                   decision_at=NOW, at=NOW)
    assert revised.status is OutcomeStatus.DECLINED and revised.provenance.source_reference == "decline-letter"
    assert ledger.revoke_consent("u1", "owner-consent-1") == 1
    assert ledger.list("u1", at=NOW) == ()


def test_no_training_or_feature_export_api_exists():
    ledger = OutcomeLedger()
    assert not hasattr(ledger, "train")
    assert not hasattr(ledger, "training_rows")
    assert not hasattr(ledger, "feature_matrix")
