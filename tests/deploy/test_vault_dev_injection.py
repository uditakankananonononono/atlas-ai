"""ATLAS-U-1209 test-first, hermetic authored NOT RUN. No Vault provisioning.

Peer must additionally verify actual Vault and Atlas service processes.
"""
import json
from pathlib import Path
import httpx
import pytest
import yaml
from app.platform.secrets import SecretError, SecretProvider
from app.platform.encryption import SecretCipher
from app.platform.fernet_file_fallback import FernetFileFallback
from app.platform.file_secrets_adapter import FileEnvironmentSecretProvider
from app.platform.vault_dev_adapter import (VaultDevSecretProvider, RUNTIME_SECRET_NAMES,
    inject_runtime_environment, bootstrap_runtime)
ROOT=Path(__file__).resolve().parents[2]
PUBLIC_PARSE_VALUES=dict(line.split('=',1) for line in
    (ROOT/'deploy/local/dev-public-placeholder.env').read_text().splitlines()
    if line and not line.startswith('#'))
DEMO_KEY=PUBLIC_PARSE_VALUES['ATLAS_API_KEY_ENCRYPTION_KEY']


def values(): return {'ATLAS_TOKEN_KEY':'hermetic-runtime-fixture','ATLAS_API_KEY_ENCRYPTION_KEY':DEMO_KEY}


def fallback(tmp_path,env=None):
    store=FernetFileFallback(tmp_path/'dev-volume',DEMO_KEY,RUNTIME_SECRET_NAMES)
    store.write(values())
    return store,FileEnvironmentSecretProvider(store,env or {})


def test_single_public_key_definition_and_parse_only_env_contract():
    text=(ROOT/'deploy/local/dev-public-placeholder.env').read_text()
    assert set(PUBLIC_PARSE_VALUES)=={'POSTGRES_PASSWORD','REDIS_PASSWORD','ATLAS_OIDC_ISSUER',
        'ATLAS_OIDC_AUDIENCE','ATLAS_TOKEN_KEY','ATLAS_API_KEY_ENCRYPTION_KEY'}
    assert text.count(DEMO_KEY)==1 and 'PUBLIC-DEMO parse-only' in text
    assert (ROOT/'deploy/vault/dev-secret-names.txt').read_text().splitlines()==list(RUNTIME_SECRET_NAMES)
    assert RUNTIME_SECRET_NAMES==('ATLAS_TOKEN_KEY','ATLAS_API_KEY_ENCRYPTION_KEY')
    for name in ('vault_dev_adapter.py','file_secrets_adapter.py','fernet_file_fallback.py'):
        assert DEMO_KEY not in (ROOT/'backend/app/platform'/name).read_text()
    cipher=SecretCipher(DEMO_KEY)
    assert cipher.decrypt(cipher.encrypt('fixture'))=='fixture'


def test_vault_read_only_exact_auth_path_and_runtime_value_injection(tmp_path):
    store,other=fallback(tmp_path)
    def handler(request):
        assert request.method=='GET'  # implementation must never provision secrets
        assert request.headers['X-Vault-Token']=='PUBLIC-DEMO-ONLY-vault-token'
        name=request.url.path.rsplit('/',1)[-1]
        assert request.url.path=='/v1/secret/data/'+name
        return httpx.Response(200,json={'data':{'data':{'value':values()[name]}}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider:SecretProvider=VaultDevSecretProvider('http://vault-dev:8200','PUBLIC-DEMO-ONLY-vault-token',other,client)
        assert inject_runtime_environment(provider,{'context':'keep'})=={'context':'keep',**values()}


def test_outage_env_then_file_no_ambient_read(tmp_path,monkeypatch):
    store,other=fallback(tmp_path,{'ATLAS_TOKEN_KEY':'fixture-env'})
    monkeypatch.setenv('ATLAS_TOKEN_KEY','ambient-must-not-read')
    def offline(request): raise httpx.ConnectError('offline',request=request)
    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        p=VaultDevSecretProvider('http://vault-dev:8200','PUBLIC-DEMO-ONLY-vault-token',other,client)
        assert p.get('ATLAS_TOKEN_KEY')=='fixture-env'
        assert p.get('ATLAS_API_KEY_ENCRYPTION_KEY')==DEMO_KEY
    assert FileEnvironmentSecretProvider(store,{}).get('ATLAS_TOKEN_KEY')==values()['ATLAS_TOKEN_KEY']


@pytest.mark.parametrize('status',[301,403,404,500])
def test_http_errors_not_outage(tmp_path,status):
    store,other=fallback(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status))) as c:
        with pytest.raises(SecretError):
            VaultDevSecretProvider('http://vault-dev:8200','PUBLIC-DEMO-ONLY-vault-token',other,c).get('ATLAS_TOKEN_KEY')


@pytest.mark.parametrize('payload',[{}, {'data':{'data':{}}}, {'data':{'data':{'value':''}}}, {'data':{'data':{'value':7}}}])
def test_bad_data_fails_closed(tmp_path,payload):
    store,other=fallback(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as c:
        with pytest.raises(SecretError):
            VaultDevSecretProvider('http://vault-dev:8200','PUBLIC-DEMO-ONLY-vault-token',other,c).get('ATLAS_TOKEN_KEY')


def test_fernet_ciphertext_roundtrip_volume_permissions_and_tamper(tmp_path):
    store,other=fallback(tmp_path)
    raw=store.path.read_bytes()
    assert all(v.encode() not in raw for v in values().values()) and b'ATLAS_TOKEN_KEY' not in raw
    assert store.path.stat().st_mode & 0o777==0o600
    assert store.path.parent==tmp_path/'dev-volume' and store.read()==values()
    assert not list(store.path.parent.glob('.runtime-secrets-*'))
    store.path.write_bytes(raw[:-4]+b'AAAA')
    with pytest.raises(SecretError): store.read()


@pytest.mark.parametrize('command',[
 ['python','scripts/migrate.py'],
 ['uvicorn','app.main:app','--host','0.0.0.0','--port','8080'],
 ['celery','-A','app.workers.celery_app:celery_app','worker','--loglevel=INFO']])
def test_actual_runtime_dispatch_and_auth_environment_preserved(tmp_path,command):
    store,p=fallback(tmp_path)
    base={'ATLAS_ENV':'production','ATLAS_DEV_NO_AUTH':'0','ATLAS_OIDC_ISSUER':PUBLIC_PARSE_VALUES['ATLAS_OIDC_ISSUER'],
          'ATLAS_OIDC_AUDIENCE':'atlas-dev','ATLAS_DATABASE_URL':'fixture-db','ATLAS_REDIS_URL':'fixture-redis'}
    before=dict(base); calls=[]
    def receipt(executable,argv,env): calls.append((executable,argv,env)); return 73
    assert bootstrap_runtime(p,command,base,store,receipt)==73
    assert base==before and len(calls)==1
    executable,argv,env=calls[0]
    assert executable==command[0] and argv==command
    assert all(env[k]==v for k,v in base.items())
    assert {n:env[n] for n in RUNTIME_SECRET_NAMES}==values() and store.read()==values()


def test_bad_key_missing_secret_never_executes_or_updates(tmp_path):
    store,p=fallback(tmp_path); old=store.path.read_bytes()
    class Invalid:
        def get(self,name): return 'fixture-token' if name=='ATLAS_TOKEN_KEY' else 'invalid-fernet'
    class Missing:
        def get(self,name): raise SecretError('unavailable')
    def forbidden(*args): raise AssertionError('invalid/partial exec')
    for provider in (Invalid(),Missing()):
        with pytest.raises(SecretError): bootstrap_runtime(provider,['python','scripts/migrate.py'],{},store,forbidden)
        assert store.path.read_bytes()==old


@pytest.mark.parametrize('name',['../outside','','A/B','FAKE'])
def test_unknown_names_never_http(tmp_path,name):
    store,p=fallback(tmp_path)
    def forbidden(r): raise AssertionError('unknown name HTTP')
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as c:
        with pytest.raises(SecretError): VaultDevSecretProvider('http://vault-dev:8200','fixture-token',p,c).get(name)


def test_missing_file_never_fabricates_runtime_values(tmp_path):
    store=FernetFileFallback(tmp_path/'empty',DEMO_KEY,RUNTIME_SECRET_NAMES)
    with pytest.raises(SecretError): FileEnvironmentSecretProvider(store,{}).get('ATLAS_TOKEN_KEY')


def test_override_actual_services_cli_env_only_no_inline_keys_no_auth_relaxation():
    path=ROOT/'deploy/local/docker-compose.vault.yml'
    doc=yaml.safe_load(path.read_text()); base=yaml.safe_load((ROOT/'deploy/local/docker-compose.yml').read_text())
    assert set(doc['services'])=={'api','worker','migrate','vault-dev'}
    for name in ('api','worker','migrate'):
        s=doc['services'][name]
        assert s['entrypoint']==['python','-m','app.platform.vault_dev_adapter','--volume','/vault-fallback-dev','--']
        assert s['command']==base['services'][name]['command']
        e=s['environment']
        assert e['ATLAS_ENV']=='production' and e['ATLAS_DEV_NO_AUTH']=='0'
        assert e['ATLAS_TOKEN_KEY']=='' and e['ATLAS_API_KEY_ENCRYPTION_KEY']==''
        assert e['ATLAS_VAULT_FALLBACK_KEY']=='${ATLAS_API_KEY_ENCRYPTION_KEY:?public-demo parse key required}'
        assert s['env_file']==['./dev-public-placeholder.env']
        assert s['depends_on']['vault-dev']['condition']=='service_healthy'
        assert 'vault-fallback-dev:/vault-fallback-dev' in s['volumes']
    assert '@sha256:' in doc['services']['vault-dev']['image']
    assert doc['services']['vault-dev']['ports']==['127.0.0.1:18201:8200']
    text=path.read_text()
    assert '--env-file deploy/local/dev-public-placeholder.env' in text
    assert 'ATLAS_TOKEN_KEY=' not in text and 'ATLAS_API_KEY_ENCRYPTION_KEY=' not in text


def test_public_demo_key_regression_is_44_chars_decodes_32_bytes_and_defined_once():
    # This failed for shipped 277a8b9e. Never inherit auditor scratch-key PASS.
    import base64
    assert len(DEMO_KEY) == 44
    assert len(base64.urlsafe_b64decode(DEMO_KEY)) == 32
    env_text = (ROOT/'deploy/local/dev-public-placeholder.env').read_text()
    assert env_text.count(DEMO_KEY) == 1
    assert sum(path.read_text().count(DEMO_KEY) for path in (
        ROOT/'backend/app/platform/vault_dev_adapter.py',
        ROOT/'backend/app/platform/file_secrets_adapter.py',
        ROOT/'backend/app/platform/fernet_file_fallback.py',
        ROOT/'deploy/local/dev-public-placeholder.env',
        ROOT/'deploy/local/docker-compose.vault.yml',
        ROOT/'deploy/vault/dev-secret-names.txt',
        ROOT/'tests/deploy/test_vault_dev_injection.py')) == 1
    cipher = SecretCipher(DEMO_KEY)
    assert cipher.decrypt(cipher.encrypt('key-regression-fixture')) == 'key-regression-fixture'


def test_http_error_exception_is_not_transport_outage(tmp_path):
    store, env_provider = fallback(tmp_path)
    request = httpx.Request('GET','http://vault-dev:8200/v1/secret/data/ATLAS_TOKEN_KEY')
    response = httpx.Response(403, request=request)
    error = httpx.HTTPStatusError('fixture HTTP denial', request=request, response=response)
    def denied(request): raise error
    with httpx.Client(transport=httpx.MockTransport(denied)) as client:
        provider = VaultDevSecretProvider('http://vault-dev:8200','fixture-token',env_provider,client)
        with pytest.raises(httpx.HTTPStatusError) as raised:
            provider.get('ATLAS_TOKEN_KEY')
        assert raised.value is error


def test_non200_success_shaped_payload_still_raises_secret_error(tmp_path):
    store, env_provider = fallback(tmp_path)
    payload = {'data':{'data':{'value':'must-not-be-returned'}}}
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(403,json=payload))) as client:
        with pytest.raises(SecretError):
            VaultDevSecretProvider('http://vault-dev:8200','fixture-token',env_provider,client).get('ATLAS_TOKEN_KEY')


def test_redirects_not_followed_even_if_client_default_is_true(tmp_path):
    store, env_provider = fallback(tmp_path)
    visited = []
    def redirect(request):
        visited.append(str(request.url))
        if request.url.path.endswith('/redirect-target'):
            return httpx.Response(200,json={'data':{'data':{'value':'redirect-leak'}}})
        return httpx.Response(302,headers={'Location':'http://vault-dev:8200/redirect-target'})
    with httpx.Client(transport=httpx.MockTransport(redirect),follow_redirects=True) as client:
        with pytest.raises(SecretError):
            VaultDevSecretProvider('http://vault-dev:8200','fixture-token',env_provider,client).get('ATLAS_TOKEN_KEY')
    assert len(visited) == 1 and visited[0].endswith('/ATLAS_TOKEN_KEY')


@pytest.mark.parametrize('url',[
    'http://example.com:8200','http://vault-dev.attacker.invalid:8200',
    'http://localhost.attacker.invalid:8200','http://127.0.0.2:8200',
    'http://user:pass@vault-dev:8200','https://vault-dev:8200'])
def test_actual_host_allowlist_refuses_untrusted_before_io(tmp_path,url):
    store, env_provider = fallback(tmp_path)
    def forbidden(request): raise AssertionError('untrusted host reached transport')
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        with pytest.raises(SecretError):
            VaultDevSecretProvider(url,'fixture-token',env_provider,client)


@pytest.mark.parametrize('url',['http://vault-dev:8200','http://localhost:18201','http://127.0.0.1:18201'])
def test_actual_host_allowlist_accepts_expected_local_hosts(tmp_path,url):
    store, env_provider = fallback(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'data':{'data':{'value':'fixture-local'}}}))) as client:
        assert VaultDevSecretProvider(url,'fixture-token',env_provider,client).get('ATLAS_TOKEN_KEY') == 'fixture-local'


def test_bootstrap_persists_fresh_vault_values_before_exec_and_failure_stops_exec(tmp_path):
    store, old_provider = fallback(tmp_path)
    fresh_values = {**values(),'ATLAS_TOKEN_KEY':'new-vault-runtime-fixture'}
    class FreshProvider:
        def get(self,name): return fresh_values[name]
    def receipt(executable,argv,env):
        assert store.read() == fresh_values
        assert env['ATLAS_TOKEN_KEY'] == fresh_values['ATLAS_TOKEN_KEY']
        return 91
    assert bootstrap_runtime(FreshProvider(),['uvicorn','app.main:app'],{},store,receipt) == 91
    class BrokenStore:
        def write(self, content): raise OSError('fixture-volume-write-failed')
    def forbidden(*args): raise AssertionError('exec after store.write failure')
    with pytest.raises(OSError,match='fixture-volume-write-failed'):
        bootstrap_runtime(FreshProvider(),['uvicorn','app.main:app'],{},BrokenStore(),forbidden)


def test_runtime_values_override_stale_base_without_mutating_base(tmp_path):
    store, provider = fallback(tmp_path)
    base = {'ATLAS_TOKEN_KEY':'PUBLIC-DEMO-stale-parse',
            'ATLAS_API_KEY_ENCRYPTION_KEY':'PUBLIC-DEMO-invalid-parse',
            'ATLAS_DEV_NO_AUTH':'0'}
    before = dict(base)
    result = inject_runtime_environment(provider,base)
    assert base == before
    assert {name:result[name] for name in RUNTIME_SECRET_NAMES} == values()
    assert result['ATLAS_DEV_NO_AUTH'] == '0'


def test_fallback_symlink_is_rejected_and_new_volume_directory_is_0700(tmp_path):
    store, provider = fallback(tmp_path)
    assert store.path.parent.stat().st_mode & 0o777 == 0o700
    actual = tmp_path/'outside-volume-ciphertext'
    store.path.replace(actual)
    store.path.symlink_to(actual)
    assert actual.is_file() and store.path.is_symlink()
    with pytest.raises(SecretError,match='symlink'):
        store.read()
    assert actual.read_bytes()  # rejected read must not alter outside target


def test_exact_loopback_publication_and_verified_vault_digest():
    doc = yaml.safe_load((ROOT/'deploy/local/docker-compose.vault.yml').read_text())
    vault = doc['services']['vault-dev']
    assert vault['ports'] == ['127.0.0.1:18201:8200']
    assert vault['image'] == 'hashicorp/vault:1.18.3@sha256:8f1ba670da547c6af67be55609bd285c3ee3d8b73f88021adbfc43c82ca409e8'
