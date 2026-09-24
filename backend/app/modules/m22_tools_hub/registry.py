"""Hash-checked artifact fetch from official package registries (free, no keys).

Supported: PyPI wheels (already ZIP) and npm tarballs (repacked to ZIP after the
registry's SHA-512 integrity check). Every download is checked against the digest
the registry itself publishes before Atlas builds a manifest. Sources without a
registry-published digest (plain GitHub repositories) are refused, not guessed.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = {"pypi.org", "files.pythonhosted.org", "registry.npmjs.org"}
MAX_METADATA_BYTES = 5 * 1024 * 1024
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


class RegistryError(ValueError):
    pass


Fetch = Callable[[str, int], bytes]


class _SameAllowlistRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise RegistryError(f"refusing non-registry URL: {url}")


def http_fetch(url: str, limit: int) -> bytes:
    """Default HTTPS fetch: allowlisted hosts only (including redirects), size-capped."""
    _check_url(url)
    opener = build_opener(_SameAllowlistRedirect())
    req = Request(url, headers={"User-Agent": "AtlasAI-ToolsHub/1.0", "Accept": "application/json, */*"})
    with opener.open(req, timeout=30) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise RegistryError("registry response exceeds size limit")
    return data


@dataclass(frozen=True)
class FetchedArtifact:
    registry: str
    package: str
    registry_version: str
    manifest_version: str
    artifact: bytes
    source_url: str
    registry_digest: str  # e.g. "sha256:<hex>" or "sha512-<base64>"
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def artifact_sha256(self) -> str:
        return hashlib.sha256(self.artifact).hexdigest()


def manifest_version(raw: str, registry: str) -> str:
    """Map a registry version onto the manifest's semver rule without hiding the original."""
    if _SEMVER.fullmatch(raw):
        return raw
    nums = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", raw)
    if not nums:
        raise RegistryError(f"cannot map version {raw!r} to semver")
    parts = [str(int(x or 0)) for x in nums.groups()]
    tag = re.sub(r"[^0-9A-Za-z.-]", "-", raw).strip(".-") or "x"
    return f"{'.'.join(parts)}+{registry}.{tag}"


def _zip_files(blob: bytes) -> dict[str, str]:
    files: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            with z.open(info) as h:
                files[info.filename] = hashlib.sha256(h.read(MAX_ARTIFACT_BYTES + 1)).hexdigest()
    return files


def fetch_pypi(package: str, version: str | None = None, fetch: Fetch = http_fetch) -> FetchedArtifact:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}", package):
        raise RegistryError("invalid PyPI package name")
    path = f"{quote(package)}/{quote(version)}" if version else quote(package)
    meta = json.loads(fetch(f"https://pypi.org/pypi/{path}/json", MAX_METADATA_BYTES))
    info = meta.get("info") or {}
    real_version = str(info.get("version") or version or "")
    wheels = [u for u in meta.get("urls", []) if u.get("packagetype") == "bdist_wheel" and not u.get("yanked")]
    # Prefer a pure-Python wheel so the install is platform independent.
    wheels.sort(key=lambda u: (not str(u.get("filename", "")).endswith("-none-any.whl"), u.get("size") or 0))
    if not wheels:
        raise RegistryError(f"{package} {real_version} publishes no wheel; sdist builds are not run by Atlas")
    chosen = wheels[0]
    expected = str((chosen.get("digests") or {}).get("sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RegistryError("PyPI did not publish a SHA-256 for the wheel")
    blob = fetch(str(chosen["url"]), MAX_ARTIFACT_BYTES)
    if hashlib.sha256(blob).hexdigest() != expected:
        raise RegistryError("downloaded wheel does not match the PyPI SHA-256")
    return FetchedArtifact(
        registry="pypi", package=package, registry_version=real_version,
        manifest_version=manifest_version(real_version, "pypi"), artifact=blob,
        source_url=str(chosen["url"]), registry_digest=f"sha256:{expected}", files=_zip_files(blob),
        metadata={"filename": chosen.get("filename"), "license": info.get("license"),
                  "summary": info.get("summary"), "requires_python": info.get("requires_python")})


def fetch_npm(package: str, version: str | None = None, fetch: Fetch = http_fetch) -> FetchedArtifact:
    if not re.fullmatch(r"(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]{0,213}", package):
        raise RegistryError("invalid npm package name")
    name = package.replace("/", "%2F")
    meta = json.loads(fetch(f"https://registry.npmjs.org/{name}/{quote(version or 'latest')}", MAX_METADATA_BYTES))
    dist = meta.get("dist") or {}
    integrity = str(dist.get("integrity") or "")
    if not integrity.startswith("sha512-"):
        raise RegistryError("npm did not publish a sha512 integrity for this version")
    tarball = str(dist.get("tarball") or "")
    blob = fetch(tarball, MAX_ARTIFACT_BYTES)
    if base64.b64encode(hashlib.sha512(blob).digest()).decode() != integrity[len("sha512-"):]:
        raise RegistryError("downloaded tarball does not match the npm integrity digest")
    out = io.BytesIO()
    files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not member.isfile():
                raise RegistryError(f"npm tarball contains a link or special file: {member.name}")
            rel = member.name.split("/", 1)[1] if "/" in member.name else member.name
            if not rel or rel.startswith("/") or ".." in rel.split("/") or "\\" in rel:
                raise RegistryError(f"unsafe path in npm tarball: {member.name}")
            if rel in files:
                raise RegistryError(f"duplicate path in npm tarball: {rel}")
            data = tar.extractfile(member).read()
            z.writestr(rel, data)
            files[rel] = hashlib.sha256(data).hexdigest()
    real_version = str(meta.get("version") or version or "")
    return FetchedArtifact(
        registry="npm", package=package, registry_version=real_version,
        manifest_version=manifest_version(real_version, "npm"), artifact=out.getvalue(),
        source_url=tarball, registry_digest=integrity, files=files,
        metadata={"license": meta.get("license"), "main": meta.get("main"), "bin": meta.get("bin"),
                  "repacked_from_tarball": True})


def default_entrypoint(fetched: FetchedArtifact) -> str:
    files = fetched.files
    if fetched.registry == "npm":
        bins = fetched.metadata.get("bin")
        candidates = list(bins.values()) if isinstance(bins, dict) else [bins] if isinstance(bins, str) else []
        candidates += [fetched.metadata.get("main"), "index.js", "package.json"]
        for c in candidates:
            if isinstance(c, str) and c.lstrip("./") in files:
                return c.lstrip("./")
    else:
        inits = sorted((p for p in files if p.endswith("/__init__.py") and p.count("/") == 1), key=len)
        if inits:
            return inits[0]
        meta = [p for p in files if p.endswith(".dist-info/METADATA")]
        if meta:
            return meta[0]
    return sorted(files)[0]


def tool_id_for(registry: str, package: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", package.lower().lstrip("@")).strip("-")
    return f"{registry}-{base}"[:120]


def build_manifest(fetched: FetchedArtifact, *, entrypoint: str | None = None,
                   permissions: list[str] | None = None) -> dict[str, Any]:
    entry = entrypoint or default_entrypoint(fetched)
    if entry not in fetched.files:
        raise RegistryError(f"entrypoint {entry!r} is not in the artifact")
    publisher = {"pypi": "PyPI (pypi.org)", "npm": "npm registry (registry.npmjs.org)"}[fetched.registry]
    return {
        "schema_version": 1, "tool_id": tool_id_for(fetched.registry, fetched.package),
        "version": fetched.manifest_version, "entrypoint": entry, "files": dict(fetched.files),
        "permissions": list(permissions or []),
        "provenance": {"source_url": fetched.source_url, "publisher": publisher,
                       "artifact_sha256": fetched.artifact_sha256},
        "metadata": {"registry": fetched.registry, "package": fetched.package,
                     "registry_version": fetched.registry_version, "registry_digest": fetched.registry_digest,
                     **{k: v for k, v in fetched.metadata.items() if v is not None}},
    }


def registry_for_candidate(source: str, url: str) -> str:
    host = urlparse(url).hostname or ""
    if source == "pypi" or host.endswith("pypi.org"):
        return "pypi"
    if source == "npm" or host.endswith("npmjs.com") or host.endswith("npmjs.org"):
        return "npm"
    raise RegistryError(f"candidate source {source!r} has no registry-published digest; upload a reviewed artifact instead")


def fetch_for(registry: str, package: str, version: str | None, fetch: Fetch = http_fetch) -> FetchedArtifact:
    if registry == "pypi":
        return fetch_pypi(package, version, fetch)
    if registry == "npm":
        return fetch_npm(package, version, fetch)
    raise RegistryError(f"unsupported registry {registry!r}")
