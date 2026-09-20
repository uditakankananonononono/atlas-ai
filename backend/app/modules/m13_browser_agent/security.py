from __future__ import annotations
import hashlib,ipaddress,socket
from urllib.parse import urlparse
class NavigationBlocked(ValueError): pass

def validate_public_url(url:str,allowed_hosts:set[str]|None=None)->str:
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or not parsed.hostname: raise NavigationBlocked("only http(s) URLs with a host are allowed")
    if parsed.username or parsed.password: raise NavigationBlocked("embedded credentials are forbidden")
    host=parsed.hostname.lower().rstrip(".")
    if allowed_hosts and host not in allowed_hosts: raise NavigationBlocked("host is not allow-listed")
    if host in {"localhost","metadata.google.internal"}: raise NavigationBlocked("local/metadata destinations forbidden")
    try:
        for info in socket.getaddrinfo(host,parsed.port or 443):
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved: raise NavigationBlocked("non-public destination forbidden")
    except socket.gaierror as e: raise NavigationBlocked("host resolution failed") from e
    return url

def values_digest(values:dict[str,str])->str:
    canonical="\n".join(f"{k}={values[k]}" for k in sorted(values))
    return hashlib.sha256(canonical.encode()).hexdigest()
