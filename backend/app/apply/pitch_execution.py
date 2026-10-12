"""Pitch drafts -> exact Module-0 outreach descriptor -> durable send.

No bool/dict 'owner approval' is accepted here. The approval must be a real
Module-0 record with an unchanged reviewed state and consumed exact payload.
Ambiguous provider outcomes remain started or dispatching and cannot be silently retried.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from email.message import EmailMessage
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

from app.modules.c30 import policy
from .pitch_drafts import _check_draft


def descriptor(draft: dict, *, tenant_id: str, sender: str, send_at: str) -> dict:
    _check_draft(draft, ('DRAFT', 'QUEUED'))
    if send_at != 'immediate':
        raise ValueError('only immediate delivery supported; future sends need a scheduler')
    return policy.bind_outreach(tenant_id=tenant_id, module_id=10, sender=sender,
                               channel='gmail', send_at=send_at, to=[draft['recipient']],
                               cc=[], bcc=[], subject=draft['subject'], body=draft['body'])


class GmailPitchSender:
    """Actual Gmail API transport. token_provider is trusted host config.

    The host must have a sender-account-bound token with Gmail send scope.
    No scopes are widened, OAuth flow run or secrets persisted by this class.
    """
    def __init__(self, account_email: str, token_provider, *, approval_store=None):
        policy.clean_text(account_email, 'PITCH', 'sender', 320)
        if not callable(token_provider):
            raise ValueError('trusted token provider required')
        if type(approval_store) is not PitchExecution:
            raise PermissionError('trusted PitchExecution approval store required')
        self._approval_store = approval_store
        self.account = account_email
        self.token_provider = token_provider

    def send(self, effect: dict, approval_id: str) -> dict:
        effect = deepcopy(effect)
        policy.validate_descriptor(effect)
        payload = effect['payload']
        if payload['sender'] != self.account or payload['channel'] != 'gmail' or payload['attachment_hashes']:
            raise ValueError('sender/channel mismatch or unsupported attachments')
        # Verify actual durable M00 consumption and atomically claim transport.
        # Caller flags, fabricated receipt objects and arbitrary payloads are not permits.
        self._approval_store._claim_transport(effect, approval_id)
        message = EmailMessage()
        message['From'] = payload['sender']
        message['To'] = ', '.join(payload['to'])
        if payload['cc']:
            message['Cc'] = ', '.join(payload['cc'])
        if payload['bcc']:
            message['Bcc'] = ', '.join(payload['bcc'])
        message['Subject'] = payload['subject']
        message.set_content(payload['body'])
        token = self.token_provider()
        profile_request = Request('https://gmail.googleapis.com/gmail/v1/users/me/profile',
                                  headers={'Authorization': 'Bearer ' + token})
        with urlopen(profile_request, timeout=30) as response:
            profile = json.load(response)
        if profile.get('emailAddress', '').lower() != self.account.lower():
            raise ValueError('OAuth token belongs to a different sending account')
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        request = Request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                          data=json.dumps({'raw': raw}).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + token,
                                   'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
        if type(data) is not dict or type(data.get('id')) is not str or not data['id']:
            raise RuntimeError('provider returned no message id; outcome unknown')
        return {'message_id': data['id'], 'thread_id': data.get('threadId'),
                'status': 'provider_accepted', 'delivered': 'unverified'}


class PitchExecution:
    def __init__(self, database: Path, *, service, registry, sender):
        if not isinstance(database, Path) or not database.is_absolute():
            raise ValueError('absolute durable database path required')
        self.database, self.service, self.registry, self.sender = database, service, registry, sender
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pitch_sends ('
                       'effect_id TEXT PRIMARY KEY, approval_id TEXT UNIQUE NOT NULL, '
                       'payload_sha256 TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT)')

    def _db(self):
        return sqlite3.connect(self.database, timeout=30)

    def execute(self, effect: dict, approval_id: str, *, actor: str) -> dict:
        from app.modules.m00_approval_center import impact
        effect = deepcopy(effect)
        policy.validate_descriptor(effect)
        if effect['class'] != 'outreach' or effect['module_id'] != 10 or effect['payload']['channel'] != 'gmail':
            raise ValueError('pitch outreach descriptor required')
        if effect['payload']['send_at'] != 'immediate':
            raise ValueError('only immediate delivery supported')
        approval_id = policy.clean_text(approval_id, 'PITCH', 'approval_id', 200)
        payload_hash = hashlib.sha256(json.dumps(effect, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        effect_id = 'pitch-' + payload_hash
        # Durable claim serializes concurrent dispatchers before any side effect.
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT status,receipt FROM pitch_sends WHERE effect_id=? OR approval_id=?',
                               (effect_id, approval_id)).fetchone()
            if prior:
                raise RuntimeError('pitch already claimed; reconcile its receipt before retry')
            preview = impact.impact_preview(self.service, approval_id, registry=self.registry)
            if preview['verdict'] != 'unchanged' or not preview['safe_to_consume']:
                raise PermissionError('unchanged owner-reviewed approval required')
            permit = policy.execute(effect, approval_id, actor=actor, effect_id=effect_id,
                                    service=self.service, registry=self.registry)
            if permit.get('allowed') is not True or permit.get('state_verdict') != 'unchanged':
                raise PermissionError('exact outreach approval not consumed')
            db.execute('INSERT INTO pitch_sends VALUES (?,?,?,?,?)',
                       (effect_id, approval_id, payload_hash, 'started', None))
        # Exceptions deliberately retain started. A timeout may mean it was sent.
        receipt = self.sender.send(deepcopy(effect), approval_id)
        if type(receipt) is not dict or type(receipt.get('message_id')) is not str or not receipt['message_id']:
            raise RuntimeError('provider receipt missing; outcome unknown')
        with self._db() as db:
            db.execute('UPDATE pitch_sends SET status=?,receipt=? WHERE effect_id=?',
                       ('provider_accepted', json.dumps(receipt), effect_id))
        return {'effect_id': effect_id, 'approval_id': approval_id, **receipt}

    def _claim_transport(self, effect: dict, approval_id: str) -> None:
        from sqlalchemy import select
        from app.modules.m00_approval_center import impact
        from app.modules.m00_approval_center.service import ApprovalEffectRow, _request_hash, _aware
        policy.validate_descriptor(effect)
        if effect['class'] != 'outreach' or effect['module_id'] != 10 or effect['action_type'] != 'outreach':
            raise PermissionError('pitch outreach effect required')
        if effect['payload']['send_at'] != 'immediate':
            raise PermissionError('immediate reviewed delivery required')
        payload_hash = hashlib.sha256(json.dumps(effect, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        effect_id = 'pitch-' + payload_hash
        # The sender independently verifies the actual approval/consumption table.
        # It cannot authorize transport from a caller-supplied permit object.
        with self.service._sessions() as session:
            consumed = session.scalar(select(ApprovalEffectRow).where(
                ApprovalEffectRow.approval_id == approval_id))
            digest = _request_hash(module_id=10, action_type='outreach', payload=effect['payload'],
                                   user_id=effect['tenant_id'])
            if consumed is None or consumed.effect_id != effect_id or consumed.request_hash != digest:
                raise PermissionError('durable exact M00 consumption required')
        view = self.service.get(approval_id)
        if view.get('expires_at') is not None and _aware(view['expires_at']) <= self.service._clock():
            raise PermissionError('approval expired before transport')
        preview = impact.impact_preview(self.service, approval_id, registry=self.registry)
        if preview['verdict'] != 'unchanged' or not preview['safe_to_consume']:
            raise PermissionError('unchanged reviewed state required at transport')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload_sha256,status FROM pitch_sends '
                             'WHERE effect_id=? AND approval_id=?', (effect_id, approval_id)).fetchone()
            if row != (payload_hash, 'started'):
                raise PermissionError('durable unused execution claim required')
            changed = db.execute('UPDATE pitch_sends SET status=? WHERE effect_id=? AND status=?',
                                 ('dispatching', effect_id, 'started'))
            if changed.rowcount != 1:
                raise PermissionError('transport already claimed')

    def receipts(self) -> list:
        with self._db() as db:
            rows = db.execute('SELECT effect_id,approval_id,status,receipt FROM pitch_sends ORDER BY rowid').fetchall()
        return [{'effect_id': e, 'approval_id': a, 'status': s,
                 'receipt': json.loads(r) if r else None} for e, a, s, r in rows]
