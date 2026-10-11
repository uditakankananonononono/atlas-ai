"""c30.x_register tests: X1-X30 bounded substitutes. Hermetic, stdlib only."""
import importlib.util
import pathlib
import sys

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.modules.c30 import policy  # canonical policy (check, clean_text, RULES)

_spec = importlib.util.spec_from_file_location(
    "c30_x_register_under_test", _BACKEND / "app/modules/m20_general_cognitive_worker/c30/x_register.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["c30_x_register_under_test"] = x
_spec.loader.exec_module(x)

AOF = {"as_of": "2026-10-11"}


def refuses(code, fn, payload):
    with pytest.raises(ValueError) as exc:
        fn(payload)
    assert str(exc.value) == code


def scope_ok(result, as_of="2026-10-11"):
    scope = result["scope"]
    assert set(scope) == {"implemented", "not_implemented", "data_source", "as_of"}
    assert scope["data_source"] == "supplied"
    assert scope["as_of"] == as_of
    assert scope["implemented"] and scope["not_implemented"]


class TestRegister:
    def test_thirty_entries_all_callable(self):
        assert set(x.REGISTER) == {"X%d" % i for i in range(1, 31)} and len(x.REGISTER) == 30
        assert all(callable(f) for f in x.REGISTER.values())

    def test_forbidden_keys_pinned_to_canonical_rules(self):
        assert len(x.FORBIDDEN_KEYS) == 13
        assert set(x.FORBIDDEN_KEYS.values()) == set(policy.RULES) == {
            "spend", "outreach", "fakeacct", "autopost", "scrape", "trade"}
        assert x.PREFIX == "XREG"


class TestGuardRemovalProof:
    """Removing a guard call must flip these exact POLICY codes to something else."""
    @pytest.mark.parametrize("key,code", [
        ("spend", "XREG_REFUSED_SPEND"),
        ("purchase", "XREG_REFUSED_SPEND"),
        ("buy_compute", "XREG_REFUSED_SPEND"),
        ("send", "XREG_REFUSED_OUTREACH"),
        ("submit", "XREG_REFUSED_OUTREACH"),
        ("outreach", "XREG_REFUSED_OUTREACH"),
        ("multi_account", "XREG_REFUSED_FAKEACCT"),
        ("fake_accounts", "XREG_REFUSED_FAKEACCT"),
        ("post_now", "XREG_REFUSED_AUTOPOST"),
        ("autopost", "XREG_REFUSED_AUTOPOST"),
        ("scrape", "XREG_REFUSED_SCRAPE"),
        ("broker", "XREG_REFUSED_TRADE"),
        ("live_trade", "XREG_REFUSED_TRADE"),
    ])
    def test_forbidden_key_refused(self, key, code):
        payload = dict(AOF, shards=[], **{key: True})
        refuses(code, x.x01_coverage_ledger, payload)

    def test_falsy_forbidden_key_falls_to_shape_strictness(self):
        refuses("XREG_REFUSED_UNKNOWN_FIELDS:payload",
                x.x01_coverage_ledger, dict(AOF, shards=[], submit=False))


class TestSharedValidation:
    def test_unknown_field(self):
        refuses("XREG_REFUSED_UNKNOWN_FIELDS:payload",
                x.x08_capability_ceiling, dict(AOF, scores=[], nope=1))

    def test_missing_field(self):
        refuses("XREG_REFUSED_EMPTY_FIELD:scores", x.x08_capability_ceiling, dict(AOF))

    def test_bad_type_payload(self):
        refuses("XREG_REFUSED_BAD_TYPE:payload", x.x08_capability_ceiling, "nope")

    def test_unsafe_chars(self):
        refuses("XREG_REFUSED_CONTROL_CHARS:as_of",
                x.x08_capability_ceiling, {"as_of": "2026-10-11\n", "scores": []})

    def test_strict_int_bool_refused(self):
        refuses("XREG_REFUSED_OUT_OF_RANGE:records",
                x.x01_coverage_ledger, dict(AOF, shards=[
                    {"shard_id": "s", "source": "a", "records": True, "checkpoint": "c"}]))


class TestX01:
    def test_rollup(self):
        r = x.x01_coverage_ledger(dict(AOF, shards=[
            {"shard_id": "s2", "source": "arxiv", "records": 5, "checkpoint": "c"},
            {"shard_id": "s1", "source": "gutenberg", "records": 7, "checkpoint": "c"},
            {"shard_id": "s3", "source": "arxiv", "records": 3, "checkpoint": "c"}]))
        assert r["total_records"] == 15
        assert r["per_source"] == {"arxiv": 8, "gutenberg": 7}
        assert r["resumable"] is True and r["claim"] == "throughput_only"
        scope_ok(r)

    def test_duplicate_shard(self):
        refuses("XREG_REFUSED_DUPLICATE:shard_id", x.x01_coverage_ledger,
                dict(AOF, shards=[{"shard_id": "s", "source": "a", "records": 1, "checkpoint": "c"},
                                  {"shard_id": "s", "source": "a", "records": 1, "checkpoint": "c"}]))


class TestX02:
    def test_analysis(self):
        r = x.x02_corpus_analyzer(dict(AOF, posts=[
            {"id": "1", "author": "amy", "text": "climate climate tech"},
            {"id": "2", "author": "bo", "text": "climate policy"}]))
        assert r["corpus_size"] == 2 and r["distinct_authors"] == 2
        assert r["top_tokens"][0] == "climate"
        scope_ok(r)


class TestX03:
    def test_draft_only(self):
        r = x.x03_drafts_only_content(dict(AOF, theme="girly fragrance brand",
                                           sources=["nice packaging ideas", "soft pastel palettes"]))
        assert r["status"] == "draft_only"
        assert "girly fragrance brand" in r["draft"]
        scope_ok(r)

    def test_near_duplicate_refused(self):
        text = "alpha beta gamma delta epsilon zeta eta theta"
        refuses("XREG_REFUSED_COPY:near_duplicate_of_source", x.x03_drafts_only_content,
                dict(AOF, theme=text, sources=[text]))

    def test_autopost_refused(self):
        refuses("XREG_REFUSED_AUTOPOST",
                x.x03_drafts_only_content,
                dict(AOF, theme="t", sources=["a b c"], autopost=True))


class TestX04:
    def test_backtest_arithmetic(self):
        r = x.x04_paper_backtester(dict(AOF, closes=[10.0, 12.0, 9.0], trades=[
            {"index": 0, "side": "buy", "qty": 2},
            {"index": 1, "side": "sell", "qty": 2}], predictions=[
            {"p": 0.7, "outcome": 1}, {"p": 0.2, "outcome": 0}]))
        assert r["final_equity"] == 4.0
        assert r["brier"] == round(((0.7 - 1) ** 2 + (0.2 - 0) ** 2) / 2, 6)
        assert r["paper"] is True and r["not_financial_advice"] is True
        scope_ok(r)

    def test_broker_refused(self):
        refuses("XREG_REFUSED_TRADE", x.x04_paper_backtester,
                dict(AOF, closes=[1.0], trades=[], predictions=[], broker=True))

    def test_open_position_counts_in_equity(self):
        r = x.x04_paper_backtester(dict(AOF, closes=[10.0, 15.0], predictions=[], trades=[
            {"index": 0, "side": "buy", "qty": 2}]))
        assert r["final_equity"] == 10.0
        assert r["walk_forward_checkpoints"] == [15.0]

    def test_walk_forward_checkpoints_deduped(self):
        r = x.x04_paper_backtester(dict(AOF, closes=[10.0, 12.0, 9.0], predictions=[], trades=[]))
        assert r["walk_forward_checkpoints"] == [12.0, 9.0]

    def test_trade_order(self):
        refuses("XREG_REFUSED_OUT_OF_RANGE:trade_order", x.x04_paper_backtester,
                dict(AOF, closes=[1.0, 2.0], predictions=[], trades=[
                    {"index": 1, "side": "buy", "qty": 1},
                    {"index": 0, "side": "buy", "qty": 1}]))


class TestX05:
    D = {"id": "d1", "recipient": "prof@example.edu", "text": "Dear Professor"}

    def test_pending_and_exact_release(self):
        r = x.x05_approval_queue(dict(AOF, drafts=[self.D], approvals=[
            {"draft_id": "d1", "recipient": "prof@example.edu", "exact_text": "Dear Professor"}]))
        assert r["queue"] == [{"id": "d1", "recipient": "prof@example.edu", "status": "released"}]
        assert r["rejected_approvals"] == []
        scope_ok(r)

    def test_mismatched_approval_stays_pending(self):
        r = x.x05_approval_queue(dict(AOF, drafts=[self.D], approvals=[
            {"draft_id": "d1", "recipient": "prof@example.edu", "exact_text": "Dear Professor,"}]))
        assert r["queue"][0]["status"] == "pending"
        assert r["rejected_approvals"] == ["d1"]

    def test_send_refused(self):
        refuses("XREG_REFUSED_OUTREACH",
                x.x05_approval_queue, dict(AOF, drafts=[], approvals=[], send=True))


class TestX06:
    def test_packets_sorted_submit_user_only(self):
        r = x.x06_prefill_tracker(dict(AOF, profile={"name": "U", "gpa": "4.0"}, opportunities=[
            {"id": "b", "deadline": "2026-12-01", "eligibility": [], "fee": 50},
            {"id": "a", "deadline": "2026-11-01", "eligibility": ["india"], "fee": 0}]))
        assert [p["opportunity_id"] for p in r["packets"]] == ["a", "b"]
        assert r["packets"][1]["waiver_draft_needed"] is True
        assert all(p["submit"] == "user_only" for p in r["packets"])
        scope_ok(r)

    def test_submit_refused(self):
        refuses("XREG_REFUSED_OUTREACH",
                x.x06_prefill_tracker, dict(AOF, profile={}, opportunities=[], submit=True))


class TestX07:
    def test_allowlist_filter(self):
        r = x.x07_public_record_watcher(dict(AOF, items=[
            {"id": "1", "source": "sec", "title": "filing", "url": "https://sec.gov/x"},
            {"id": "2", "source": "darkweb", "title": "no", "url": "http://x"}]))
        assert [d["id"] for d in r["digest"]] == ["1"]
        assert r["excluded_non_allowlisted"] == ["2"]
        scope_ok(r)

    def test_classified_refused(self):
        refuses("XREG_REFUSED_CLASSIFIED:restricted_material_refused",
                x.x07_public_record_watcher, dict(AOF, items=[], seek_restricted=True))


class TestX08:
    def test_measured_only(self):
        r = x08 = x.x08_capability_ceiling(dict(AOF, scores=[
            {"task": "b", "score": 9, "max_score": 10},
            {"task": "a", "score": 1, "max_score": 4}]))
        assert r["ceiling_ratio"] == 0.9
        assert r["measured"][0]["task"] == "a"
        assert r["claims"] == "measured_only"
        scope_ok(r)

    def test_score_above_max_refused(self):
        refuses("XREG_REFUSED_OUT_OF_RANGE:score", x.x08_capability_ceiling,
                dict(AOF, scores=[{"task": "t", "score": 11, "max_score": 10}]))


class TestX09:
    def test_ranking(self):
        r = x.x09_niche_scorer(dict(AOF, niches=[
            {"id": "b", "demand": 10, "competition": 1, "setup_cost": 1},
            {"id": "a", "demand": 10, "competition": 4, "setup_cost": 5}]))
        assert [n["id"] for n in r["ranking"]] == ["b", "a"]
        assert r["blueprint_skeleton"]["worker_roles"]
        scope_ok(r)


class TestX10:
    def test_game_artifacts(self):
        r = x.x10_preproduction(dict(AOF, kind="game", title="Star Pet", themes=["cute"]))
        assert r["status"] == "preproduction_only"
        assert "design_doc" in r["artifacts"]
        scope_ok(r)

    def test_publish_refused(self):
        refuses("XREG_REFUSED_PUBLISH:publishing_and_monetization_stay_hers",
                x.x10_preproduction, dict(AOF, kind="anime", title="t", themes=[], publish=True))


class TestX11:
    def test_ev_arithmetic(self):
        r = x.x11_ev_ranker(dict(AOF, opportunities=[
            {"id": "a", "expected_return": 100, "cost": 10, "probability": 0.5},
            {"id": "b", "expected_return": 1000, "cost": 5, "probability": 0.01}]))
        assert r["ranking"][0] == {"id": "a", "expected_value": 40.0}
        assert r["ranking"][1]["expected_value"] == 5.0
        assert r["guarantee_language"] is False
        scope_ok(r)

    def test_guarantee_refused(self):
        refuses("XREG_REFUSED_GUARANTEE:income_cannot_be_guaranteed", x.x11_ev_ranker,
                dict(AOF, opportunities=[
                    {"id": "a", "expected_return": 1, "cost": 0, "probability": 1, "guaranteed": True}]))


class TestX12:
    def test_seeded_determinism_and_labels(self):
        a = x.x12_world_sim(dict(AOF, seed=42, agents=["ada"], steps=5))
        b = x.x12_world_sim(dict(AOF, seed=42, agents=["ada"], steps=5))
        assert a["events"] == b["events"]
        assert a["agents"] == [{"name": "ada", "synthetic": True}]
        scope_ok(a)

    def test_deceptive_refused(self):
        refuses("XREG_REFUSED_DECEPTIVE:synthetic_people_must_stay_labeled",
                x.x12_world_sim, dict(AOF, seed=1, agents=[], steps=1, deceptive_use=True))


class TestX13:
    def test_lenses_and_disclaimer(self):
        r = x.x13_style_lenses(dict(AOF, idea="solar panels for toys"))
        assert set(r["lenses"]) == set(x.LENSES)
        assert "not diagnosis" in r["disclaimer"]
        scope_ok(r)

    def test_clinical_refused(self):
        refuses("XREG_REFUSED_CLINICAL:no_diagnosis_or_condition_imitation",
                x.x13_style_lenses, dict(AOF, idea="x", diagnose=True))


class TestX14:
    def test_packet_and_verbatim(self):
        r = x.x14_claim_packet(dict(AOF, unit_id="c30.x", excerpt="do X",
                                    code_summary="does X bounded", tests="12 tests",
                                    responses=[{"validator": "claude", "text": "gap: none"}]))
        assert r["packet"]["question"] == "does this code implement the excerpt; list gaps"
        assert r["responses"] == [{"validator": "claude", "text": "gap: none"}]
        assert r["verdict_semantics"] == "evidence_not_approval"
        scope_ok(r)

    def test_unknown_validator(self):
        refuses("XREG_REFUSED_BAD_TYPE:validator", x.x14_claim_packet,
                dict(AOF, unit_id="u", excerpt="e", code_summary="c", tests="t",
                     responses=[{"validator": "gpt5", "text": "x"}]))


class TestX15:
    def test_shard_arithmetic(self):
        r = x.x15_shard_planner(dict(AOF, items=10, shard_size=4))
        assert r["shard_count"] == 3
        assert r["resume_tokens_preview"] == ["shard-0-of-3", "shard-1-of-3", "shard-2-of-3"]
        assert r["compute_agnostic"] is True
        scope_ok(r)

    def test_spend_refused(self):
        refuses("XREG_REFUSED_SPEND",
                x.x15_shard_planner, dict(AOF, items=1, shard_size=1, purchase=True))


class TestX16:
    def test_export_analysis(self):
        r = x.x16_export_analyzer(dict(AOF, export_kind="instagram", records=[
            {"id": "1", "kind": "like", "text": "pastel perfume bottles"},
            {"id": "2", "kind": "follow", "text": "pastel everything"}]))
        assert r["per_kind"] == {"follow": 1, "like": 1}
        assert r["themes"][0] == "pastel"
        scope_ok(r)

    def test_third_party_private_refused(self):
        refuses("XREG_REFUSED_THIRDPARTYPRIVATE:private_data_of_others_refused",
                x.x16_export_analyzer,
                dict(AOF, export_kind="pasted", records=[], third_party_private=True))


class TestX17:
    def test_assembly_measured_pages(self):
        r = x.x17_masterplan_assembler(dict(AOF, sections=[
            {"id": "s1", "source_ref": "doc1", "content": "x" * 9000},
            {"id": "s2", "source_ref": None, "content": "y" * 100}]))
        assert r["unsourced"] == ["s2"]
        assert r["page_estimate"] == 3
        assert r["sections"][0]["mark"] == "sourced"
        scope_ok(r)


class TestX18:
    def test_pipeline_ends_at_approval(self):
        r = x.x18_scan_to_approval(dict(AOF, items=[
            {"id": "1", "text": "scholarship for builders"},
            {"id": "2", "text": "builders meetup"}]))
        assert r["scanned"] == 2
        assert all(d["status"] == "pending_approval" for d in r["drafts"])
        scope_ok(r)

    def test_outreach_refused(self):
        refuses("XREG_REFUSED_OUTREACH",
                x.x18_scan_to_approval, dict(AOF, items=[], outreach=True))


class TestX19:
    def test_capacity_math(self):
        r = x.x19_builder_scheduler(dict(AOF, jobs=1000, concurrency_cap=7))
        assert r["queued"] == 1000 and r["waves"] == 143
        assert r["actual_concurrency"] == 7
        assert r["concurrency_basis"] == "configured_cap_not_measured_hardware"
        scope_ok(r)

    def test_overcap_refused(self):
        refuses("XREG_REFUSED_OVERCAP:queue_capacity_is_1000",
                x.x19_builder_scheduler, dict(AOF, jobs=1001, concurrency_cap=1))


class TestX20:
    def test_deltas(self):
        r = x.x20_measured_deltas(dict(AOF, axes={"tests": {"before": 10, "after": 25},
                                                  "zero": {"before": 0, "after": 3}}))
        assert r["axes"]["tests"] == {"delta": 15, "pct": 1.5}
        assert r["axes"]["zero"] == {"delta": 3, "pct": None}
        scope_ok(r)

    def test_multiplier_refused(self):
        refuses("XREG_REFUSED_NOUNIT:multiplier_claims_have_no_unit",
                x.x20_measured_deltas, dict(AOF, axes={}, multiplier=True))


class TestX21:
    def test_test_gated_count(self):
        r = x.x21_concept_registry(dict(AOF, concepts=[
            {"name": "global workspace", "test_passed": True},
            {"name": "sketch", "test_passed": False}]))
        assert r["registered"] == 2 and r["passing"] == 1
        assert r["counted_concepts"] == ["global workspace"]
        assert r["count_basis"] == "test_gated"
        scope_ok(r)


class TestX22:
    def test_complete_packet_submit_gated(self):
        r = x.x22_prefill_complete(dict(AOF, application_id="app1",
                                        fields={"name": "", "essay": "draft"},
                                        profile={"name": "Sam"}))
        assert r["complete"] is True
        assert r["prefilled"] == {"essay": "draft", "name": "Sam"}
        assert r["submit"] == "user_only"
        scope_ok(r)

    def test_submit_refused(self):
        refuses("XREG_REFUSED_OUTREACH",
                x.x22_prefill_complete,
                dict(AOF, application_id="a", fields={}, profile={}, submit=True))


class TestX23:
    def test_legality_split(self):
        r = x.x23_source_legality(dict(AOF, sites=[
            {"url": "https://free.edu", "free_public": True, "tos_checked": True, "license": "cc0"},
            {"url": "https://paywall.com", "free_public": False, "tos_checked": True, "license": "paid"},
            {"url": "https://unchecked.io", "free_public": True, "tos_checked": False, "license": "mit"}]))
        assert r["ingestible_count"] == 1
        assert r["excluded"][0]["reasons"] == ["not_free_public"]
        assert r["excluded"][1]["reasons"] == ["tos_unchecked"]
        scope_ok(r)


class TestX24:
    def test_seed_plus_validated(self):
        r = x.x24_open_book_collections(dict(AOF, add=[
            {"name": "arXiv", "url": "https://arxiv.org", "public_domain": True}]))
        assert r["seed_count"] == 6 and "arXiv" in r["collections"]
        scope_ok(r)

    def test_piracy_refused(self):
        refuses("XREG_REFUSED_PIRACY:copyrighted_pirate_sources_refused",
                x.x24_open_book_collections, dict(AOF, add=[], pirate=True))

    def test_non_public_domain_add_refused(self):
        refuses("XREG_REFUSED_PIRACY:public_domain_only", x.x24_open_book_collections,
                dict(AOF, add=[{"name": "libgen", "url": "http://x", "public_domain": False}]))


class TestX25:
    def test_claims(self):
        r = x.x25_patent_claim_drafter(dict(AOF, title="scent printer", features=["nozzle array"],
                                            prior_art_refs=["us1234"]))
        assert r["claims"][0].startswith("1. A method for scent printer")
        assert len(r["claims"]) == 2
        assert r["status"] == "draft_only"
        scope_ok(r)

    def test_prior_art_required(self):
        refuses("XREG_REFUSED_PRIORART_MISSING:prior_art_search_record_required",
                x.x25_patent_claim_drafter,
                dict(AOF, title="t", features=[], prior_art_refs=[]))

    def test_filing_refused(self):
        refuses("XREG_REFUSED_FILE:filing_is_hers", x.x25_patent_claim_drafter,
                dict(AOF, title="t", features=[], prior_art_refs=["r"], file=True))


class TestX26:
    def test_templates(self):
        r = x.x26_hustle_templates(dict(AOF, paths=["tutoring"]))
        assert r["templates"][0]["test_plan"].startswith("one small no-spend")
        scope_ok(r)

    def test_impersonate_refused(self):
        refuses("XREG_REFUSED_IMPERSONATE:no_employment_impersonation",
                x.x26_hustle_templates, dict(AOF, paths=[], impersonate=True))


class TestX27:
    def test_thresholds(self):
        r = x.x27_science_criteria_checker(dict(AOF, projects=[
            {"id": "p1", "datasets": 120, "tools": 40, "outcome_claims": ["award"]},
            {"id": "p2", "datasets": 119, "tools": 40, "outcome_claims": []}]))
        assert r["results"][0]["datasets_ok"] is True
        assert r["results"][0]["outcome_claims"] == "not_checkable"
        assert r["results"][1]["datasets_ok"] is False
        assert r["thresholds"] == {"datasets": 120, "tools": 40}
        scope_ok(r)


class TestX28:
    ROWS = [{"id": "u1", "status": "IMPLEMENTED-BOUNDED"}, {"id": "x1", "status": "SUBSTITUTE"}]

    def test_blocked_and_ack_flow(self):
        refuses("XREG_REFUSED_CANDY_EARLY:line_is_never_auto_sent", x.x28_release_gate,
                dict(AOF, rows=[], user_acknowledged_substitutes=False, auto_send=True))
        r = x.x28_release_gate(dict(AOF, rows=[{"id": "u2", "status": "OPEN"}],
                                    user_acknowledged_substitutes=False))
        assert r["release"] == "blocked" and r["blockers"] == ["u2"]
        r = x.x28_release_gate(dict(AOF, rows=self.ROWS, user_acknowledged_substitutes=False))
        assert r["release"] == "awaiting_user_acknowledgment"
        assert r["substitutes"] == ["x1"] and r["candy_line"] == "withheld"
        r = x.x28_release_gate(dict(AOF, rows=self.ROWS, user_acknowledged_substitutes=True))
        assert r["release"] == "ready" and r["candy_line"] == "withheld"
        scope_ok(r)


class TestX29:
    def test_measured_board(self):
        r = x.x29_benchmark_board(dict(AOF, benchmarks=[
            {"name": "gsm8k", "ours": 0.9, "baseline": 0.8},
            {"name": "arc", "ours": 0.5, "baseline": 0.7}]))
        assert r["wins"] == 1
        assert r["board"][1]["delta"] == round(0.9 - 0.8, 6)
        assert all(b["claimed"] == "measured" for b in r["board"])
        scope_ok(r)

    def test_unmeasured_refused(self):
        refuses("XREG_REFUSED_UNMEASURED:claims_require_measurement",
                x.x29_benchmark_board, dict(AOF, benchmarks=[], claim_unmeasured=True))


class TestX30:
    def test_plan_never_executes(self):
        r = x.x30_install_gate(dict(AOF, installs=[{"tool": "ripgrep", "approved": True}]))
        assert r["plan"] == [{"tool": "ripgrep", "planned": True}]
        assert r["executed"] is False
        scope_ok(r)

    def test_unapproved_refused(self):
        refuses("XREG_REFUSED_UNAPPROVED_INSTALL:her_approval_required_per_install",
                x.x30_install_gate, dict(AOF, installs=[{"tool": "x", "approved": False}]))


class TestCoverageHonesty:
    """Counts are computed from input, never asserted; no all/every claims."""
    def test_empty_inputs_report_zero(self):
        assert x.x02_corpus_analyzer(dict(AOF, posts=[]))["corpus_size"] == 0
        assert x.x19_builder_scheduler(dict(AOF, jobs=0, concurrency_cap=5))["queued"] == 0
        assert x.x21_concept_registry(dict(AOF, concepts=[]))["passing"] == 0
