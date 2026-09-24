"""Durable contradiction decision revisions (M09 enhancement).

- ``RevisionStore.append`` writes one revision per transaction and only when its
  ``previous_revision_sha256`` equals the stored head for that claim
  (compare-and-append). A unique (tenant, claim, seq) index turns a concurrent
  append into a conflict instead of a fork.
- The revision's ``actor_id`` must be the authenticated actor. When the actor has
  registered an Ed25519 public key, the revision must carry a signature over its
  revision hash, verified before the row is written. A signature proves key
  possession, not real-world identity.
- Actor key governance (same rules as M10 reviewer keys):
  enrollment by the actor or an ``atlas-admin`` with a proof-of-possession
  signature over the canonical enrollment statement; one active key per actor
  (a second enrollment is refused, rotate instead); rotation needs the new
  key's proof plus an endorsement by the current key, or an admin (recorded as
  ``recovery``); retirement by the actor or an admin, with a reason and an
  ``effective_from`` (default now; earlier when the key may have leaked).
  A retired key never signs a new revision again. When a stored chain is
  re-checked, a revision signed by a retired key counts only if it was stored
  before the key's ``effective_from``; that relies on the server-set
  ``stored_at`` column, not a trusted timestamp. Every enroll / rotate / retire
  / refusal goes to the append-only ``m09_actor_key_events`` log.
- ``verify_sources`` fetches each snapshot's ``source_uri`` (public http(s) only,
  no redirects, size cap) and compares SHA-256 of the bytes to the captured hash.
  Bytes that match are kept, content-addressed and immutable, in
  ``m09_source_blobs``, so later checks still work when the URL is gone or has
  changed: the stored copy is re-hashed on every read. A mismatch means the
  source changed or was captured wrong; it says nothing about which claim is
  true.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import JSON, Boolean, DateTime, Integer, LargeBinary, String, Text, UniqueConstraint, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .contradiction_revisions import DecisionRevision

MAX_SOURCE_BYTES = 20 * 1024 * 1024
ADMIN_ROLE = "atlas-admin"
ENROLL_PURPOSE = "atlas-m09-actor-key-enrollment"
ENDORSE_PURPOSE = "atlas-m09-actor-key-rotation"


class RevisionConflict(ValueError):
    pass


class RevisionRejected(ValueError):
    pass


class KeyGovernanceError(PermissionError):
    pass


class RevisionRow(Base):
    __tablename__ = "m09_contradiction_revisions"
    __table_args__ = (UniqueConstraint("tenant_id", "claim_norm", "seq", name="uq_m09_rev_seq"),
                      UniqueConstraint("tenant_id", "revision_id", name="uq_m09_rev_id"))
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    claim_norm: Mapped[str] = mapped_column(String(500), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    revision_id: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    previous_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    signature_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActorKeyRow(Base):
    __tablename__ = "m09_actor_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "actor_id", "key_id", name="uq_m09_actor_key"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120), index=True)
    key_id: Mapped[str] = mapped_column(String(64))
    public_key_b64: Mapped[str] = mapped_column(Text)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    enrolled_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    retire_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ActorKeyEventRow(Base):
    __tablename__ = "m09_actor_key_events"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(120), index=True)
    key_id: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(60))
    by: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceBlobRow(Base):
    __tablename__ = "m09_source_blobs"
    __table_args__ = (UniqueConstraint("tenant_id", "sha256", name="uq_m09_source_blob"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    byte_count: Mapped[int] = mapped_column(Integer)
    first_uri: Mapped[str] = mapped_column(Text)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def key_id_for(public_key_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(public_key_b64)).hexdigest()[:32]


def enrollment_statement(tenant_id: str, actor_id: str, key_id: str) -> bytes:
    """What a new key signs to prove its holder is enrolling it for this actor."""
    return _canonical({"purpose": ENROLL_PURPOSE, "tenant_id": tenant_id, "actor_id": actor_id, "key_id": key_id})


def rotation_statement(tenant_id: str, actor_id: str, old_key_id: str, new_key_id: str) -> bytes:
    """What the current key signs to endorse its successor."""
    return _canonical({"purpose": ENDORSE_PURPOSE, "tenant_id": tenant_id, "actor_id": actor_id,
                       "old_key_id": old_key_id, "new_key_id": new_key_id})


def _aware(v: datetime | None) -> datetime | None:
    return v if v is None or v.tzinfo else v.replace(tzinfo=timezone.utc)


def revision_sha256(r: DecisionRevision) -> str:
    """Same canonical digest as ``verify_revision_chain``."""
    return hashlib.sha256(json.dumps(r.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(claim: str) -> str:
    return claim.casefold().strip()


def _load_key(b64: str) -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(b64, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad key
        raise RevisionRejected("public key must be base64 of a 32-byte Ed25519 key") from exc


class RevisionStore:
    def __init__(self, tenant_id: str, actor_id: str, session_factory: sessionmaker = SessionLocal,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc), create_schema: bool = True,
                 roles: frozenset[str] = frozenset()):
        self.tenant_id, self.actor_id, self.sessions, self.clock = tenant_id, actor_id, session_factory, clock
        self.roles = frozenset(roles)
        if create_schema and session_factory is SessionLocal:
            Base.metadata.create_all(engine, tables=[RevisionRow.__table__, ActorKeyRow.__table__,
                                                     ActorKeyEventRow.__table__, SourceBlobRow.__table__])

    # -- actor key governance -------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return ADMIN_ROLE in self.roles

    def _event(self, db, actor_id: str, key_id: str, event: str, details: dict) -> None:
        db.add(ActorKeyEventRow(tenant_id=self.tenant_id, actor_id=actor_id, key_id=key_id, event=event,
                                by=self.actor_id, details=details, at=self.clock()))

    def _refuse(self, actor_id: str, key_id: str, event: str, reason: str) -> None:
        with self.sessions.begin() as db:  # own transaction so the refusal is kept
            self._event(db, actor_id, key_id, event, {"reason": reason})

    def _authorize(self, actor_id: str, key_id: str, action: str) -> None:
        if actor_id == self.actor_id or self.is_admin:
            return
        self._refuse(actor_id, key_id, f"{action}_refused", "caller is neither the actor nor an atlas-admin")
        raise KeyGovernanceError(f"only actor {actor_id!r} or an {ADMIN_ROLE} may {action} this key")

    def _check(self, public_key_b64: str, signature_b64: str | None, message: bytes, what: str) -> None:
        if not signature_b64:
            raise KeyGovernanceError(f"{what} signature is required")
        try:
            _load_key(public_key_b64).verify(base64.b64decode(signature_b64, validate=True), message)
        except (InvalidSignature, ValueError) as exc:
            raise KeyGovernanceError(f"{what} signature does not verify") from exc

    def _key(self, db, actor_id: str, key_id: str) -> ActorKeyRow | None:
        return db.scalar(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id,
                                                   ActorKeyRow.actor_id == actor_id, ActorKeyRow.key_id == key_id))

    def _active_keys(self, db, actor_id: str) -> list[ActorKeyRow]:
        return list(db.scalars(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id, ActorKeyRow.actor_id == actor_id,
                                                         ActorKeyRow.active.is_not(False))))

    def register_key(self, public_key_b64: str, proof_signature_b64: str | None = None, actor_id: str | None = None) -> dict:
        actor = actor_id or self.actor_id
        _load_key(public_key_b64)
        key_id = key_id_for(public_key_b64)
        self._authorize(actor, key_id, "enroll")
        try:
            self._check(public_key_b64, proof_signature_b64, enrollment_statement(self.tenant_id, actor, key_id), "proof-of-possession")
        except KeyGovernanceError as exc:
            self._refuse(actor, key_id, "enroll_refused", str(exc))
            raise
        with self.sessions.begin() as db:
            existing = self._key(db, actor, key_id)
            if existing is not None:
                if existing.active is False:
                    raise RevisionConflict("this key was retired and can never be enrolled again; generate a new key")
                return {"actor_id": actor, "key_id": key_id, "active": True, "already_enrolled": True}
            active = self._active_keys(db, actor)
            if active:
                raise RevisionConflict(f"actor already has active key {active[0].key_id}; rotate instead")
            db.add(ActorKeyRow(tenant_id=self.tenant_id, actor_id=actor, key_id=key_id, public_key_b64=public_key_b64,
                               registered_at=self.clock(), active=True, enrolled_by=self.actor_id))
            self._event(db, actor, key_id, "enrolled", {"admin": actor != self.actor_id})
        return {"actor_id": actor, "key_id": key_id, "active": True, "already_enrolled": False}

    def rotate_key(self, new_public_key_b64: str, proof_signature_b64: str | None, endorsement_signature_b64: str | None = None,
                   actor_id: str | None = None, reason: str = "rotated") -> dict:
        actor = actor_id or self.actor_id
        _load_key(new_public_key_b64)
        new_id = key_id_for(new_public_key_b64)
        self._authorize(actor, new_id, "rotate")
        with self.sessions() as db:
            active = self._active_keys(db, actor)
            if len(active) != 1:
                raise RevisionConflict("actor has no active key; enroll instead" if not active else
                                       "actor has several legacy active keys; retire all but one first")
            old_id, old_pub = active[0].key_id, active[0].public_key_b64
            if self._key(db, actor, new_id) is not None:
                raise RevisionConflict("new key is already registered for this actor")
        try:
            self._check(new_public_key_b64, proof_signature_b64, enrollment_statement(self.tenant_id, actor, new_id), "proof-of-possession")
            if endorsement_signature_b64:
                self._check(old_pub, endorsement_signature_b64, rotation_statement(self.tenant_id, actor, old_id, new_id), "old-key endorsement")
                mode = "continuity"
            elif self.is_admin:
                mode = "recovery"
            else:
                raise KeyGovernanceError("rotation needs an endorsement from the current key (admins may recover without it)")
        except KeyGovernanceError as exc:
            self._refuse(actor, new_id, "rotate_refused", str(exc))
            raise
        now = self.clock()
        with self.sessions.begin() as db:
            old = self._key(db, actor, old_id)
            if old is None or old.active is False:
                raise RevisionConflict("active key changed during rotation; retry")
            old.active, old.retired_at, old.retired_by, old.effective_from = False, now, self.actor_id, now
            old.retire_reason, old.replaced_by_key_id = f"{reason} ({mode})"[:300], new_id
            db.add(ActorKeyRow(tenant_id=self.tenant_id, actor_id=actor, key_id=new_id, public_key_b64=new_public_key_b64,
                               registered_at=now, active=True, enrolled_by=self.actor_id))
            self._event(db, actor, old_id, "retired", {"reason": old.retire_reason, "replaced_by": new_id, "effective_from": now.isoformat()})
            self._event(db, actor, new_id, "enrolled", {"rotation": mode, "replaces": old_id})
        return {"actor_id": actor, "retired_key_id": old_id, "active_key_id": new_id, "mode": mode}

    def retire_key(self, key_id: str, reason: str, actor_id: str | None = None, effective_from: datetime | None = None) -> dict:
        actor = actor_id or self.actor_id
        if not reason or len(reason.strip()) < 3:
            raise RevisionRejected("a retirement reason (3+ characters) is required")
        self._authorize(actor, key_id, "retire")
        now = self.clock()
        with self.sessions.begin() as db:
            row = self._key(db, actor, key_id)
            if row is None:
                raise LookupError("no such key for this actor")
            eff = _aware(effective_from) or now
            eff = min(max(eff, _aware(row.registered_at)), now)
            if row.active is not False:
                row.active, row.retired_at, row.retired_by, row.retire_reason, row.effective_from = False, now, self.actor_id, reason[:300], eff
                self._event(db, actor, key_id, "retired", {"reason": reason[:300], "effective_from": eff.isoformat()})
            elif eff < _aware(row.effective_from or row.retired_at or now):
                row.effective_from = eff  # a later report can only move the cutoff earlier
                self._event(db, actor, key_id, "effective_from_moved_earlier", {"reason": reason[:300], "effective_from": eff.isoformat()})
            out = {"actor_id": actor, "key_id": key_id, "active": False, "retired_at": _aware(row.retired_at).isoformat(),
                   "effective_from": _aware(row.effective_from).isoformat(), "retire_reason": row.retire_reason}
        return out

    def list_keys(self, actor_id: str | None = None) -> list[dict]:
        with self.sessions() as db:
            q = select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id)
            if actor_id:
                q = q.where(ActorKeyRow.actor_id == actor_id)
            return [{"actor_id": k.actor_id, "key_id": k.key_id, "active": k.active is not False, "enrolled_by": k.enrolled_by,
                     "registered_at": _aware(k.registered_at), "retired_at": _aware(k.retired_at), "retired_by": k.retired_by,
                     "retire_reason": k.retire_reason, "effective_from": _aware(k.effective_from),
                     "replaced_by_key_id": k.replaced_by_key_id} for k in db.scalars(q.order_by(ActorKeyRow.pk))]

    def key_events(self, actor_id: str) -> list[dict]:
        with self.sessions() as db:
            return [{"key_id": e.key_id, "event": e.event, "by": e.by, "details": e.details, "at": _aware(e.at)}
                    for e in db.scalars(select(ActorKeyEventRow).where(ActorKeyEventRow.tenant_id == self.tenant_id,
                                        ActorKeyEventRow.actor_id == actor_id).order_by(ActorKeyEventRow.pk))]

    def _keys(self, db, actor_id: str) -> list[ActorKeyRow]:
        return list(db.scalars(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id, ActorKeyRow.actor_id == actor_id)))

    # -- revisions ------------------------------------------------------------
    def append(self, revision: DecisionRevision, signature_b64: str | None = None) -> dict:
        if revision.actor_id != self.actor_id:
            raise RevisionRejected("revision actor_id must be the authenticated actor")
        digest, claim = revision_sha256(revision), _norm(revision.claim_key)
        try:
            with self.sessions.begin() as db:
                head = db.scalar(select(RevisionRow).where(RevisionRow.tenant_id == self.tenant_id, RevisionRow.claim_norm == claim)
                                 .order_by(RevisionRow.seq.desc()).limit(1))
                expected = head.sha256 if head else None
                if revision.previous_revision_sha256 != expected:
                    raise RevisionConflict(f"stale head: expected previous_revision_sha256={expected}")
                key_id = None
                all_keys = self._keys(db, self.actor_id)
                keys = [k for k in all_keys if k.active is not False]  # retired keys never sign again
                if all_keys:
                    if not signature_b64:
                        raise RevisionRejected("actor has a registered key; revision must be signed")
                    if not keys:
                        raise RevisionRejected("actor's keys are all retired; enroll a new key before signing")
                    try:
                        sig = base64.b64decode(signature_b64, validate=True)
                    except Exception as exc:  # noqa: BLE001
                        raise RevisionRejected("signature is not base64") from exc
                    for k in keys:
                        try:
                            _load_key(k.public_key_b64).verify(sig, digest.encode())
                            key_id = k.key_id
                            break
                        except InvalidSignature:
                            continue
                    if key_id is None:
                        retired = [k for k in all_keys if k.active is False]
                        for k in retired:
                            try:
                                _load_key(k.public_key_b64).verify(sig, digest.encode())
                                raise RevisionRejected(f"signed with retired key {k.key_id}; retired keys never verify new revisions")
                            except InvalidSignature:
                                continue
                        raise RevisionRejected("signature does not verify against the actor's active key")
                elif signature_b64:
                    raise RevisionRejected("signature supplied but the actor has no registered key")
                row = RevisionRow(tenant_id=self.tenant_id, claim_norm=claim, seq=(head.seq + 1) if head else 1,
                                  revision_id=revision.revision_id, sha256=digest, previous_sha256=expected,
                                  payload=revision.model_dump(mode="json"), signature_b64=signature_b64, key_id=key_id,
                                  stored_at=self.clock())
                db.add(row)
                db.flush()
                seq = row.seq
        except IntegrityError as exc:
            raise RevisionConflict("concurrent append or duplicate revision_id; re-read the head and retry") from exc
        return {"claim_key": revision.claim_key, "seq": seq, "sha256": digest, "signed_key_id": key_id}

    def chain(self, claim_key: str) -> dict:
        with self.sessions() as db:
            rows = list(db.scalars(select(RevisionRow).where(RevisionRow.tenant_id == self.tenant_id,
                                                             RevisionRow.claim_norm == _norm(claim_key)).order_by(RevisionRow.seq)))
            keys = {(k.actor_id, k.key_id): k for k in db.scalars(select(ActorKeyRow).where(ActorKeyRow.tenant_id == self.tenant_id))}
        if not rows:
            raise LookupError("no revisions for this claim")
        problems, prev, status = [], None, {}
        for r in rows:
            rev = DecisionRevision.model_validate(r.payload)
            if revision_sha256(rev) != r.sha256:
                problems.append(f"seq {r.seq}: stored payload no longer matches its hash")
            if r.previous_sha256 != prev or rev.previous_revision_sha256 != prev:
                problems.append(f"seq {r.seq}: chain break")
            if r.key_id:
                k = keys.get((rev.actor_id, r.key_id))
                try:
                    if k is None:
                        raise KeyError(r.key_id)
                    _load_key(k.public_key_b64).verify(base64.b64decode(r.signature_b64), r.sha256.encode())
                except (KeyError, InvalidSignature):
                    problems.append(f"seq {r.seq}: signature no longer verifies against the actor's registered key")
                    status[r.seq] = "invalid"
                else:
                    if k.active is not False:
                        status[r.seq] = "active_key"
                    else:
                        cutoff = _aware(k.effective_from or k.retired_at)
                        if _aware(r.stored_at) < cutoff:
                            status[r.seq] = "retired_key_stored_before_cutoff"
                        else:
                            status[r.seq] = "retired_key_after_cutoff"
                            problems.append(f"seq {r.seq}: signed by key {r.key_id} but stored after its retirement took effect ({cutoff.isoformat()})")
            prev = r.sha256
        return {"claim_key": rows[-1].payload["claim_key"], "revision_count": len(rows), "head_sha256": prev,
                "valid": not problems, "problems": problems,
                "revisions": [{"seq": r.seq, "revision_id": r.revision_id, "sha256": r.sha256, "actor_id": r.payload["actor_id"],
                               "signed_key_id": r.key_id, "signature_status": status.get(r.seq, "unsigned"),
                               "stored_at": _aware(r.stored_at), "action": r.payload["action"]} for r in rows],
                "latest_decision": rows[-1].payload}


# -- source bytes -----------------------------------------------------------------
def _http_fetch(url: str) -> bytes:
    import httpx
    from app.modules.m13_browser_agent.security import validate_public_url
    validate_public_url(url)
    with httpx.Client(follow_redirects=False, timeout=20) as client, client.stream("GET", url) as resp:
        if resp.status_code != 200:
            raise RevisionRejected(f"HTTP {resp.status_code}")
        out = bytearray()
        for chunk in resp.iter_bytes():
            out += chunk
            if len(out) > MAX_SOURCE_BYTES:
                raise RevisionRejected("source larger than 20 MB")
        return bytes(out)


class SourceBlobStore:
    """Tenant-scoped, content-addressed, write-once store for verified source bytes."""

    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.tenant_id, self.sessions, self.clock = tenant_id, session_factory, clock
        if session_factory is SessionLocal:
            Base.metadata.create_all(engine, tables=[SourceBlobRow.__table__])

    def put(self, content: bytes, uri: str) -> dict:
        digest = hashlib.sha256(content).hexdigest()
        if len(content) > MAX_SOURCE_BYTES:
            raise RevisionRejected("source larger than 20 MB")
        try:
            with self.sessions.begin() as db:
                existing = db.scalar(select(SourceBlobRow).where(SourceBlobRow.tenant_id == self.tenant_id, SourceBlobRow.sha256 == digest))
                if existing is not None:  # immutable: never overwritten
                    return {"sha256": digest, "byte_count": existing.byte_count, "stored": False, "already_stored": True}
                db.add(SourceBlobRow(tenant_id=self.tenant_id, sha256=digest, content=content, byte_count=len(content),
                                     first_uri=uri[:2000], stored_at=self.clock()))
        except IntegrityError:
            return {"sha256": digest, "byte_count": len(content), "stored": False, "already_stored": True}
        return {"sha256": digest, "byte_count": len(content), "stored": True, "already_stored": False}

    def get(self, sha256: str) -> tuple[bytes, dict] | None:
        """Stored bytes, re-hashed on read; raises if the stored copy was altered."""
        with self.sessions() as db:
            row = db.scalar(select(SourceBlobRow).where(SourceBlobRow.tenant_id == self.tenant_id, SourceBlobRow.sha256 == sha256))
            if row is None:
                return None
            content, meta = bytes(row.content), {"first_uri": row.first_uri, "stored_at": _aware(row.stored_at).isoformat(),
                                                   "byte_count": row.byte_count}
        if hashlib.sha256(content).hexdigest() != sha256:
            raise RevisionRejected(f"stored copy of {sha256} no longer matches its hash")
        return content, meta


def verify_sources(revision: DecisionRevision, source_uris: dict[str, str],
                   fetch: Callable[[str], bytes] = _http_fetch, blobs: SourceBlobStore | None = None) -> dict:
    results = []
    for snap in revision.source_snapshots:
        uri = source_uris.get(snap.evidence_id)
        entry: dict = {"evidence_id": snap.evidence_id, "captured_sha256": snap.content_sha256}
        if uri:
            entry["uri"] = uri
            try:
                content = fetch(uri)
            except Exception as exc:  # noqa: BLE001 - report per source, keep going
                entry.update(status="unreachable", error=str(exc)[:300])
            else:
                actual = hashlib.sha256(content).hexdigest()
                entry.update(fetched_sha256=actual, status="match" if actual == snap.content_sha256 else "mismatch")
                if entry["status"] == "match" and blobs is not None:
                    entry["stored_copy"] = blobs.put(content, uri)
        else:
            entry["status"] = "no_uri"
        if entry["status"] != "match" and blobs is not None:
            # Fall back to (or, on mismatch, also report) the stored verified copy.
            try:
                got = blobs.get(snap.content_sha256)
            except RevisionRejected as exc:
                entry["stored_copy"] = {"status": "corrupt", "error": str(exc)}
            else:
                if got is None:
                    entry["stored_copy"] = {"status": "none"}
                else:
                    entry["stored_copy"] = {"status": "match", **got[1]}
                    if entry["status"] in {"unreachable", "no_uri"}:
                        entry["live_status"], entry["status"] = entry["status"], "stored_match"
        results.append(entry)
    return {"revision_id": revision.revision_id, "all_match": all(r["status"] == "match" for r in results),
            "all_verified": all(r["status"] in {"match", "stored_match"} for r in results), "sources": results,
            "boundary": "match: the bytes at that URL now equal the captured snapshot. stored_match: the URL was not checked or not reachable, "
                        "but Atlas holds bytes it fetched earlier that still hash to the captured value. Neither shows the source is authentic "
                        "or that its claim is true."}
