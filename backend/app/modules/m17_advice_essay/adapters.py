"""Ports and guarded adapters for Module 17 external capabilities.

No network clients are imported or created here. The host app injects approved API,
transcription, embedding, and model implementations. This keeps imports offline and
prevents the module from silently scraping logged-in sessions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .schemas import AdviceSource, SourceKind


class PublicContentClient(Protocol):
    def fetch_public(self, canonical_url: str) -> tuple[str, str | None]:
        """Return public text and creator attribution from an approved API/page."""


class Transcriber(Protocol):
    def transcribe(self, media: bytes, mime_type: str) -> str: ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class CollectionPolicy:
    allowed_hosts: frozenset[str]
    max_content_chars: int = 100_000
    require_public_api: bool = True


class GuardedPublicCollector:
    """Collect from explicit allowlisted public URLs through an injected client.

    Cookie/login inputs, proxies, account creation, engagement, and browser evasion
    are intentionally absent from this contract.
    """

    def __init__(self, client: PublicContentClient, policy: CollectionPolicy) -> None:
        self.client = client
        self.policy = policy

    def collect(self, *, owner_id, platform: str, canonical_url: str) -> AdviceSource:
        from urllib.parse import urlparse

        parsed = urlparse(canonical_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("only canonical HTTPS public URLs are accepted")
        if parsed.hostname.lower() not in self.policy.allowed_hosts:
            raise ValueError("host is not approved for public collection")
        content, creator = self.client.fetch_public(canonical_url)
        if not content.strip():
            raise ValueError("public source returned no content")
        if len(content) > self.policy.max_content_chars:
            raise ValueError("public source exceeds collection size limit")
        return AdviceSource(
            owner_id=owner_id,
            source_kind=SourceKind.PUBLIC_API if self.policy.require_public_api else SourceKind.PUBLIC_WEB,
            platform=platform,
            canonical_url=canonical_url,
            creator=creator,
            content=content,
            permission_basis="public content collected through an approved adapter",
        )
