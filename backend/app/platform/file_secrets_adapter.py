"""ATLAS-U-1209 explicit file/env SecretProvider.get adapter.

Vault transport-unreachable fallback policy: nonempty explicit env mapping
first, then authenticated Fernet file. Empty env entries mean unavailable.
HTTP errors/auth denial/malformed Vault replies must NOT invoke this fallback.
Never silently reads ambient process env. No secret values in error messages.

- Managed HCP Vault, prod KMS/HSM integration.
- "Encrypted at rest" applies ONLY to the Fernet fallback file - NEVER to the Vault dev server or its volume (dev server storage is unencrypted in-memory/file backend).
- No real secrets exist in this unit; production secret provisioning is out of scope.
"""
from .fernet_file_fallback import valid_value
from .secrets import SecretError


class FileEnvironmentSecretProvider:
    def __init__(self, store, environ):
        self.store, self.environ = store, dict(environ)

    def get(self, name):
        if name not in self.store.allowed_names:
            raise SecretError('unknown runtime secret name')
        value = self.environ.get(name)
        if value:
            return valid_value(value)
        return valid_value(self.store.read()[name])
