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
