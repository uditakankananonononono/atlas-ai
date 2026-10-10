"""Authored first, NOT RUN. TLS via memory BIOs only, no network or containers."""
import importlib.util
from pathlib import Path
import ssl

import pytest
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('atlas_local_ca_x01', ROOT / 'deploy/mtls/local_ca.py')
ca = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ca)


def exchange(server_context, client_context, hostname):
    si, so, ci, co = (ssl.MemoryBIO() for _ in range(4))
    server = server_context.wrap_bio(si, so, server_side=True)
    client = client_context.wrap_bio(ci, co, server_hostname=hostname)
    server_done = client_done = False
    for _ in range(40):
        for endpoint, side in [(client, 'client'), (server, 'server')]:
            try:
                endpoint.do_handshake()
                if side == 'client':
                    client_done = True
                else:
                    server_done = True
            except ssl.SSLWantReadError:
                pass
        outgoing = co.read()
        if outgoing:
            si.write(outgoing)
        outgoing = so.read()
        if outgoing:
            ci.write(outgoing)
        if server_done and client_done:
            client.write(b'authenticated')
            si.write(co.read())
            assert server.read() == b'authenticated'
            return
    raise AssertionError('TLS handshake did not finish within bounded BIO pump')


@pytest.fixture
def issued(tmp_path):
    ca.issue_local_material(tmp_path / 'pki')
    return tmp_path / 'pki'


def test_valid_client_requires_real_certificate_and_authenticates(issued):
    exchange(ca.server_context(issued / 'redis'), ca.client_context(issued / 'api'), 'redis')


def test_absent_client_certificate_is_rejected(issued):
    client = ssl.create_default_context(cafile=str(issued / 'api/ca.pem'))
    with pytest.raises(ssl.SSLError):
        exchange(ca.server_context(issued / 'redis'), client, 'redis')


def test_untrusted_client_is_rejected(issued, tmp_path):
    other = tmp_path / 'other'
    ca.issue_local_material(other)
    client = ca.client_context(other / 'api')
    client.load_verify_locations(cafile=str(issued / 'api/ca.pem'))
    with pytest.raises(ssl.SSLError):
        exchange(ca.server_context(issued / 'redis'), client, 'redis')


def test_wrong_server_hostname_is_rejected(issued):
    with pytest.raises(ssl.SSLError):
        exchange(ca.server_context(issued / 'redis'), ca.client_context(issued / 'api'), 'not-redis')


def test_certificates_have_distinct_keys_role_sans_and_client_identity(issued):
    keys = set()
    for role in ca.ROLES:
        folder = issued / role
        cert = x509.load_pem_x509_certificate((folder / 'cert.pem').read_bytes())
        key = serialization.load_pem_private_key((folder / 'key.pem').read_bytes(), password=None)
        keys.add(key.public_key().public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo))
        assert x509.DNSName(role) in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        usage = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        assert ExtendedKeyUsageOID.CLIENT_AUTH in usage and ExtendedKeyUsageOID.SERVER_AUTH in usage
        assert cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value == 'atlas'
        assert (folder / 'key.pem').stat().st_mode & 0o777 == 0o600
        assert not (folder / 'ca-key.pem').exists()
    assert len(keys) == len(ca.ROLES)
    assert 'hostssl all atlas all cert' in (issued / 'postgres/pg_hba.conf').read_text()
    assert 'hostnossl all all all reject' in (issued / 'postgres/pg_hba.conf').read_text()


def test_refuses_reissuance_or_partial_existing_output(issued, tmp_path):
    original = (issued / 'api/cert.pem').read_bytes()
    with pytest.raises(FileExistsError):
        ca.issue_local_material(issued)
    assert (issued / 'api/cert.pem').read_bytes() == original
    partial = tmp_path / 'partial'
    partial.mkdir()
    with pytest.raises(FileExistsError):
        ca.issue_local_material(partial)


def test_celery_additive_config_sets_both_verified_tls_channels(monkeypatch):
    spec = importlib.util.spec_from_file_location('atlas_celery_tls_x01', ROOT / 'backend/app/workers/celery_tls_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('ATLAS_MTLS_ENABLED', '1')
    monkeypatch.setenv('ATLAS_MTLS_DIR', '/mtls/worker')
    settings = module.tls_settings()
    for name in ['broker_use_ssl', 'redis_backend_use_ssl']:
        assert settings[name] == {'ssl_cert_reqs': ssl.CERT_REQUIRED,
                                 'ssl_ca_certs': '/mtls/worker/ca.pem',
                                 'ssl_certfile': '/mtls/worker/cert.pem',
                                 'ssl_keyfile': '/mtls/worker/key.pem',
                                 'ssl_check_hostname': True}
    monkeypatch.setenv('ATLAS_MTLS_ENABLED', '0')
    with pytest.raises(RuntimeError):
        module.tls_settings()


def test_override_routes_all_base_services_to_verified_tls_and_no_plaintext_ports():
    base = yaml.safe_load((ROOT / 'deploy/local/docker-compose.yml').read_text())
    override = yaml.safe_load((ROOT / 'deploy/local/docker-compose.mtls.yml').read_text())
    services = override['services']
    assert set(base['services']) <= set(services)
    for role in ['migrate', 'api', 'worker']:
        settings = services[role]['environment']
        assert 'sslmode=verify-full' in settings['ATLAS_DATABASE_URL']
        assert f'sslcert=/mtls/pki/{role}/cert.pem' in settings['ATLAS_DATABASE_URL']
        assert settings['ATLAS_REDIS_URL'].startswith('rediss://')
        assert 'ssl_cert_reqs=required' in settings['ATLAS_REDIS_URL']
        assert 'ssl_check_hostname=true' in settings['ATLAS_REDIS_URL']
        assert f'ssl_certfile=/mtls/pki/{role}/cert.pem' in settings['ATLAS_REDIS_URL']
        assert services[role]['depends_on']['mtls-init']['condition'] == 'service_completed_successfully'
        assert any('/app/deploy/mtls/local_ca.py:ro' in item for item in services[role]['volumes'])
    assert 'app.workers.celery_tls_config' in str(services['worker']['command'])
    assert '--ssl-cert-reqs' in str(services['api']['command'])
    assert '--port 0' in str(services['redis']['command'])
    assert '--tls-auth-clients yes' in str(services['redis']['command'])
    assert 'ssl=on' in str(services['postgres']['command'])
    assert 'hba_file=/run/atlas-postgres/pg_hba.conf' in str(services['postgres']['command'])
    assert services['mtls-init']['user'] == '0:0'
    assert 'local_ca.py' in str(services['mtls-init']['command'])


def test_persisted_pki_validation_checks_policy_and_key_corruption(issued):
    ca.validate_material(issued)
    ca.validate_material(issued, role='worker')
    (issued / 'postgres/pg_hba.conf').write_text('host all all all trust\n')
    with pytest.raises(ValueError):
        ca.validate_material(issued)
    (issued / 'worker/key.pem').write_bytes(b'not-a-private-key')
    with pytest.raises(ValueError):
        ca.validate_material(issued, role='worker')


def test_api_command_requires_exact_client_certificate_guard():
    import shlex
    override = yaml.safe_load((ROOT / 'deploy/local/docker-compose.mtls.yml').read_text())
    command = shlex.split(override['services']['api']['command'][-1])
    assert command.count('--ssl-cert-reqs') == 1
    assert command[command.index('--ssl-cert-reqs') + 1] == '2'


def test_persisted_key_permissions_fail_closed(issued):
    (issued / 'api/key.pem').chmod(0o644)
    with pytest.raises(ValueError, match='unsafe key permissions'):
        ca.validate_material(issued)


def test_expired_pki_fails_closed(issued, monkeypatch):
    from datetime import datetime, timedelta
    future = datetime.now(ca.timezone.utc) + timedelta(days=31)
    class FutureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return future
    monkeypatch.setattr(ca, 'datetime', FutureClock)
    with pytest.raises(ValueError, match='expired or not yet valid'):
        ca.validate_material(issued)


def test_inconsistent_local_ca_fails_closed(issued, tmp_path):
    other = tmp_path / 'other-ca'
    ca.issue_local_material(other)
    (issued / 'worker/ca.pem').write_bytes((other / 'worker/ca.pem').read_bytes())
    with pytest.raises(ValueError, match='inconsistent local CA'):
        ca.validate_material(issued)
