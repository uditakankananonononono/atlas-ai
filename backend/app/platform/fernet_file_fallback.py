"""ATLAS-U-1209 development Fernet fallback artifact.

- Managed HCP Vault, prod KMS/HSM integration.
- "Encrypted at rest" applies ONLY to the Fernet fallback file - NEVER to the Vault dev server or its volume (dev server storage is unencrypted in-memory/file backend).
- No real secrets exist in this unit; production secret provisioning is out of scope.

PUBLIC-DEMO-ONLY key in the env file is public, not a confidentiality/security guarantee.
Runtime provisioning and independent audit belong to the peer, never builder.
"""
import json
import os
from pathlib import Path
import tempfile
from .encryption import SecretCipher
from .secrets import SecretError



def valid_value(value):
    if not isinstance(value, str) or not value or len(value) > 65536:
        raise SecretError('secret value missing or invalid')
    return value


class FernetFileFallback:
    def __init__(self, volume, key, names):
        self.volume = Path(volume)
        self.path = self.volume / 'runtime-secrets.fernet'
        self.allowed_names = tuple(names)
        self.cipher = SecretCipher(key)

    def _validate(self, values):
        if not isinstance(values, dict) or set(values) != set(self.allowed_names):
            raise SecretError('fallback name set is invalid')
        return {name: valid_value(values[name]) for name in self.allowed_names}

    def write(self, values):
        encrypted = self.cipher.encrypt(json.dumps(self._validate(values), sort_keys=True))
        self.volume.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix='.runtime-secrets-', dir=self.volume)
        try:
            with os.fdopen(fd, 'w', encoding='ascii') as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def read(self):
        try:
            if self.path.is_symlink():
                raise SecretError('fallback symlink refused')
            return self._validate(json.loads(self.cipher.decrypt(self.path.read_text(encoding='ascii'))))
        except (OSError, ValueError, UnicodeError) as exc:
            raise SecretError('fallback unavailable or authentication failed') from exc
