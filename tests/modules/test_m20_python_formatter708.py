"""Python formatter behavior, safety checks and authenticated routes."""
import ast
import hashlib
import sys

import black
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m20_general_cognitive_worker.python_formatter708 import format_python, FormatterUnavailable
from app.modules.m20_general_cognitive_worker.formatting708_routes import router


@pytest.mark.parametrize('source', [
    'x=1\n',
    'def f(x,y):\n return x+y\n',
    '# keep comment\nx={"日本語": [1,2,3]}\n',
    'def f(x):\n return f"value={x!r}"\n',
    'from os import system\nsystem("DO NOT EXECUTE")\n',
    'x=1 # type: int\n',
    '',
])
def test_real_formatter_and_structural_checks(source):
    out = format_python(source)
    assert out['formatted_source'] == black.format_str(source, mode=black.Mode())
    assert ast.dump(ast.parse(source, type_comments=True)) == ast.dump(ast.parse(out['formatted_source'], type_comments=True))
    assert out['before_sha256'] == hashlib.sha256(source.encode()).hexdigest()
    assert out['after_sha256'] == hashlib.sha256(out['formatted_source'].encode()).hexdigest()
    assert out['second_pass_equal'] and out['formatter_executed']
    assert not out['source_executed'] and not out['repository_mutated']
    assert not out['runtime_semantics_verified']
    assert format_python(out['formatted_source'])['changed'] is False


def test_actual_change_and_diff():
    out = format_python('x=1\n')
    assert out['formatted_source'] == 'x = 1\n'
    assert '-x=1' in out['diff'] and '+x = 1' in out['diff']


@pytest.mark.parametrize('source', ['def broken(', 'x=\x00', '\ud800', 'x'*25001, '日'*10000])
def test_bad_source_refused(source):
    with pytest.raises(ValueError):
        format_python(source)


@pytest.mark.parametrize('length', [True, '88', 39, 201, 88.0])
def test_bad_style_refused(length):
    with pytest.raises(ValueError):
        format_python('x=1', length)


def test_ast_change_refused(monkeypatch):
    monkeypatch.setattr(black, 'format_str', lambda source, mode: 'x = 2\n')
    with pytest.raises(ValueError, match='changed the Black-normalized Python AST'):
        format_python('x=1\n')


def test_nonidempotence_refused(monkeypatch):
    outputs = iter(['x = 1\n', 'x = 1\n\n'])
    monkeypatch.setattr(black, 'format_str', lambda source, mode: next(outputs))
    with pytest.raises(ValueError, match='not idempotent'):
        format_python('x=1\n')


def test_optional_dependency_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, 'black', None)
    with pytest.raises(FormatterUnavailable):
        format_python('x=1\n')


def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_signed_owner_route(oidc_auth_headers, monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    c = client()
    headers = oidc_auth_headers('tenant-a', 'actor-a')
    out = c.post('/code-formatting/708/format-python', headers=headers, json={'source': 'x=1\n'})
    assert out.status_code == 200
    assert out.json()['formatted_source'] == 'x = 1\n'
    assert out.json()['tenant_id'] == 'tenant-a' and out.json()['actor_id'] == 'actor-a'
    for forged in [{'tenant_id': 'tenant-b'}, {'actor_id': 'actor-b'},
                   {'resource_refs': [{'tenant_id': 'tenant-b'}]}]:
        assert c.post('/code-formatting/708/format-python', headers=headers,
                      json={'source': 'x=1', **forged}).status_code == 403
    assert c.post('/code-formatting/708/format-python', json={'source': 'x=1'}).status_code == 401
    for bad in [{'source':'x=1', 'command':'run'}, {'source':'x=1','line_length':True},
                {'source':'日'*10000}]:
        assert c.post('/code-formatting/708/format-python', headers=headers,json=bad).status_code == 422

    assert c.post('/code-formatting/708/format-python', headers={**headers, 'Content-Type':'application/json'},
                  content=b'{"source":"\\ud800"}').status_code == 422


def test_route_optional_dependency_unavailable(oidc_auth_headers, monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setitem(sys.modules, 'black', None)
    assert client().post('/code-formatting/708/format-python',headers=oidc_auth_headers(),
                         json={'source':'x=1'}).status_code == 503


@pytest.mark.parametrize('source', [
    'def f():\n """ hi  """\n pass\n',
    '"""   module docs   """\nx=1\n',
    'class C:\n """\n  multiline\n    docs\n """\n pass\n',
])
def test_docstring_normalization_uses_black_safe_mode(source):
    out = format_python(source)
    black.assert_equivalent(source, out['formatted_source'])
    assert out['second_pass_equal'] and 'docstring' in out['ast_comparison']
    assert any('__doc__' in limit for limit in out['limits'])


def test_black_is_available_in_dev_dependency_group():
    import tomllib
    from pathlib import Path
    data = tomllib.loads((Path(__file__).resolve().parents[2] / 'pyproject.toml').read_text())
    assert 'black==26.10.1' in data['project']['optional-dependencies']['dev']
