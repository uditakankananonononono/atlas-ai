"""Verified contact enrichment via official, keyed provider APIs.

Ledger rows: Clearbit enrichment (CRM-131) and Hunter.io enrichment
(CRM-132). Both providers are optional adapters: without an API key the
adapter raises EnrichmentNotConfiguredError, so the module never has a
required paid dependency and never falls back to stealth scraping.

Safety rules enforced here:

- Provider keys come from the caller (environment in routes, explicit
  argument in tests) and are never returned, logged, or embedded in
  error messages.
- A contact's email is marked verified only when a provider's verifier
  returns a deliverable/valid verdict. Finder output alone is never
  treated as verified.
- Enrichment never overwrites a user-set field. Empty fields may be
  filled; occupied fields get a recorded suggestion instead.
- Every enrichment write goes through the repository, so the append-only
  change log records exactly what changed and which provider supplied it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field

from .schemas import Contact
from .service import ContactNotFoundError, ContactRepository


class EnrichmentError(RuntimeError):
    """Base class for enrichment failures."""


class EnrichmentNotConfiguredError(EnrichmentError):
    """Raised when a provider adapter has no API key configured."""


class UpstreamEnrichmentError(EnrichmentError):
    """Raised when a provider API rejects or fails a request."""


VerificationStatus = Literal["valid", "risky", "invalid", "unknown"]


class EmailVerification(BaseModel):
    """Normalized verifier verdict for one address."""

    email: str
    status: VerificationStatus
    score: int = Field(ge=0, le=100)
    provider: str
    checked_at: datetime
    detail: dict[str, Any] = Field(default_factory=dict)


class EmailFinderResult(BaseModel):
    """Normalized finder result: a candidate address plus public provenance."""

    email: str | None
    confidence: int = Field(ge=0, le=100)
    provider: str
    sources: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class PersonProfile(BaseModel):
    """Normalized person-profile lookup result (Clearbit-style)."""

    found: bool
    pending: bool = False
    full_name: str | None = None
    organization: str | None = None
    title: str | None = None
    location: str | None = None
    provider: str
    detail: dict[str, Any] = Field(default_factory=dict)


class EnrichmentProvider(Protocol):
    """Async boundary every enrichment adapter implements."""

    name: str

    async def find_email(self, *, domain: str, full_name: str) -> EmailFinderResult: ...
    async def verify_email(self, *, email: str) -> EmailVerification: ...


class PersonProfileProvider(Protocol):
    """Optional adapter boundary for person-profile lookups."""

    name: str

    async def lookup_person(self, *, email: str) -> PersonProfile: ...


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HunterIoClient:
    """Official Hunter.io v2 API adapter with an injected HTTP client.

    Hunter authenticates with an ``api_key`` query parameter (the only
    method the v2 API documents). The key is attached at request time and
    never appears in exceptions, results, or logs.
    """

    name = "hunter"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        base_url: str = "https://api.hunter.io/v2",
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _key(self) -> str:
        if not self._api_key:
            raise EnrichmentNotConfiguredError(
                "Hunter.io enrichment is not configured: set HUNTER_API_KEY"
            )
        return self._api_key

    async def find_email(self, *, domain: str, full_name: str) -> EmailFinderResult:
        first, last = _split_name(full_name)
        response = await self._client.get(
            f"{self._base_url}/email-finder",
            params={
                "domain": domain,
                "first_name": first,
                "last_name": last,
                "api_key": self._key(),
            },
        )
        if response.is_error:
            raise UpstreamEnrichmentError(
                f"Hunter.io email-finder failed ({response.status_code})"
            )
        data = response.json().get("data") or {}
        sources = [
            str(item.get("uri"))
            for item in data.get("sources") or []
            if item.get("uri")
        ]
        return EmailFinderResult(
            email=data.get("email"),
            confidence=int(data.get("score") or 0),
            provider=self.name,
            sources=sources,
            detail={"domain": domain},
        )

    async def verify_email(self, *, email: str) -> EmailVerification:
        response = await self._client.get(
            f"{self._base_url}/email-verifier",
            params={"email": email, "api_key": self._key()},
        )
        if response.is_error:
            raise UpstreamEnrichmentError(
                f"Hunter.io email-verifier failed ({response.status_code})"
            )
        data = response.json().get("data") or {}
        return EmailVerification(
            email=email,
            status=_normalize_hunter_status(str(data.get("status") or data.get("result") or "unknown")),
            score=int(data.get("score") or 0),
            provider=self.name,
            checked_at=_utcnow(),
            detail={"result": data.get("result"), "regexp": data.get("regexp")},
        )


def _normalize_hunter_status(raw: str) -> VerificationStatus:
    raw = raw.lower()
    if raw in {"valid", "deliverable"}:
        return "valid"
    if raw in {"invalid", "undeliverable"}:
        return "invalid"
    if raw in {"accept_all", "risky", "webmail", "disposable"}:
        return "risky"
    return "unknown"


class ClearbitClient:
    """Official Clearbit person-lookup adapter with an injected HTTP client.

    Uses Bearer authentication against the documented v2 combined/find
    endpoint. 200 means a profile, 202 means the lookup is queued, 404
    means no record. The key never appears in exceptions or results.
    """

    name = "clearbit"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        base_url: str = "https://person.clearbit.com/v2",
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise EnrichmentNotConfiguredError(
                "Clearbit enrichment is not configured: set CLEARBIT_API_KEY"
            )
        return {"Authorization": f"Bearer {self._api_key}"}

    async def lookup_person(self, *, email: str) -> PersonProfile:
        response = await self._client.get(
            f"{self._base_url}/combined/find",
            params={"email": email},
            headers=self._headers(),
        )
        if response.status_code == 404:
            return PersonProfile(found=False, provider=self.name)
        if response.status_code == 202:
            return PersonProfile(found=False, pending=True, provider=self.name)
        if response.is_error:
            raise UpstreamEnrichmentError(
                f"Clearbit person lookup failed ({response.status_code})"
            )
        data = response.json()
        person = data.get("person") or {}
        employment = person.get("employment") or {}
        name = person.get("name") or {}
        return PersonProfile(
            found=True,
            full_name=name.get("fullName") or None,
            organization=employment.get("name") or None,
            title=employment.get("title") or None,
            location=person.get("location") or None,
            provider=self.name,
        )


class EnrichmentService:
    """Apply provider enrichment to stored contacts under strict safety rules."""

    def __init__(
        self,
        repository: ContactRepository,
        finder: EnrichmentProvider,
        profiler: PersonProfileProvider | None = None,
        clock: Any = None,
    ) -> None:
        self.repository = repository
        self.finder = finder
        self.profiler = profiler
        self._clock = clock or _utcnow

    async def verify_contact_email(self, contact_id: str) -> EmailVerification:
        """Verify the stored address and record the verdict with provenance.

        The address itself is never changed; only the verification record
        in metadata is written, plus an append-only change-log entry.
        """
        contact = self._contact(contact_id)
        if not contact.email:
            raise ValueError("contact has no email address to verify")
        verdict = await self.finder.verify_email(email=contact.email)
        metadata = dict(contact.metadata)
        enrichment = dict(metadata.get("enrichment") or {})
        enrichment["email_verified"] = verdict.status == "valid"
        enrichment["email_verification"] = verdict.model_dump(mode="json")
        metadata["enrichment"] = enrichment
        self._save(
            contact,
            metadata=metadata,
            changes={
                "event": "email_verified",
                "provider": verdict.provider,
                "status": verdict.status,
                "score": verdict.score,
            },
        )
        return verdict

    async def find_contact_email(self, contact_id: str, domain: str) -> EmailFinderResult:
        """Find a candidate address for a contact that has none.

        A found address is filled only when the contact has no email; an
        occupied address is never overwritten - the candidate is recorded
        as a suggestion with its public sources for human review.
        """
        contact = self._contact(contact_id)
        if contact.email:
            raise ValueError("contact already has an email address; verify it instead")
        result = await self.finder.find_email(domain=domain, full_name=contact.name)
        metadata = dict(contact.metadata)
        enrichment = dict(metadata.get("enrichment") or {})
        update: dict[str, Any] = {"metadata": metadata}
        if result.email:
            enrichment["finder"] = result.model_dump(mode="json")
            update["email"] = result.email
            changes = {
                "event": "email_enriched",
                "provider": result.provider,
                "email": result.email,
                "confidence": result.confidence,
                "sources": result.sources,
            }
        else:
            enrichment["finder_attempt"] = {
                "provider": result.provider,
                "domain": domain,
                "found": False,
                "at": self._clock().isoformat(),
            }
            changes = {"event": "email_enrichment_miss", "provider": result.provider}
        metadata["enrichment"] = enrichment
        self._save(contact, changes=changes, **update)
        return result

    async def enrich_contact_profile(self, contact_id: str) -> PersonProfile:
        """Fill empty profile fields from a person-profile provider.

        Only empty fields are filled. The provider's values for occupied
        fields are recorded under metadata.enrichment.profile for review.
        """
        if self.profiler is None:
            raise EnrichmentNotConfiguredError("no person-profile provider is configured")
        contact = self._contact(contact_id)
        if not contact.email:
            raise ValueError("contact has no email address for profile lookup")
        profile = await self.profiler.lookup_person(email=contact.email)
        if not profile.found:
            return profile
        metadata = dict(contact.metadata)
        enrichment = dict(metadata.get("enrichment") or {})
        enrichment["profile"] = profile.model_dump(mode="json")
        metadata["enrichment"] = enrichment
        update: dict[str, Any] = {"metadata": metadata}
        filled: list[str] = []
        if not contact.institution and profile.organization:
            update["institution"] = profile.organization
            filled.append("institution")
        self._save(
            contact,
            changes={
                "event": "profile_enriched",
                "provider": profile.provider,
                "filled": filled,
            },
            **update,
        )
        return profile

    def _contact(self, contact_id: str) -> Contact:
        contact = self.repository.get(contact_id)
        if contact is None:
            raise ContactNotFoundError(contact_id)
        return contact

    def _save(self, contact: Contact, changes: dict[str, Any], **update: Any) -> Contact:
        updated = contact.model_copy(
            update={
                **update,
                "updated_at": self._clock(),
                "version": contact.version + 1,
            }
        )
        return self.repository.save(updated, changes)
