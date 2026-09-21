from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Protocol, Callable

class SecretError(RuntimeError): pass
class SecretProvider(Protocol):
    def get(self, name: str) -> str: ...

@dataclass
class EnvironmentSecretProvider:
    environ: dict[str,str] | None = None
    def get(self,name:str)->str:
        value=(self.environ or os.environ).get(name,"")
        if not value: raise SecretError(f"secret {name!r} is unavailable")
        return value

@dataclass
class GoogleSecretManagerProvider:
    project_id: str
    access: Callable[[str], bytes]
    def get(self,name:str)->str:
        if not name.replace("_","-").replace("-","").isalnum(): raise SecretError("invalid secret name")
        path=f"projects/{self.project_id}/secrets/{name}/versions/latest"
        value=self.access(path).decode("utf-8")
        if not value: raise SecretError(f"secret {name!r} is empty")
        return value

@dataclass
class VaultLiteralProvider:
    """Reads a literal KV path through an injected authenticated Vault client."""
    mount: str
    read: Callable[[str,str],dict[str,str]]
    def get(self,name:str)->str:
        if "/" in name or not name: raise SecretError("secret name must be a literal key")
        value=self.read(self.mount,name).get("value","")
        if not value: raise SecretError(f"secret {name!r} is unavailable")
        return value

def authenticated_vault_provider(url:str,token:str,mount:str='secret')->VaultLiteralProvider:
    """Build a real authenticated Vault KV v2 reader; token stays in process memory."""
    import hvac
    client=hvac.Client(url=url,token=token)
    if not client.is_authenticated():raise SecretError('Vault authentication failed')
    def read(_mount:str,name:str)->dict[str,str]:
        result=client.secrets.kv.v2.read_secret_version(path=name,mount_point=_mount)
        data=result.get('data',{}).get('data',{})
        value=data.get('value')
        return {'value':str(value) if value is not None else ''}
    return VaultLiteralProvider(mount,read)

# Compatibility with Python's standard-library ``secrets`` API.  This project
# historically used the top-level module name for its provider abstraction,
# which means it shadows stdlib ``secrets`` whenever Atlas runs from the repo
# root.  Starlette and Atlas modules legitimately import these symbols.
import base64 as _base64
import binascii as _binascii
import hmac as _hmac
import random as _random

SystemRandom = _random.SystemRandom
_sysrand = SystemRandom()
choice = _sysrand.choice
randbelow = _sysrand._randbelow
randbits = _sysrand.getrandbits
compare_digest = _hmac.compare_digest

def token_bytes(nbytes: int | None = None) -> bytes:
    if nbytes is None:
        nbytes = 32
    if not isinstance(nbytes, int):
        raise TypeError("nbytes must be an integer")
    if nbytes < 0:
        raise ValueError("nbytes must be non-negative")
    return os.urandom(nbytes)

def token_hex(nbytes: int | None = None) -> str:
    return _binascii.hexlify(token_bytes(nbytes)).decode("ascii")

def token_urlsafe(nbytes: int | None = None) -> str:
    return _base64.urlsafe_b64encode(token_bytes(nbytes)).rstrip(b"=").decode("ascii")
