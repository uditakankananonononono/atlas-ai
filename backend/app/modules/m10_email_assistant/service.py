"""Domain logic for the Email Assistant (module 10).

Spec reference: user directive, Module 10.
- Gmail OAuth 2.0 connect, Google Cloud Pub/Sub push ingestion, embedding
  into tenant storage (LTM seam via core.vector_store is integrator work).
- Seven-label categorisation (fine-tuned BERT pluggable; deterministic
  fallback), LLM action extraction with the spec output schema.
- Drafting replies with a context window of recent related emails plus an
  optional knowledge-graph hook (module 9 seam). Drafts are proposed to the
  Approval Center. This module has no send path: executing an approved
  "send_email_reply" is the approval dispatcher's job (workers seam).

Advancement pass beyond spec: idempotent ingestion on (tenant, gmail_id),
history-id checkpointing, watch renewal, sender-frequency priority inbox,
List-Unsubscribe detection, deadline follow-up surfacing, append-only audit.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Protocol
from uuid import uuid4

import httpx

from app.core.models import ApprovalRequest
from app.core.providers import generate
from app.core.token_crypto import TokenCipher

from .classifier import Classification, ClassifierInput, EmailClassifier, configured_classifier
from .extraction import GenerateFn, extract_actions
from .gmail import (
    GmailClient,
    GmailRawMessage,
    OAuthTokens,
    exchange_code,
    refresh_access_token,
)
from .schemas import (
    ACTIONABLE_CATEGORIES,
    ActionItem,
    EmailCategory,
    EmailDraftView,
    EmailMessageView,
    GmailAccountView,
    IngestResult,
    PriorityMessage,
    WatchRenewalResult,
)
from .sql_repository import EmailMessageRow, SqlEmailRepository


class PubSubVerificationError(PermissionError):
    """Raised when a Pub/Sub push carries the wrong verification token."""


class AccountNotFoundError(LookupError):
    pass


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class NullEmbedder:
    """Used when no embedding provider is configured (offline/tests)."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


class ApprovalSink(Protocol):
    def put(self, item: ApprovalRequest, *, user_id: str | None = None) -> ApprovalRequest: ...


GraphContextFn = Callable[[str], list[str]]  # module 9 seam: entity -> related facts

CATEGORY_PRIORITY_WEIGHT = {
    EmailCategory.ACTION_REQUIRED: 5.0,
    EmailCategory.PROFESSOR_REPLY: 4.0,
    EmailCategory.OPPORTUNITY: 3.5,
    EmailCategory.COLLABORATION: 3.0,
    EmailCategory.PERSONAL: 2.0,
    EmailCategory.NEWSLETTER: 0.5,
    EmailCategory.SPAM: 0.0,
}


class Service:
    def __init__(
        self,
        repository: SqlEmailRepository,
        approval_sink: ApprovalSink,
        gmail: GmailClient,
        http: httpx.AsyncClient,
        *,
        cipher: TokenCipher,
        google_client_id: str,
        google_client_secret: str,
        pubsub_verification_token: str,
        classifier: EmailClassifier | None = None,
        embedder: Embedder | None = None,
        llm_generate: GenerateFn = generate,
        graph_context: GraphContextFn | None = None,
        llm_provider: str = "openai",
        llm_model: str | None = None,
    ) -> None:
        self.repository = repository
        self.tenant_id = str(getattr(repository, "tenant_id", "")).strip()
        if not self.tenant_id:
            raise ValueError("tenant-scoped repository is required")
        self.approval_sink = approval_sink
        self.gmail = gmail
        self.http = http
        self.cipher = cipher
        self.google_client_id = google_client_id
        self.google_client_secret = google_client_secret
        self.pubsub_verification_token = pubsub_verification_token
        self.classifier = classifier or configured_classifier()
        self.embedder = embedder or NullEmbedder()
        self.llm_generate = llm_generate
        self.graph_context = graph_context
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    # -- OAuth connect -----------------------------------------------------
    def authorization_url(self, redirect_uri: str, state: str) -> str:
        from .gmail import build_authorization_url

        return build_authorization_url(self.google_client_id, redirect_uri, state)

    async def connect_account(self, auth_code: str, redirect_uri: str) -> GmailAccountView:
        tokens = await exchange_code(
            self.http,
            code=auth_code,
            client_id=self.google_client_id,
            client_secret=self.google_client_secret,
            redirect_uri=redirect_uri,
        )
        return await self._store_tokens(tokens)

    async def _store_tokens(self, tokens: OAuthTokens) -> GmailAccountView:
        profile = await self.gmail.get_profile(tokens.access_token)
        email_address = profile["emailAddress"]
        if not tokens.refresh_token:
            raise ValueError(
                "Google did not return a refresh token; reconnect with prompt=consent"
            )
        account_id = str(uuid4())
        now = datetime.now(timezone.utc)
        self.repository.save_account(
            account_id=account_id,
            email_address=email_address,
            encrypted_refresh_token=self.cipher.encrypt(tokens.refresh_token),
            history_id=str(profile.get("historyId")) if profile.get("historyId") else None,
            watch_expiration=None,
        )
        return GmailAccountView(
            id=account_id, email_address=email_address,
            history_id=str(profile.get("historyId")) if profile.get("historyId") else None,
            watch_expiration=None, created_at=now,
        )

    async def _access_token(self, account) -> str:
        refresh = self.cipher.decrypt(account.encrypted_refresh_token)
        return await refresh_access_token(
            self.http,
            refresh_token=refresh,
            client_id=self.google_client_id,
            client_secret=self.google_client_secret,
        )

    # -- Pub/Sub ingestion ---------------------------------------------------
    def decode_push(self, envelope: dict[str, Any], verification_token: str) -> tuple[str, str]:
        if verification_token != self.pubsub_verification_token:
            raise PubSubVerificationError("invalid Pub/Sub verification token")
        data_b64 = envelope.get("message", {}).get("data")
        if not data_b64:
            raise ValueError("Pub/Sub envelope has no message.data")
        padding = "=" * (-len(data_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(data_b64 + padding).decode())
        return payload["emailAddress"], str(payload["historyId"])

    async def handle_push(self, envelope: dict[str, Any], verification_token: str) -> IngestResult:
        email_address, history_id = self.decode_push(envelope, verification_token)
        return await self.ingest_from_history(email_address, history_id)

    async def ingest_from_history(self, email_address: str, history_id: str) -> IngestResult:
        account = self.repository.get_account_by_email(email_address)
        if account is None:
            raise AccountNotFoundError(email_address)
        access_token = await self._access_token(account)
        start = account.history_id or history_id
        message_ids = await self.gmail.list_history(access_token, start)
        fetched = len(message_ids)
        new_messages = 0
        drafts = 0
        for message_id in message_ids:
            if self.repository.has_message(message_id):
                continue
            raw = await self.gmail.get_message(access_token, message_id)
            drafted = await self._ingest_message(account.id, raw)
            new_messages += 1
            if drafted:
                drafts += 1
        self.repository.update_history_id(account.id, history_id)
        return IngestResult(
            email_address=email_address, history_id=history_id,
            fetched=fetched, new_messages=new_messages, drafts_proposed=drafts,
        )

    async def _ingest_message(self, account_id: str, raw: GmailRawMessage) -> bool:
        """Store, classify, extract, embed, and (when actionable) draft.
        Returns True when a reply draft was proposed."""
        classification: Classification = self.classifier.classify(
            ClassifierInput(
                subject=raw.subject, sender=raw.sender, snippet=raw.snippet,
                labels=raw.labels, headers=raw.headers,
            )
        )
        actions = await extract_actions(
            self.llm_generate,
            provider=self.llm_provider,
            model=self.llm_model,
            subject=raw.subject,
            body=raw.body_text,
        )
        embedding = (await self.embedder.embed([f"{raw.subject}\n{raw.body_text}"]))[0]
        unsubscribe_url = self._unsubscribe_url(raw.headers)
        received_at = (
            datetime.fromtimestamp(raw.received_at, tz=timezone.utc) if raw.received_at else None
        )
        message_id = str(uuid4())
        self.repository.save_message(
            message_id=message_id, account_id=account_id, gmail_id=raw.gmail_id,
            thread_id=raw.thread_id, history_id=raw.history_id, subject=raw.subject,
            sender=raw.sender, recipients=raw.recipients, snippet=raw.snippet,
            body_text=raw.body_text, received_at=received_at, labels=raw.labels,
            headers=raw.headers, category=classification.category.value,
            category_confidence=classification.confidence,
            embedding=embedding or None, unsubscribe_url=unsubscribe_url,
        )
        self.repository.save_action_items(
            message_id,
            [
                {"id": str(uuid4()), "action": item.action,
                 "deadline": item.deadline, "related_entity": item.related_entity,
                 "confidence": classification.confidence}
                for item in actions
            ],
        )
        if classification.category in ACTIONABLE_CATEGORIES and "SENT" not in raw.labels:
            await self._draft_reply(message_id, raw, classification, actions)
            return True
        return False

    @staticmethod
    def _unsubscribe_url(headers: dict[str, str]) -> str | None:
        raw = headers.get("list-unsubscribe", "")
        for part in raw.split(","):
            part = part.strip().strip("<>")
            if part.startswith("http"):
                return part
        return None

    # -- drafting (always approval-gated) -----------------------------------
    async def _draft_reply(
        self,
        message_id: str,
        raw: GmailRawMessage,
        classification: Classification,
        actions: list[ActionItem],
    ) -> EmailDraftView:
        context = self._context_window(raw)
        action_lines = "\n".join(f"- {a.action}" for a in actions) or "- (none extracted)"
        graph_facts: list[str] = self.graph_context(raw.sender) if self.graph_context else []
        graph_block = "\n".join(f"- {fact}" for fact in graph_facts) or "- (none)"
        prompt = (
            "Draft a concise, truthful reply to this email. Do not send it. Do not invent "
            "facts or commitments. Return exactly 'Subject: ...' followed by the body.\n"
            f"Category: {classification.category.value}\n"
            f"From: {raw.sender}\nSubject: {raw.subject}\n"
            f"Action items:\n{action_lines}\n"
            f"Related knowledge-graph facts:\n{graph_block}\n"
            f"Recent related emails (context window):\n{context}\n"
            f"Email body:\n{raw.body_text[:4000]}"
        )
        model, text = await self.llm_generate(prompt, self.llm_provider, self.llm_model)
        subject, body = self._parse_draft(text, raw.subject)
        draft_id = str(uuid4())
        approval = ApprovalRequest(
            id=str(uuid4()),
            module_id=10,
            action_type="send_email_reply",
            payload={
                "tenant_id": self.tenant_id,
                "draft_id": draft_id,
                "message_id": message_id,
                "gmail_id": raw.gmail_id,
                "thread_id": raw.thread_id,
                "to": raw.sender,
                "subject": subject,
                "body": body,
            },
        )
        self.approval_sink.put(approval, user_id=self.tenant_id)
        self.repository.save_draft(
            draft_id=draft_id, message_id=message_id, approval_id=approval.id,
            to=raw.sender, subject=subject, body=body, model=model,
        )
        return EmailDraftView(
            id=draft_id, message_id=message_id, approval_id=approval.id, to=raw.sender,
            subject=subject, body=body, model=model, created_at=datetime.now(timezone.utc),
        )

    def _context_window(self, raw: GmailRawMessage, max_chars: int = 6000) -> str:
        """Recent related emails: same thread first, then same sender."""
        pieces: list[str] = []
        total = 0
        seen = {raw.gmail_id}
        rows: list[EmailMessageRow] = []
        if raw.thread_id:
            rows.extend(self.repository.thread_messages(raw.thread_id, limit=5))
        for row in rows:
            if row.gmail_id in seen:
                continue
            seen.add(row.gmail_id)
            chunk = f"[{row.received_at}] {row.sender}: {row.subject}\n{row.snippet}\n"
            if total + len(chunk) > max_chars:
                break
            pieces.append(chunk)
            total += len(chunk)
        return "".join(pieces) or "(no prior context)"

    @staticmethod
    def _parse_draft(text: str, original_subject: str) -> tuple[str, str]:
        cleaned = text.strip()
        first, separator, rest = cleaned.partition("\n")
        if first.lower().startswith("subject:") and separator and rest.strip():
            return first.split(":", 1)[1].strip(), rest.strip()
        subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"
        return subject, cleaned

    # -- watch renewal --------------------------------------------------------
    async def renew_watches(self, topic: str, within_hours: int = 24) -> WatchRenewalResult:
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(hours=within_hours)
        renewed: list[str] = []
        skipped: list[str] = []
        for account in self.repository.list_accounts():
            expiration = account.watch_expiration
            if expiration is not None and expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)
            if expiration is not None and expiration > threshold:
                skipped.append(account.email_address)
                continue
            access_token = await self._access_token(account)
            info = await self.gmail.watch(access_token, topic)
            self.repository.update_watch_expiration(
                account.id,
                datetime.fromtimestamp(info.expiration_ms / 1000.0, tz=timezone.utc),
                info.history_id,
            )
            renewed.append(account.email_address)
        return WatchRenewalResult(renewed=renewed, skipped=skipped)

    # -- reads ----------------------------------------------------------------
    def list_accounts(self) -> list[GmailAccountView]:
        return [
            GmailAccountView(
                id=a.id, email_address=a.email_address, history_id=a.history_id,
                watch_expiration=a.watch_expiration, created_at=a.created_at,
            )
            for a in self.repository.list_accounts()
        ]

    def list_messages(self, category: EmailCategory | None = None, limit: int = 100) -> list[EmailMessageView]:
        return [
            self._message_view(row)
            for row in self.repository.list_messages(
                category=category.value if category else None, limit=limit)
        ]

    def list_action_items(self, status: str = "open") -> list[dict]:
        return [
            {
                "id": row.id, "message_id": row.message_id, "action": row.action,
                "deadline": row.deadline, "related_entity": row.related_entity,
                "confidence": row.confidence, "status": row.status,
            }
            for row in self.repository.list_action_items(status=status)
        ]

    def list_drafts(self) -> list[EmailDraftView]:
        return [
            EmailDraftView(
                id=row.id, message_id=row.message_id, approval_id=row.approval_id,
                to=row.to, subject=row.subject, body=row.body, model=row.model,
                status=row.status, created_at=row.created_at,
            )
            for row in self.repository.list_drafts()
        ]

    def priority_inbox(self, limit: int = 20) -> list[PriorityMessage]:
        """Advancement pass: sender-frequency x category-weight x recency scoring."""
        counts = self.repository.sender_counts()
        now = datetime.now(timezone.utc)
        scored: list[PriorityMessage] = []
        for row in self.repository.list_messages(limit=200):
            category = EmailCategory(row.category) if row.category else EmailCategory.PERSONAL
            received = row.received_at
            if received is not None and received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            age_hours = max((now - received).total_seconds() / 3600.0, 0.0) if received else 720.0
            recency = 1.0 / (1.0 + age_hours / 24.0)
            score = (
                CATEGORY_PRIORITY_WEIGHT[category] * 2.0
                + min(counts.get(row.sender, 1), 10) * 0.5
                + recency * 3.0
            )
            reasons = [f"category:{category.value}", f"sender-frequency:{counts.get(row.sender, 1)}"]
            scored.append(PriorityMessage(message=self._message_view(row), score=round(score, 3), reasons=reasons))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    def follow_ups_due(self, within_hours: int = 48) -> list[dict]:
        """Advancement pass: open action items whose deadline is near."""
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=within_hours)
        due: list[dict] = []
        for item in self.list_action_items():
            deadline = item["deadline"]
            if deadline is None:
                continue
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if now <= deadline <= horizon:
                due.append(item)
        return sorted(due, key=lambda item: item["deadline"])

    @staticmethod
    def _message_view(row: EmailMessageRow) -> EmailMessageView:
        return EmailMessageView(
            id=row.id, gmail_id=row.gmail_id, thread_id=row.thread_id, subject=row.subject,
            sender=row.sender, recipients=list(row.recipients or []), snippet=row.snippet,
            received_at=row.received_at, labels=list(row.labels or []),
            category=EmailCategory(row.category) if row.category else None,
            category_confidence=row.category_confidence, unsubscribe_url=row.unsubscribe_url,
        )
