"""Row 64 delta: run the real pipeline over 210 locally generated sources and check retrieval,
citation, conflict, restart and deletion behave. This is a pipeline scale/behaviour test over
SYNTHETIC local text. It is not evidence of a real 200-source corpus and not of 'learning into
Atlas'; both stay PARTIAL."""
import hashlib
import random
import pytest
from test_m25_knowledge_ingestion import src, pipe, ingest
from app.modules.m25_knowledge_copilot_training.pipeline import ConsentError, KnowledgeError, UnsupportedClaim
from app.modules.m25_knowledge_copilot_training.schemas import Citation, Claim

N = 210


def token(i):
    return "zq%04dx" % i


def build(tmp_path):
    p = pipe(tmp_path)
    for i in range(N):
        ingest(p, src("s%d" % i), text="Source %d states %s clearly.\n\nUnrelated filler %d." % (i, token(i), i * 7))
    return p


def test_210_sources_each_retrievable_by_its_own_token_and_cited(tmp_path):
    p = build(tmp_path)
    assert len(p.records) == N
    for i in random.Random(64).sample(range(N), 40):
        hit = p.search(token(i), limit=1)
        assert hit and hit[0]["source_id"] == "s%d" % i and token(i) in hit[0]["text"]
    i = 123
    q = "Source %d states %s clearly." % (i, token(i))
    c = Citation(source_id="s%d" % i, version=1, anchor_ids=["paragraph-1"], quote_hash=hashlib.sha256(q.encode()).hexdigest())
    assert p.substantiate([Claim(text=token(i), citations=[c])])
    wrong = Citation(source_id="s5", version=1, anchor_ids=["paragraph-1"], quote_hash=hashlib.sha256(q.encode()).hexdigest())
    with pytest.raises(UnsupportedClaim):
        p.substantiate([Claim(text=token(i), citations=[wrong])])
    with pytest.raises(UnsupportedClaim):
        p.substantiate([Claim(text="never ingested")])


def test_consent_gate_holds_at_scale_and_other_tenant_denied(tmp_path):
    p = build(tmp_path)
    bad = src("noconsent")
    bad.consent.purposes = ["other"]
    with pytest.raises(ConsentError):
        ingest(p, bad)
    assert "noconsent" not in p.records and len(p.records) == N
    with pytest.raises(KnowledgeError):
        p.search(token(1), tenant_id="tenant-b")


def test_dedup_and_new_version_do_not_duplicate_sources(tmp_path):
    p = build(tmp_path)
    again = ingest(p, src("s3"), text="Source 3 states %s clearly.\n\nUnrelated filler %d." % (token(3), 21))
    assert again.number == 1 and len(p.records) == N
    v2 = ingest(p, src("s3"), text="Source 3 now states %s differently." % token(3))
    assert v2.number == 2 and len(p.records) == N


def test_delete_removes_source_from_retrieval_only(tmp_path):
    p = build(tmp_path)
    p.delete_verified("s7")
    assert not [h for h in p.search(token(7), limit=5) if h["source_id"] == "s7"]
    assert p.search(token(8), limit=1)[0]["source_id"] == "s8"


def test_restart_restore_requires_attestation_and_preserves_retrieval(tmp_path):
    from app.modules.m25_knowledge_copilot_training.recovery import RecoveryError
    p = build(tmp_path)
    fresh = pipe(tmp_path)
    with pytest.raises(RecoveryError):
        fresh.restore_verified()
    assert fresh.records == {}
    fresh.restore_verified(same_adapters_attested=True)
    assert len(fresh.records) == N
    assert fresh.search(token(150), limit=1)[0]["source_id"] == "s150"
