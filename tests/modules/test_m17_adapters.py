from uuid import uuid4

import pytest

from app.modules.m17_advice_essay.adapters import CollectionPolicy, GuardedPublicCollector
from app.modules.m17_advice_essay.schemas import SourceKind


class Client:
    def __init__(self): self.called = False
    def fetch_public(self, canonical_url): self.called = True; return "Use concrete scenes.", "Writer"


def test_collector_enforces_https_and_host_allowlist_before_fetch():
    client = Client(); collector = GuardedPublicCollector(client, CollectionPolicy(frozenset({"api.example.org"})))
    with pytest.raises(ValueError, match="HTTPS"):
        collector.collect(owner_id=uuid4(), platform="example", canonical_url="http://api.example.org/post")
    with pytest.raises(ValueError, match="approved"):
        collector.collect(owner_id=uuid4(), platform="example", canonical_url="https://evil.example/post")
    assert not client.called


def test_collector_builds_provenance_bound_public_api_source():
    client = Client(); collector = GuardedPublicCollector(client, CollectionPolicy(frozenset({"api.example.org"})))
    source = collector.collect(owner_id=uuid4(), platform="example", canonical_url="https://api.example.org/post/1")
    assert source.source_kind == SourceKind.PUBLIC_API
    assert source.canonical_url == "https://api.example.org/post/1"
    assert source.creator == "Writer"
