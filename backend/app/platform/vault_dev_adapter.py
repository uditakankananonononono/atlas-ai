"""ATLAS-U-1209 actual Atlas local Vault bootstrap. PUBLIC-DEMO parse-only setup.

- Managed HCP Vault, prod KMS/HSM integration.
- "Encrypted at rest" applies ONLY to the Fernet fallback file - NEVER to the Vault dev server or its volume (dev server storage is unencrypted in-memory/file backend).
- No real secrets exist in this unit; production secret provisioning is out of scope.

Reads actual peer-provisioned Vault runtime values, never seeds or fabricates.
Execs actual migrate/uvicorn/celery command after replacing parse-only values.
Explicit runtime env outage fallback precedes existing encrypted file. Public
fallback key is loaded from environment and provides no security assurance.
Independent hermetic and actual loopback acceptance must precede landing.
Auth configuration is preserved, never relaxed. Compose interpolation docs:
https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/
https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/
"""
import argparse
import os
from urllib.parse import urlparse
import httpx
from .encryption import SecretCipher
from .fernet_file_fallback import FernetFileFallback, valid_value
from .file_secrets_adapter import FileEnvironmentSecretProvider
from .secrets import SecretError

RUNTIME_SECRET_NAMES = ('ATLAS_TOKEN_KEY', 'ATLAS_API_KEY_ENCRYPTION_KEY')


class VaultDevSecretProvider:
    def __init__(self, url, token, fallback, client):
        parsed = urlparse(url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'vault-dev', 'localhost', '127.0.0.1'}
                or parsed.username or parsed.password or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment):
            raise SecretError('local Vault endpoint required')
        self.url, self.token = url.rstrip('/'), valid_value(token)
        self.fallback, self.client = fallback, client

    def get(self, name):
        if name not in RUNTIME_SECRET_NAMES:
            raise SecretError('unknown runtime secret name')
        try:
            response = self.client.get(self.url + '/v1/secret/data/' + name,
                                       headers={'X-Vault-Token': self.token}, timeout=3,
                                       follow_redirects=False)
        except httpx.TransportError:
            return valid_value(self.fallback.get(name))
        if response.status_code != 200:
            raise SecretError('Vault HTTP read rejected; no outage fallback')
        try:
            return valid_value(response.json()['data']['data']['value'])
        except (ValueError, KeyError, TypeError) as exc:
            raise SecretError('Vault response invalid') from exc


def inject_runtime_environment(provider, base):
    values = {name: valid_value(provider.get(name)) for name in RUNTIME_SECRET_NAMES}
    try:
        SecretCipher(values['ATLAS_API_KEY_ENCRYPTION_KEY'])
    except ValueError as exc:
        raise SecretError('runtime encryption key invalid') from exc
    return {**base, **values}


def bootstrap_runtime(provider, command, base, store, execute=os.execvpe):
    if not command:
        raise SecretError('actual runtime command required')
    environment = inject_runtime_environment(provider, dict(base))
    store.write({name: environment[name] for name in RUNTIME_SECRET_NAMES})
    return execute(command[0], list(command), environment)


def main():
    parser = argparse.ArgumentParser(description='Actual Atlas local Vault bootstrap')
    parser.add_argument('--volume', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    url = os.environ.get('ATLAS_VAULT_DEV_URL', 'http://vault-dev:8200')
    token = valid_value(os.environ.get('ATLAS_VAULT_DEV_TOKEN'))
    fallback_key = valid_value(os.environ.get('ATLAS_VAULT_FALLBACK_KEY'))
    with httpx.Client() as client:
        store = FernetFileFallback(args.volume, fallback_key, RUNTIME_SECRET_NAMES)
        # ONLY explicit runtime fallback variables. Parse-only key names are
        # cleared by override and never accepted as bootstrap fallback values.
        fallback = FileEnvironmentSecretProvider(store, {
            name: os.environ.get('ATLAS_RUNTIME_FALLBACK_' + name, '')
            for name in RUNTIME_SECRET_NAMES})
        provider = VaultDevSecretProvider(url, token, fallback, client)
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        return bootstrap_runtime(provider, command, os.environ, store)


if __name__ == '__main__':
    raise SystemExit(main())
