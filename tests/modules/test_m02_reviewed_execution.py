"""Reviewed-execution gate tests. Stdlib only, hermetic.

Pins the gate: only an exact draft_ready_for_review plan enters review, the
draft digest is recomputed from draft_values (snapshot hash taken on trust),
one final decision per review, ordered timestamps, permits require an
approved unexpired hash-exact review and are single-use, and the ledger
verifies chain, per-kind content and review order on every path. The module
executes nothing: the permit carries executes=False and the boundary string.
"""
import hashlib
import json

import pytest

from app.modules.m02_competition_manager import reviewed_execution as rx

T0 = "2026-10-11T06:30:00Z"
T1 = "2026-10-11T07:30:00+00:00"          # == T0 + 1h
SNAP = "a" * 64
DRAFT = {"name": "Supplied Name"}
DIGEST = hashlib.sha256(json.dumps(DRAFT, sort_keys=True).encode()).hexdigest()
PLAN = {"site_url": "https://example.invalid/apply",
        "status": "draft_ready_for_review",
        "submission_enabled": False, "browser_action_performed": False,
        "snapshot_sha256": SNAP, "draft_sha256": DIGEST, "draft_values": dict(DRAFT),
        "handoff": {"requires_exact_review": True, "snapshot_sha256": SNAP, "draft_sha256": DIGEST}}
OPEN_REC = {"kind": "review_opened", "review_id": "R1", "site_url": PLAN["site_url"],
            "snapshot_sha256": SNAP, "draft_sha256": DIGEST, "opened_by": "u",
            "opened_at": "2026-10-11T06:30:00+00:00", "valid_hours": 24}
DEC_REC = {"kind": "review_decision", "review_id": "R1", "decision": "approved",
           "reviewer": "u", "rationale": "draft matches sources",
           "decided_at": "2026-10-11T07:30:00+00:00"}
PER_REC = {"kind": "execution_permit", "review_id": "R1", "permit_id": "PERMIT-R1",
           "issued_at": "2026-10-11T08:00:00+00:00", "site_url": PLAN["site_url"],
           "snapshot_sha256": SNAP, "draft_sha256": DIGEST}


def chain(records):
    out, prev = [], "0" * 64
    for i, r in enumerate(records):
        payload = json.dumps({"seq": i, "record": r, "prev_hash": prev}, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256(payload.encode()).hexdigest()
        out.append({"seq": i, "record": r, "prev_hash": prev, "record_hash": h})
        prev = h
    return out


def opened(**kw):
    return rx.open_review(PLAN, review_id="R1", reviewer="udita", now=T0, **kw)


def approved():
    return rx.record_decision(opened(), review_id="R1", decision="approved",
                              reviewer="udita", rationale="draft matches sources", now=T1)


def refuses(code, fn, *a, **kw):
    with pytest.raises(ValueError) as exc:
        fn(*a, **kw)
    assert str(exc.value) == "APPREX: " + code


class TestGoldenPath:
    def test_open_decide_permit_round_trip(self):
        ledger = approved()
        assert rx.audit_state(ledger, "R1") == "approved"
        ledger, permit = rx.issue_permit(ledger, PLAN, review_id="R1", now="2026-10-11T08:00:00Z")
        assert rx.audit_state(ledger, "R1") == "permit_issued"
        assert permit == {"permit_id": "PERMIT-R1", "review_id": "R1",
                          "site_url": "https://example.invalid/apply",
                          "snapshot_sha256": SNAP, "draft_sha256": DIGEST,
                          "approved_by": "udita", "decided_at": "2026-10-11T07:30:00+00:00",
                          "issued_at": "2026-10-11T08:00:00+00:00",
                          "executes": False, "boundary": rx.BOUNDARY}
        assert rx.loads(rx.dumps(ledger)) == ledger
        assert len(ledger) == 3

    def test_pending_state_is_open(self):
        assert rx.audit_state(opened(), "R1") == "open"

    def test_rejection_is_terminal(self):
        ledger = rx.record_decision(opened(), review_id="R1", decision="rejected",
                                    reviewer="udita", rationale="essay too thin", now=T1)
        assert rx.audit_state(ledger, "R1") == "rejected"
        refuses("review 'R1' was rejected", rx.issue_permit, ledger, PLAN, review_id="R1", now=T1)


class TestDraftDigestRecomputation:
    def test_tampered_draft_values_refused_at_open_and_permit(self):
        tampered = dict(PLAN, draft_values={"name": "Mallory"})
        refuses("plan draft_sha256 does not match draft_values",
                rx.open_review, tampered, review_id="R1", reviewer="u", now=T0)
        refuses("plan draft_sha256 does not match draft_values",
                rx.issue_permit, approved(), tampered, review_id="R1", now=T1)

    def test_draft_values_shape_refused(self):
        refuses("plan draft_values must be an exact dict of strings",
                rx.open_review, dict(PLAN, draft_values={"name": 5}),
                review_id="R1", reviewer="u", now=T0)

    def test_changed_draft_with_honest_digest_mismatches_the_review(self):
        other = {"name": "Other"}
        digest = hashlib.sha256(json.dumps(other, sort_keys=True).encode()).hexdigest()
        bad = dict(PLAN, draft_values=other, draft_sha256=digest,
                   handoff={"requires_exact_review": True, "snapshot_sha256": SNAP, "draft_sha256": digest})
        refuses("plan does not match the reviewed draft hashes",
                rx.issue_permit, approved(), bad, review_id="R1", now=T1)


class TestExactStringBoundaries:
    def test_str_subclass_refused_everywhere(self):
        class S(str):
            pass
        refuses("plan site_url must be non-blank text",
                rx.open_review, dict(PLAN, site_url=S(PLAN["site_url"])),
                review_id="R1", reviewer="u", now=T0)
        refuses("reviewer must be non-blank text",
                rx.open_review, PLAN, review_id="R1", reviewer=S("u"), now=T0)
        refuses("plan snapshot_sha256 must be 64 lowercase hex characters",
                rx.open_review, dict(PLAN, snapshot_sha256=S(SNAP)),
                review_id="R1", reviewer="u", now=T0)
        refuses("now must be timezone-aware ISO text",
                rx.open_review, PLAN, review_id="R1", reviewer="u", now=S(T0))
        refuses("review_id must be 1-64 characters of A-Za-z0-9._/-",
                rx.open_review, PLAN, review_id=S("R1"), reviewer="u", now=T0)

    def test_control_format_and_separator_chars_refused_in_text(self):
        for bad in ("rev\u202eiewer", "rev\niewer", "rev\u2028iewer"):
            refuses("reviewer contains a disallowed character (Cc, Cf, Zl or Zp)",
                    rx.open_review, PLAN, review_id="R1", reviewer=bad, now=T0)
        refuses("rationale contains a disallowed character (Cc, Cf, Zl or Zp)",
                rx.record_decision, opened(), review_id="R1", decision="approved",
                reviewer="u", rationale="bad\u0007text", now=T1)


class TestGateRefusals:
    def test_only_complete_drafts_enter_review(self):
        for status in ("blocked", "needs_input"):
            refuses("only a draft_ready_for_review plan can enter review",
                    rx.open_review, dict(PLAN, status=status),
                    review_id="R1", reviewer="u", now=T0)

    def test_execution_flags_refuse_review(self):
        refuses("plan flags indicate execution; refusing to review",
                rx.open_review, dict(PLAN, browser_action_performed=True),
                review_id="R1", reviewer="u", now=T0)

    def test_handoff_must_require_exact_review(self):
        bad = dict(PLAN, handoff={"requires_exact_review": False,
                                  "snapshot_sha256": SNAP, "draft_sha256": DIGEST})
        refuses("plan handoff must require exact review", rx.open_review, bad,
                review_id="R1", reviewer="u", now=T0)

    def test_handoff_hashes_must_match_plan(self):
        bad = dict(PLAN, handoff={"requires_exact_review": True,
                                  "snapshot_sha256": "c" * 64, "draft_sha256": DIGEST})
        refuses("plan handoff snapshot_sha256 does not match the plan",
                rx.open_review, bad, review_id="R1", reviewer="u", now=T0)

    def test_undecided_review_issues_no_permit(self):
        refuses("review 'R1' has no decision", rx.issue_permit, opened(), PLAN,
                review_id="R1", now=T1)

    def test_one_final_decision_per_review(self):
        refuses("review 'R1' already has a decision", rx.record_decision, approved(),
                review_id="R1", decision="rejected", reviewer="u", rationale="changed", now=T1)

    def test_unknown_review_refused(self):
        refuses("review 'R9' is not open", rx.record_decision, opened(), review_id="R9",
                decision="approved", reviewer="u", rationale="r", now=T1)
        refuses("review 'R9' is not open", rx.audit_state, opened(), "R9")

    def test_permit_is_single_use(self):
        ledger, _permit = rx.issue_permit(approved(), PLAN, review_id="R1", now=T1)
        refuses("review 'R1' already has an execution permit",
                rx.issue_permit, ledger, PLAN, review_id="R1", now=T1)

    def test_snapshot_mismatch_refused(self):
        bad = dict(PLAN, snapshot_sha256="c" * 64,
                   handoff={"requires_exact_review": True, "snapshot_sha256": "c" * 64,
                            "draft_sha256": DIGEST})
        refuses("plan does not match the reviewed draft hashes",
                rx.issue_permit, approved(), bad, review_id="R1", now=T1)
        refuses("plan does not match the reviewed draft hashes",
                rx.issue_permit, approved(), dict(PLAN, site_url="https://example.invalid/other"),
                review_id="R1", now=T1)

    def test_validity_window_enforced(self):
        ledger = approved()
        refuses("review 'R1' validity window has expired",
                rx.issue_permit, ledger, PLAN, review_id="R1", now="2026-10-12T06:30:00.000001Z")
        ledger2, _permit = rx.issue_permit(ledger, PLAN, review_id="R1", now="2026-10-12T06:30:00Z")
        assert rx.audit_state(ledger2, "R1") == "permit_issued"   # exactly at the deadline: allowed

    def test_duplicate_review_id_refused(self):
        refuses("review 'R1' is already open", rx.open_review, PLAN, review_id="R1",
                reviewer="u", now=T1, ledger=opened())


class TestOrderedTimestamps:
    def test_decision_cannot_predate_the_opening(self):
        refuses("review 'R1' decision is before it opened", rx.record_decision, opened(),
                review_id="R1", decision="approved", reviewer="u", rationale="r",
                now="2026-10-11T05:30:00Z")

    def test_permit_cannot_predate_the_decision(self):
        refuses("review 'R1' permit is before the decision", rx.issue_permit,
                approved(), PLAN, review_id="R1", now="2026-10-11T07:00:00Z")

    def test_far_future_opening_overflow_refused(self):
        refuses("review 'R1' valid_hours overflows the clock", rx.open_review, PLAN,
                review_id="R1", reviewer="u", now="9999-12-31T23:00:00Z", valid_hours=720)


class TestValidation:
    def test_exact_dict_plan(self):
        class Plan(dict):
            pass
        refuses("plan must be the exact dict returned by plan_application",
                rx.open_review, Plan(PLAN), review_id="R1", reviewer="u", now=T0)

    def test_review_id_charset(self):
        for bad in ("", "has space", "x" * 65, 5):
            refuses("review_id must be 1-64 characters of A-Za-z0-9._/-",
                    rx.open_review, PLAN, review_id=bad, reviewer="u", now=T0)

    def test_text_caps_and_blanks(self):
        refuses("reviewer must be non-blank text", rx.open_review, PLAN,
                review_id="R1", reviewer="  ", now=T0)
        refuses("rationale exceeds 256 characters", rx.record_decision, opened(),
                review_id="R1", decision="approved", reviewer="u", rationale="x" * 257, now=T1)
        ledger = rx.open_review(PLAN, review_id="R1", reviewer="x" * 256, now=T0)
        assert ledger[0]["record"]["opened_by"] == "x" * 256      # 256 accepted

    def test_valid_hours_bounds(self):
        for bad in (0, -1, 721, float("nan"), True):
            refuses("valid_hours must be a finite number in (0, 720]",
                    rx.open_review, PLAN, review_id="R1", reviewer="u", now=T0, valid_hours=bad)
        for ok in (0.5, 720):
            assert rx.open_review(PLAN, review_id="R1", reviewer="u", now=T0, valid_hours=ok)

    def test_timestamps_must_be_zoned_iso(self):
        for bad in ("2026-10-11 06:30", "not-a-date", 5):
            refuses("now must be timezone-aware ISO text", rx.open_review, PLAN,
                    review_id="R1", reviewer="u", now=bad)

    def test_decision_literal(self):
        refuses("decision must be 'approved' or 'rejected'", rx.record_decision, opened(),
                review_id="R1", decision="yes", reviewer="u", rationale="r", now=T1)

    def test_keyword_only_arguments_enforced(self):
        with pytest.raises(TypeError):
            rx.open_review(PLAN, "R1", "u", T0)
        with pytest.raises(TypeError):
            rx.record_decision(opened(), "R1", "approved", "u", "r", T1)
        with pytest.raises(TypeError):
            rx.issue_permit(approved(), PLAN, "R1", T1)


class TestLedgerIntegrity:
    def test_malformed_ledgers_refused_on_direct_paths(self):
        refuses("ledger entry 0 has an unexpected shape", rx.record_decision, [{}],
                review_id="R1", decision="approved", reviewer="u", rationale="r", now=T1)
        refuses("ledger entry 0 has an unexpected shape", rx.issue_permit, [{}], PLAN,
                review_id="R1", now=T1)
        refuses("ledger entry 0 has an unexpected shape", rx.audit_state, [{}], "R1")
        refuses("ledger must be a list of at most 512 records", rx.record_decision, "x",
                review_id="R1", decision="approved", reviewer="u", rationale="r", now=T1)

    def test_tampered_record_fails_integrity(self):
        raw = rx.loads(rx.dumps(approved()))
        raw[1]["record"]["reviewer"] = "mallory"
        refuses("ledger entry 1 fails the integrity check", rx.loads, rx.dumps(raw))

    def test_broken_chain_refused(self):
        raw = rx.loads(rx.dumps(approved()))
        raw[1]["prev_hash"] = "0" * 64
        refuses("ledger entry 1 breaks the sequence chain", rx.loads, rx.dumps(raw))

    def test_unknown_kind_and_shape_refused(self):
        raw = chain([dict(OPEN_REC, kind="backdoor")])
        refuses("ledger entry 0 has an unknown record kind", rx.loads, rx.dumps(raw))
        raw = chain([OPEN_REC])
        raw[0]["extra"] = 1
        refuses("ledger entry 0 has an unexpected shape", rx.loads, rx.dumps(raw))
        raw = chain([dict(OPEN_REC, opened_by="")])
        refuses("ledger entry 0 has invalid content: APPREX: opened_by must be non-blank text",
                rx.loads, rx.dumps(raw))

    def test_order_violations_refused(self):
        refuses("ledger entry 0 decides unopened review 'R1'",
                rx.loads, rx.dumps(chain([DEC_REC])))
        refuses("ledger entry 1 permits review 'R1' before its decision",
                rx.loads, rx.dumps(chain([OPEN_REC, PER_REC])))
        refuses("ledger entry 2 permits rejected review 'R1'",
                rx.loads, rx.dumps(chain([OPEN_REC, dict(DEC_REC, decision="rejected"), PER_REC])))
        refuses("ledger entry 2 has a second decision for review 'R1'",
                rx.loads, rx.dumps(chain([OPEN_REC, DEC_REC, dict(DEC_REC, decided_at="2026-10-11T09:00:00Z")])))
        refuses("ledger entry 1 reopens review 'R1'",
                rx.loads, rx.dumps(chain([OPEN_REC, dict(OPEN_REC, opened_by="v")])))

    def test_permit_consistency_refused(self):
        refuses("ledger entry 2 permit does not match the opened review",
                rx.loads, rx.dumps(chain([OPEN_REC, DEC_REC, dict(PER_REC, site_url="https://evil.invalid")])))
        refuses("ledger entry 2 permit_id does not match the review",
                rx.loads, rx.dumps(chain([OPEN_REC, DEC_REC, dict(PER_REC, permit_id="PERMIT-X")])))
        early = dict(DEC_REC, decided_at="2026-10-11T05:30:00+00:00")
        refuses("ledger entry 1 decision is before the review opened",
                rx.loads, rx.dumps(chain([OPEN_REC, early])))
        pre = dict(PER_REC, issued_at="2026-10-11T07:00:00+00:00")
        refuses("ledger entry 2 permit is before the decision",
                rx.loads, rx.dumps(chain([OPEN_REC, DEC_REC, pre])))
        late = dict(PER_REC, issued_at="2026-10-12T07:00:00+00:00")
        refuses("ledger entry 2 permit is outside the review validity window",
                rx.loads, rx.dumps(chain([OPEN_REC, DEC_REC, late])))

    def test_overflowing_validity_window_refused(self):
        far = dict(OPEN_REC, opened_at="9999-12-31T23:00:00+00:00", valid_hours=720)
        dec = dict(DEC_REC, decided_at="9999-12-31T23:30:00+00:00")
        per = dict(PER_REC, issued_at="9999-12-31T23:59:00+00:00")
        refuses("review 'R1' valid_hours overflows the clock",
                rx.loads, rx.dumps(chain([far, dec, per])))

    def test_record_cap(self):
        ledger = opened()
        for i in range(2, 513):
            ledger = rx.open_review(PLAN, review_id=f"R{i}", reviewer="u", now=T0, ledger=ledger)
        refuses("ledger exceeds 512 records", rx.open_review, PLAN, review_id="R513",
                reviewer="u", now=T0, ledger=ledger)
        big = [dict(OPEN_REC, review_id=f"R{i}") for i in range(513)]
        refuses("ledger must be a list of at most 512 records", rx.loads, rx.dumps(chain(big)))
        refuses("ledger must be a list of at most 512 records", rx.loads, '{"a": 1}')

    def test_serialized_text_bounds(self):
        text = rx.dumps(approved())
        padded = text + " " * (1_000_000 - len(text))
        assert rx.loads(padded) == approved()                  # exactly 1M accepted
        refuses("serialized ledger must be text at most 1000000 characters",
                rx.loads, padded + " ")
        refuses("serialized ledger must be text at most 1000000 characters", rx.loads, 5)
        refuses("serialized ledger must be text at most 1000000 characters", rx.loads, b"{}")

    def test_dumps_is_byte_stable(self):
        ledger = approved()
        text = rx.dumps(ledger)
        assert text == json.dumps(ledger, sort_keys=True, separators=(",", ":"))
        assert text.find('"prev_hash"') < text.find('"record"') < text.find('"record_hash"') < text.find('"seq"')

    def test_module_is_hermetic_standard_library_only(self):
        import ast, inspect
        tree = ast.parse(inspect.getsource(rx))
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                names.add(n.module.split(".")[0])
        assert names <= {"__future__", "hashlib", "json", "math", "re", "unicodedata", "datetime"}
