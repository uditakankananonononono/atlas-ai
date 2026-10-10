"""Opt-in local-compose CA and TLS bootstrap, not a runtime attestation.

Fleet-wide cert issuance/rotation across a real production deployment. mTLS is OPT-IN via the override, not default; no claim that the base deployment is encrypted.

Only the five local-compose services are covered. External providers and unrelated
optional adapters are outside this local substitute. CA signing key stays in
memory, never printed or persisted. Delete the PKI volume to issue a new CA.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import ssl
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROLES = ('api', 'worker', 'migrate', 'postgres', 'redis')


def _write(path: Path, data: bytes, mode: int = 0o644) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(data)
    os.chmod(path, mode)


def issue_local_material(destination: Path) -> None:
    """Create a fresh CA and per-service keys atomically; refuse overwrite.

    Entropy/key bytes intentionally vary. Certificates expire after 30 days;
    renewal and deployment rotation are not automatic. No stored CA private key.
    """
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('refusing existing PKI destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.atlas-pki-', dir=destination.parent))
    try:
        now = datetime.now(timezone.utc)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Atlas local opt-in CA')])
        ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                   .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
                   .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                   .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                               key_encipherment=False, data_encipherment=False,
                                               key_agreement=False, key_cert_sign=True, crl_sign=True,
                                               encipher_only=False, decipher_only=False), critical=True)
                   .sign(ca_key, hashes.SHA256()))
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
        for role in ROLES:
            folder = staging / role
            folder.mkdir(mode=0o755)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            # PostgreSQL cert auth maps CN to the database role 'atlas'. Service
            # hostname is separately verified via SAN by every TLS client.
            cert = (x509.CertificateBuilder()
                    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'atlas')]))
                    .issuer_name(ca_name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .add_extension(x509.SubjectAlternativeName([x509.DNSName(role)]), critical=False)
                    .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH,
                                                         ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
                    .sign(ca_key, hashes.SHA256()))
            _write(folder / 'ca.pem', ca_pem)
            _write(folder / 'cert.pem', cert.public_bytes(serialization.Encoding.PEM))
            _write(folder / 'key.pem', key.private_bytes(serialization.Encoding.PEM,
                                                        serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()), 0o600)
        _write(staging / 'postgres' / 'pg_hba.conf',
               b'local all all trust\nhostnossl all all all reject\nhostssl all atlas all cert\nhostssl all all all reject\n')
        os.chmod(staging, 0o755)
        # Existing destinations are rejected above; caller must serialize init.
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_material(destination: Path, *, role: str | None = None) -> None:
    """Fail closed on partial, expired, replaced or mismatched persisted PKI."""
    destination = Path(destination)
    if role is not None and role not in ROLES:
        raise ValueError("unknown service role")
    check_full_policy = role is None
    reference_ca = None
    now = datetime.now(timezone.utc)
    for role in ((role,) if role else ROLES):
        folder = destination / role
        for name in ('ca.pem', 'cert.pem', 'key.pem'):
            if (folder / name).is_symlink() or not (folder / name).is_file():
                raise ValueError('missing or symlinked PKI file')
        ca_bytes = (folder / 'ca.pem').read_bytes()
        if reference_ca is not None and ca_bytes != reference_ca:
            raise ValueError('inconsistent local CA')
        reference_ca = ca_bytes
        authority = x509.load_pem_x509_certificate(ca_bytes)
        cert = x509.load_pem_x509_certificate((folder / 'cert.pem').read_bytes())
        key = serialization.load_pem_private_key((folder / 'key.pem').read_bytes(), password=None)
        for item in (authority, cert):
            if not item.not_valid_before_utc <= now < item.not_valid_after_utc:
                raise ValueError('PKI expired or not yet valid; recreate local volume')
        if not authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise ValueError('invalid CA constraint')
        authority.public_key().verify(authority.signature, authority.tbs_certificate_bytes,
                                      padding.PKCS1v15(), authority.signature_hash_algorithm)
        authority.public_key().verify(cert.signature, cert.tbs_certificate_bytes,
                                      padding.PKCS1v15(), cert.signature_hash_algorithm)
        if cert.issuer != authority.subject:
            raise ValueError('wrong certificate issuer')
        if cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) != key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo):
            raise ValueError('certificate/key mismatch')
        if x509.DNSName(role) not in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value:
            raise ValueError('wrong service SAN')
        if cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value != 'atlas':
            raise ValueError('wrong client identity')
        usage = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH not in usage or ExtendedKeyUsageOID.SERVER_AUTH not in usage:
            raise ValueError('missing TLS usages')
        if (folder / 'key.pem').stat().st_mode & 0o777 != 0o600:
            raise ValueError('unsafe key permissions')
    expected = 'local all all trust\nhostnossl all all all reject\nhostssl all atlas all cert\nhostssl all all all reject\n'
    if check_full_policy and (destination / 'postgres/pg_hba.conf').read_text() != expected:
        raise ValueError('PostgreSQL certificate policy changed')


def server_context(folder: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(folder / 'ca.pem'))
    context.load_cert_chain(str(folder / 'cert.pem'), str(folder / 'key.pem'))
    return context


def client_context(folder: Path) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(folder / 'ca.pem'))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(folder / 'cert.pem'), str(folder / 'key.pem'))
    return context


def main() -> None:
    parser = argparse.ArgumentParser(description='Opt-in local PKI; never logs key material')
    parser.add_argument('command', choices=['init', 'check'])
    parser.add_argument('--root', type=Path, default=Path('/mtls/pki'))
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument('--container-owners', action='store_true')
    args = parser.parse_args()
    if args.command == 'init':
        if not args.root.exists():
            issue_local_material(args.root)
        validate_material(args.root, role=args.role)
        if args.container_owners:
            import pwd
            account = pwd.getpwnam('atlas')
            for role in ('api', 'worker', 'migrate'):
                os.chown(args.root / role / 'key.pem', account.pw_uid, account.pw_gid)
    else:
        validate_material(args.root, role=args.role)


if __name__ == '__main__':
    main()
