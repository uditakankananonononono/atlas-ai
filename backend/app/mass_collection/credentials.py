"""Origin-scoped owner credentials encrypted with Atlas's existing TokenCipher."""
from pathlib import Path
import json
from cryptography.fernet import InvalidToken
from app.core.token_crypto import TokenCipher, TokenCryptoError
from .engine import CollectionError, origin, atomic_json


class CredentialStore:
    def __init__(self, path: Path | str, tenant: str, *, master_secret=None):
        self.path = Path(path)
        try:
            self.cipher = TokenCipher(tenant, master_secret)
        except TokenCryptoError as exc:
            raise CollectionError(str(exc)) from exc

    def save(self, name: str, url: str, bearer: str, *, owner_confirmed: bool):
        if owner_confirmed is not True or not isinstance(name, str) or not isinstance(bearer, str) or not name or not bearer or '\n' in bearer or '\r' in bearer:
            raise CollectionError('own-account confirmation and a valid token are required')
        site = origin(url)
        if not site.startswith('https://') and not site.startswith('http://127.0.0.1:'):
            raise CollectionError('credentials require HTTPS')
        try:
            rows = json.loads(self.path.read_text()) if self.path.exists() else {}
            if not isinstance(rows, dict): raise TypeError('credential store must be an object')
        except (OSError, ValueError, TypeError, RecursionError, MemoryError) as exc:
            raise CollectionError('credential store unreadable') from exc
        rows[name] = {'origin': site, 'token': self.cipher.encrypt(bearer), 'owner_confirmed': True}
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_json(self.path, rows)

    def headers(self, name, url):
        try:
            row = json.loads(self.path.read_text())[name]
            if row['origin'] != origin(url) or row['owner_confirmed'] is not True:
                raise CollectionError('credential origin or ownership mismatch')
            return {'Authorization': 'Bearer '+self.cipher.decrypt(row['token'])}
        except (OSError, KeyError, ValueError, TypeError, AttributeError, RecursionError, MemoryError, InvalidToken, TokenCryptoError) as exc:
            raise CollectionError('credential unavailable') from exc
