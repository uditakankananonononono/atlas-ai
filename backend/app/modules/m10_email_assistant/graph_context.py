"""Module 9 knowledge-graph integration for module 10: account-scoped writer and reader.

Keys (m09 unique on tenant + source_module + external_id), account ids are uuid4 strings
created by Service._store_tokens and never contain ':':
  CONTACT  contact:<account_id>:<lowercased address>
  EMAIL    email:<account_id>:<gmail_id>
Every node written here carries metadata.account_id. The reader returns only nodes whose
metadata.account_id equals the drafting account. Nodes with no or a different account tag
are excluded: M09 has no audience/visibility contract, so there is no grounded policy that
makes untagged knowledge shareable across mailboxes. Unknown scope returns no facts.
Operational errors propagate to Service, which reports them separately from "no facts".
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parseaddr
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.modules.m09_knowledge_workspace.repository import DuplicateEdgeError
from app.modules.m09_knowledge_workspace.schemas import Edge, Node, NodeType, Relationship

SOURCE_MODULE = "m10-email-assistant"
ACTOR_ID = "m10-email-assistant"
MAX_FACTS = 10
MAX_FACT_CHARS = 300
_ADDR = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def normalise_address(sender: str) -> str | None:
    addr = parseaddr(sender or "")[1].strip().lower()
    return addr if _ADDR.match(addr) and len(addr) <= 254 else None


def _valid_part(value: str | None) -> bool:
    return bool(value) and ":" not in value and len(value) <= 100


def contact_external_id(account_id: str, address: str) -> str:
    if not _valid_part(account_id):
        raise ValueError("invalid account id")
    return f"contact:{account_id}:{address.strip().lower()}"


def email_external_id(account_id: str, gmail_id: str) -> str:
    if not _valid_part(account_id) or not _valid_part(gmail_id):
        raise ValueError("invalid account or gmail id")
    return f"email:{account_id}:{gmail_id}"


def _line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:MAX_FACT_CHARS]


def _mine(node, account_id: str, kind: str) -> bool:
    return (node is not None and node.source_module == SOURCE_MODULE
            and node.metadata.get("account_id") == account_id
            and node.metadata.get("kind") == kind)


class KnowledgeGraphReplyContext:
    """Reader; callable matching service.GraphContextFn."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def __call__(self, sender: str, account_id: str | None) -> list[str]:
        address = normalise_address(sender)
        if not _valid_part(account_id) or not address:
            return []  # unknown scope: fail closed
        contact = self.repository.get_by_source(
            SOURCE_MODULE, contact_external_id(account_id, address))
        if not _mine(contact, account_id, "contact") or contact.node_type != NodeType.CONTACT:
            return []
        facts = [_line(f"CONTACT {contact.title} <{address}>: {contact.body or ''}")]
        neighbours = []
        for edge in self.repository.edges_for({contact.id}):
            other_id = edge.target_id if edge.source_id == contact.id else edge.source_id
            other = self.repository.get_node(other_id)
            if _mine(other, account_id, "email"):
                neighbours.append(other)
        neighbours.sort(key=lambda n: n.updated_at, reverse=True)
        for other in neighbours[: MAX_FACTS - 1]:
            facts.append(_line(f"EMAIL from {contact.title} ({other.metadata.get('received_at') or 'undated'}) "
                               f"{other.title}: {other.body or ''}"))
        return facts


class KnowledgeGraphIngestor:
    """Writer; callable matching service.GraphIngestFn. Idempotent upserts."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def __call__(self, account_id: str, raw) -> None:
        address = normalise_address(raw.sender)
        if not address:
            return  # no usable sender: nothing to bind
        now = datetime.now(timezone.utc)
        received = (datetime.fromtimestamp(raw.received_at, tz=timezone.utc).isoformat()
                    if raw.received_at else None)
        subject = (raw.subject or "(no subject)").strip() or "(no subject)"
        name = parseaddr(raw.sender)[0].strip() or address
        email_ext = email_external_id(account_id, raw.gmail_id)
        email_node, _ = self._upsert(
            NodeType.EMAIL, subject[:500], (raw.snippet or "")[:500], email_ext,
            {"kind": "email", "account_id": account_id, "gmail_id": raw.gmail_id,
             "thread_id": raw.thread_id, "received_at": received}, now)
        contact_node, _ = self._upsert(
            NodeType.CONTACT, name[:500], f"Last email ({received or 'undated'}): {subject}"[:1000],
            contact_external_id(account_id, address),
            {"kind": "contact", "account_id": account_id, "address": address}, now)
        try:
            self.repository.save_edge(Edge(
                id=str(uuid4()), source_id=email_node.id, target_id=contact_node.id,
                relationship=Relationship.REFERENCES, rationale="sender of this email",
                evidence={"account_id": account_id, "gmail_id": raw.gmail_id}, created_at=now))
        except DuplicateEdgeError:
            pass

    def _upsert(self, kind, title, body, ext, metadata, now):
        existing = self.repository.get_by_source(SOURCE_MODULE, ext)
        if existing is None:
            node = Node(id=str(uuid4()), node_type=kind, title=title, body=body, metadata=metadata,
                        source_module=SOURCE_MODULE, external_id=ext, created_at=now, updated_at=now)
            try:
                self.repository.save_node(node)
                return node, True
            except IntegrityError:  # concurrent first write of the same key
                existing = self.repository.get_by_source(SOURCE_MODULE, ext)
                if existing is None:
                    raise
        if existing.metadata.get("account_id") != metadata["account_id"] or existing.node_type != kind:
            raise ValueError("graph node key collision across scope")
        updated = existing.model_copy(update={
            "title": title, "body": body, "metadata": metadata,
            "version": existing.version + 1, "updated_at": now})
        saved = self.repository.save_node(updated, "node.updated", expected_version=existing.version)
        return (saved or existing), False
