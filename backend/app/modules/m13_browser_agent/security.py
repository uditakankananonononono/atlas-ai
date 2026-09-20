from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit


class NavigationBlocked(ValueError):
    pass


_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


def _is_forbidden_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value.split("%", 1)[0])
    return not ip.is_global


def _resolve(host: str, port: int) -> set[str]:
    try:
        return {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise NavigationBlocked("host resolution failed") from error


def _host_allowed(host: str, allowed_hosts: Iterable[str] | None) -> bool:
    if not allowed_hosts:
        return True
    # An explicit leading dot means that host and its subdomains. Otherwise exact only.
    for item in allowed_hosts:
        item = item.lower().rstrip(".")
        if item.startswith(".") and (host == item[1:] or host.endswith(item)):
            return True
        if host == item:
            return True
    return False


def validate_public_url(url: str, allowed_hosts: Iterable[str] | None = None) -> str:
    if not isinstance(url, str) or len(url) > 4096:
        raise NavigationBlocked("invalid URL")
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise NavigationBlocked("only http(s) URLs with a host are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise NavigationBlocked("embedded credentials are forbidden")
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise NavigationBlocked("local/metadata destinations forbidden")
    if not _host_allowed(host, allowed_hosts):
        raise NavigationBlocked("host is not allow-listed")
    try:
        if _is_forbidden_ip(host):
            raise NavigationBlocked("non-public destination forbidden")
    except ValueError:
        addresses = _resolve(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not addresses or any(_is_forbidden_ip(ip) for ip in addresses):
            raise NavigationBlocked("non-public destination forbidden")
    # Remove a fragment because it is never sent and must not affect approval identity.
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def values_digest(values: dict[str, str]) -> str:
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_digest(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
