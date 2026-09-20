from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .lane_models import MailboxRef, ProviderMessage, SendResult


@dataclass(frozen=True)
class ProviderPage:
    messages: tuple[ProviderMessage, ...]
    next_cursor: str | None


class MailProvider(Protocol):
    def sync(self, mailbox: MailboxRef, cursor: str | None, limit: int) -> ProviderPage: ...

    def send(
        self,
        mailbox: MailboxRef,
        *,
        to: Sequence[str],
        cc: Sequence[str],
        subject: str,
        body_text: str,
        thread_id: str,
        idempotency_key: str,
        headers: Mapping[str, str],
    ) -> SendResult: ...
