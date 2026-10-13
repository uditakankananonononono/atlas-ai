"""Fresh provider-identity checks for explicitly routed GitHub/Google GETs.

Not a global HTTP interceptor. Owner subjects and authority are supplied by a
trusted authenticated control plane; a successful provider probe alone never
establishes ownership or permits disclosure. Secrets stay only in call memory.
SQLite serializes binding changes and dispatch, including across processes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROVIDERS = {
    'github': ('https://api.github.com', 'https://api.github.com/user'),
    'google': ('https://www.googleapis.com', 'https://openidconnect.googleapis.com/v1/userinfo'),
}


class AccountRefusal(RuntimeError):
    """Sanitized failure, never includes token or provider response body."""


def _text(value, name, limit=256):
    if (type(value) is not str or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('invalid ' + name)
    return value


def binding_digest(tenant, service, subject):
    return hashlib.sha256(json.dumps({'tenant': tenant, 'service': service,
                                     'subject': subject}, sort_keys=True).encode()).hexdigest()


class OwnerAccountRuntime:
    """Use a private persistent DB and trusted, non-user-replaceable callbacks.

    authority(ref, digest) rechecks owner binding permission on enrollment and
    every GET. read_authority(tenant, service, subject, url) independently checks
    disclosure/read scope. Both require the literal True, not truthy objects.
    credential(tenant, service) retrieves the access token once per dispatch.
    get() holds a SQLite write lock for the entire probe and operation request.
    Lock contention waits up to 15 seconds, then raises AccountRefusal.
    Optional transport is for offline tests only, never a live-acceptance claim.
    """
    def __init__(self, database, *, authority, read_authority, credential, transport=None):
        if not all(callable(x) for x in (authority, read_authority, credential)):
            raise ValueError('trusted callbacks required')
        self.database = str(Path(database))
        self.authority, self.read_authority = authority, read_authority
        self.credential, self.transport = credential, transport
        with self._transaction() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS owner_bindings_g139 (
                tenant TEXT NOT NULL, service TEXT NOT NULL, subject TEXT NOT NULL,
                authority_ref TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(tenant,service));
                CREATE TABLE IF NOT EXISTS owner_dispatch_g139 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL,
                service TEXT NOT NULL, subject TEXT, path TEXT NOT NULL,
                outcome TEXT NOT NULL, at TEXT NOT NULL);''')

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except sqlite3.OperationalError:
            db.rollback()
            raise AccountRefusal('owner-account storage unavailable or locked') from None
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def bind(self, tenant, service, subject, authority_ref):
        _text(tenant, 'tenant'); self._provider(service); _text(subject, 'subject')
        _text(authority_ref, 'authority_ref')
        with self._transaction() as db:
            if self.authority(authority_ref, binding_digest(tenant, service, subject)) is not True:
                raise AccountRefusal('owner authority rejected')
            existing = db.execute('SELECT subject,revoked FROM owner_bindings_g139 WHERE tenant=? AND service=?',
                                  (tenant, service)).fetchone()
            if existing and not existing['revoked']:
                raise AccountRefusal('revoke existing binding before replacement')
            db.execute('INSERT INTO owner_bindings_g139 VALUES(?,?,?,?,0) ON CONFLICT(tenant,service) '
                       'DO UPDATE SET subject=excluded.subject,authority_ref=excluded.authority_ref,revoked=0',
                       (tenant, service, subject, authority_ref))

    def revoke(self, tenant, service):
        # Administrative control-plane method, never expose to an unauthenticated route.
        _text(tenant, 'tenant'); self._provider(service)
        with self._transaction() as db:
            db.execute('UPDATE owner_bindings_g139 SET revoked=1 WHERE tenant=? AND service=?', (tenant, service))

    def receipts(self, tenant):
        _text(tenant, 'tenant')
        with self._transaction() as db:
            return [dict(r) for r in db.execute('SELECT * FROM owner_dispatch_g139 WHERE tenant=? ORDER BY id', (tenant,))]

    @staticmethod
    def _provider(service):
        if type(service) is not str or service not in PROVIDERS:
            raise ValueError('unsupported provider')
        return PROVIDERS[service]

    @staticmethod
    def _subject(service, response):
        obj = response.json()
        if type(obj) is not dict:
            raise AccountRefusal('malformed provider identity')
        if service == 'github':
            if type(obj.get('id')) is not int or obj['id'] <= 0 or obj.get('type') != 'User':
                raise AccountRefusal('not a GitHub user identity')
            return str(obj['id'])
        sub = obj.get('sub')
        if type(sub) is not str or not sub or len(sub) > 255 or not sub.isascii() or not sub.isprintable():
            raise AccountRefusal('malformed Google subject')
        return sub

    @staticmethod
    def _fetch(client, url, headers, limit):
        with client.stream('GET', url, headers=headers) as response:
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise AccountRefusal('provider response too large')
                chunks.append(chunk)
            # Returned request metadata does not retain the bearer credential.
            return httpx.Response(response.status_code, headers=response.headers,
                                  content=b''.join(chunks), request=httpx.Request('GET', url))

    def get(self, tenant, service, path):
        """Authenticated GET with fresh identity probe and exact-resource authority.

        No redirects, query strings, retry, proxy env, arbitrary hosts, or writes.
        GETs can still disclose private data. read_authority must approve that
        scope. Provider subject, not email/login/display name, binds identity.
        A receipt of DISPATCHED describes HTTP execution, not semantic success.
        """
        _text(tenant, 'tenant'); base, identity_url = self._provider(service)
        _text(path, 'path', 2048)
        if not re.fullmatch(r'/[A-Za-z0-9_./@~!$&()*+,;=:-]*', path) or path.startswith('//') or any(c in path for c in ('?', '#', '\\', '%')) or '..' in path.split('/'):
            raise ValueError('invalid resource path')
        url = base + path
        with self._transaction() as db:
            row = db.execute('SELECT * FROM owner_bindings_g139 WHERE tenant=? AND service=?', (tenant, service)).fetchone()
            outcome, subject, response = 'REFUSED', None, None
            try:
                if row is None or row['revoked']:
                    raise AccountRefusal('missing or revoked owner binding')
                subject = row['subject']
                if self.authority(row['authority_ref'], binding_digest(tenant, service, subject)) is not True:
                    raise AccountRefusal('owner authority rejected')
                if self.read_authority(tenant, service, subject, url) is not True:
                    raise AccountRefusal('read scope rejected')
                token = self.credential(tenant, service)
                _text(token, 'credential', 8192)
                headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
                if service == 'github': headers['X-GitHub-Api-Version'] = '2022-11-28'
                with httpx.Client(timeout=10, follow_redirects=False, trust_env=False,
                                  transport=self.transport) as client:
                    identity = self._fetch(client, identity_url, headers, 65536)
                    if identity.status_code != 200:
                        raise AccountRefusal('provider identity unavailable')
                    if self._subject(service, identity) != subject:
                        raise AccountRefusal('provider account drift')
                    # The same in-memory credential is used for probe and operation.
                    # Binding changes are serialized until this request finishes.
                    if self.authority(row['authority_ref'], binding_digest(tenant, service, subject)) is not True:
                        raise AccountRefusal('owner authority changed during probe')
                    if self.read_authority(tenant, service, subject, url) is not True:
                        raise AccountRefusal('read scope changed during probe')
                    outcome = 'AMBIGUOUS'
                    response = self._fetch(client, url, headers, 10485760)
                    outcome = 'DISPATCHED'
            except Exception:
                response = None
            db.execute('INSERT INTO owner_dispatch_g139(tenant,service,subject,path,outcome,at) VALUES(?,?,?,?,?,?)',
                       (tenant, service, subject, path, outcome, datetime.now(timezone.utc).isoformat()))
        # Raise outside the transaction so refusal/failure evidence is retained.
        if response is None:
            raise AccountRefusal('owner-account request ' + outcome.lower()) from None
        return response


def register_owner_account_reads(runtime, gateway):
    """Mount a Module 22 handler on an actual AtlasRuntime instance.

    Enrollment/revocation never travel in a handoff. Payload has only service
    and path; tenant comes from the authenticated runtime context. Reads need
    the independently bound exact-resource permission, never a payload flag.
    """
    import asyncio

    async def handler(context, handoff):
        if type(handoff.payload) is not dict or set(handoff.payload) != {'service', 'path'}:
            raise ValueError('exact service/path payload required')
        response = await asyncio.to_thread(gateway.get, context.tenant_id,
                                          handoff.payload['service'], handoff.payload['path'])
        return {'http_status': response.status_code, 'body': response.text,
                'identity_checked': True, 'semantic_success_verified': False}
    runtime.register(22, 'owner_account_read', handler)
