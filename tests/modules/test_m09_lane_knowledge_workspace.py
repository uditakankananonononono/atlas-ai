from datetime import datetime, timezone
from itertools import count

import pytest

from app.modules.m09_knowledge_workspace.lane_models import ConflictError, KnowledgeError, Relation, SourceRef, SuggestionStatus
from app.modules.m09_knowledge_workspace.lane_service import KnowledgeWorkspace


def workspace():
    ids = count(1)
    return KnowledgeWorkspace(clock=lambda: datetime(2026, 9, 20, tzinfo=timezone.utc), id_factory=lambda: f"id-{next(ids)}")


def test_versioning_is_immutable_and_optimistically_locked():
    kb = workspace()
    first = kb.create_document(document_id="d1", title="Atlas", content="initial knowledge", actor_id="u", source_refs=[SourceRef("https://example.test/a")])
    second = kb.update_document("d1", actor_id="u", expected_version=1, content="revised knowledge")
    assert (first.version, first.content) == (1, "initial knowledge")
    assert (second.version, second.previous_version) == (2, 1)
    assert [v.content for v in kb.history("d1")] == ["initial knowledge", "revised knowledge"]
    with pytest.raises(ConflictError, match="stale"):
        kb.update_document("d1", actor_id="u", expected_version=1, content="lost update")


def test_provenance_graph_traverses_both_directions_and_deduplicates():
    kb = workspace()
    for doc in "abc":
        kb.create_document(document_id=doc, title=doc, content=f"content {doc}", actor_id="u")
    edge1 = kb.add_provenance(source_document_id="a", target_document_id="b", relation=Relation.SUPPORTS, actor_id="u")
    assert kb.add_provenance(source_document_id="a", target_document_id="b", relation="supports", actor_id="u") == edge1
    kb.add_provenance(source_document_id="b", target_document_id="c", relation="derived_from", actor_id="u")
    assert len(kb.provenance_graph("a", direction="outgoing", max_depth=1)) == 1
    assert len(kb.provenance_graph("b", direction="both", max_depth=2)) == 2
    with pytest.raises(KnowledgeError, match="self-referential"):
        kb.add_provenance(source_document_id="a", target_document_id="a", relation="references", actor_id="u")


def test_retrieval_uses_latest_version_ranking_and_metadata_filter():
    kb = workspace()
    kb.create_document(document_id="bio", title="Protein folding", content="AlphaFold structure biology", actor_id="u", metadata={"team": "science"})
    kb.create_document(document_id="sales", title="Sales", content="pipeline and outreach", actor_id="u", metadata={"team": "growth"})
    kb.update_document("bio", actor_id="u", expected_version=1, content="AlphaFold protein protein evidence")
    hits = kb.retrieve("protein evidence", metadata_filter={"team": "science"})
    assert len(hits) == 1 and hits[0].document.version == 2
    assert hits[0].matched_terms == ("protein", "evidence")
    assert kb.retrieve("protein", metadata_filter={"team": "growth"}) == ()


def test_suggestion_accept_creates_version_and_cannot_repeat():
    kb = workspace()
    kb.create_document(document_id="d", title="Old", content="old body", actor_id="author")
    suggestion = kb.propose_change("d", proposer_id="agent", base_version=1, rationale="new evidence", proposed_content="new body")
    accepted = kb.decide_suggestion(suggestion.suggestion_id, reviewer_id="reviewer", accept=True, note="checked")
    assert accepted.status is SuggestionStatus.ACCEPTED
    assert accepted.resulting_version == 2
    assert kb.get_document("d").content == "new body"
    with pytest.raises(ConflictError, match="already"):
        kb.decide_suggestion(suggestion.suggestion_id, reviewer_id="reviewer", accept=False)


def test_stale_suggestion_requires_rebase_and_rejection_does_not_edit():
    kb = workspace()
    kb.create_document(document_id="d", title="T", content="one", actor_id="u")
    stale = kb.propose_change("d", proposer_id="a", base_version=1, rationale="change", proposed_content="proposed")
    kb.update_document("d", actor_id="u", expected_version=1, content="two")
    with pytest.raises(ConflictError, match="stale"):
        kb.decide_suggestion(stale.suggestion_id, reviewer_id="r", accept=True)
    rejection = kb.decide_suggestion(stale.suggestion_id, reviewer_id="r", accept=False)
    assert rejection.status is SuggestionStatus.REJECTED
    assert kb.get_document("d").version == 2


def test_audit_is_ordered_filterable_and_records_material_actions():
    kb = workspace()
    kb.create_document(document_id="d", title="T", content="body", actor_id="u")
    suggestion = kb.propose_change("d", proposer_id="agent", base_version=1, rationale="fix", proposed_title="Better")
    kb.decide_suggestion(suggestion.suggestion_id, reviewer_id="u", accept=True)
    audit = kb.audit_history()
    assert [event.sequence for event in audit] == list(range(1, len(audit) + 1))
    assert [event.action for event in audit] == ["document.created", "suggestion.created", "document.updated", "suggestion.accepted"]
    assert len(kb.audit_history(actor_id="agent")) == 1
    assert kb.document_fingerprint("d") == kb.document_fingerprint("d", 2)


def test_diff_and_restore_preserve_history_and_audit_reason():
    kb = workspace()
    kb.create_document(document_id="d", title="Original", content="line one\nline two\n", actor_id="u", metadata={"kind": "note"})
    kb.update_document("d", actor_id="u", expected_version=1, title="Changed", content="line one\nnew line\n")
    diff = kb.diff_versions("d", 1, 2)
    assert "--- d@1" in diff and "+++ d@2" in diff
    assert "-# Original" in diff and "+# Changed" in diff
    restored = kb.restore_version("d", restore_version=1, expected_version=2, actor_id="reviewer", reason="bad source")
    assert restored.version == 3 and restored.title == "Original"
    assert restored.metadata["restored_from_version"] == 1
    assert [event.action for event in kb.audit_history()][-2:] == ["document.updated", "document.restored"]
    assert kb.audit_history()[-1].details["reason"] == "bad source"


def test_provenance_path_is_shortest_directed_and_depth_bounded():
    kb = workspace()
    for doc in "abcd":
        kb.create_document(document_id=doc, title=doc, content=f"body {doc}", actor_id="u")
    kb.add_provenance(source_document_id="a", target_document_id="b", relation="references", actor_id="u")
    kb.add_provenance(source_document_id="b", target_document_id="c", relation="supports", actor_id="u")
    kb.add_provenance(source_document_id="a", target_document_id="d", relation="derived_from", actor_id="u")
    kb.add_provenance(source_document_id="d", target_document_id="c", relation="supports", actor_id="u")
    path = kb.provenance_path("a", "c")
    assert len(path) == 2
    assert path[0].source_document_id == "a" and path[-1].target_document_id == "c"
    assert kb.provenance_path("c", "a") == ()
    assert kb.provenance_path("a", "c", max_depth=1) == ()


def test_audit_history_is_hash_chained_and_integrity_verifiable():
    from dataclasses import replace

    kb = workspace()
    kb.create_document(document_id="d", title="T", content="body", actor_id="u")
    kb.update_document("d", actor_id="u", expected_version=1, content="changed")
    events = kb.audit_history()
    assert kb.verify_audit_integrity()
    assert events[0].previous_hash == ""
    assert events[1].previous_hash == events[0].event_hash
    assert len(events[0].event_hash) == 64

    # Simulate storage tampering to prove verification fails closed.
    kb.store._audit[0] = replace(events[0], action="document.deleted")
    assert not kb.verify_audit_integrity()


def test_exposed_document_metadata_and_audit_details_are_immutable():
    kb = workspace()
    document = kb.create_document(document_id="d", title="T", content="body", actor_id="u", metadata={"team": "science"})
    with pytest.raises(TypeError):
        document.metadata["team"] = "attacker"
    event = kb.audit_history()[0]
    with pytest.raises(TypeError):
        event.details["version"] = 99
    assert kb.verify_audit_integrity()
