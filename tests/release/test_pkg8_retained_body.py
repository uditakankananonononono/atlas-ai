"""Harness portability checks; no product mutation or network."""
import hashlib,importlib.util,subprocess
from pathlib import Path
import pytest
PATH=Path(__file__).resolve().parents[2]/'audits/m23-legacy-crawl-delay/pkg8-followup/replay.py'
spec=importlib.util.spec_from_file_location('pkg8_replay',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
EXPECTED_BODY_SHA256='76e00134fa6e9d61c9e68c03747aef5d43d21074fa58fd0c70050f064c2cc9af'
BODY=(PATH.parent/'legacy-body.txt').read_bytes()
assert hashlib.sha256(BODY).hexdigest()==EXPECTED_BODY_SHA256
# Byte pin is independent of the harness constant, not proof of historical authorship.

@pytest.fixture
def retained(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'OUT',tmp_path)
    (tmp_path/'legacy-body.txt').write_bytes(BODY)
    return tmp_path/'legacy-body.txt'

def test_missing_pin_uses_retained_bytes(retained,monkeypatch):
    def missing(*args,**kw):return subprocess.CompletedProcess(args,128,'','missing object')
    monkeypatch.setattr(m.subprocess,'run',missing)
    body,status=m.load_legacy_body(compare_git=True)
    assert body.encode()==BODY and status=='unavailable'
    assert retained.read_bytes()==BODY

def test_tampered_body_refused_before_git_or_mutation(retained,monkeypatch):
    retained.write_bytes(BODY+b'# tampered\n')
    def no_git(*args,**kw):pytest.fail('git reached before body hash refusal')
    monkeypatch.setattr(m.subprocess,'run',no_git)
    with pytest.raises(ValueError,match='SHA mismatch'):m.load_legacy_body(compare_git=True)

def test_available_body_compares_without_overwrite(retained,monkeypatch):
    source='def fetch_case_metadata(case_id, transport=None):\n'+BODY.decode()
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,0,source,''))
    assert m.load_legacy_body(compare_git=True)==(BODY.decode(),'matched')
    assert retained.read_bytes()==BODY

def test_available_body_mismatch_refused_without_overwrite(retained,monkeypatch):
    source='def fetch_case_metadata(case_id, transport=None):\n    return {}\n'
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,0,source,''))
    with pytest.raises(ValueError,match='disagrees'):m.load_legacy_body(compare_git=True)
    assert retained.read_bytes()==BODY

@pytest.mark.parametrize('src',['no site',"return fetch_case_metadata_bounded(case_id, transport, **kwargs)\n"*2])
def test_delegate_site_must_be_unique(src):
    with pytest.raises(ValueError,match='exactly once'):m.kwargs_mutant(src)

def test_unique_delegate_site_replaced():
    assert m.kwargs_mutant('return fetch_case_metadata_bounded(case_id, transport, **kwargs)')=='return fetch_case_metadata_bounded(case_id, transport)'


def test_default_does_not_attempt_git_comparison(retained,monkeypatch):
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:pytest.fail('unexpected optional Git comparison'))
    assert m.load_legacy_body()==(BODY.decode(),'not-requested')

def test_optin_prohibits_lazy_fetch(retained,monkeypatch):
    def missing(*a,**k):
        assert k['env']['GIT_NO_LAZY_FETCH']=='1'
        assert k['env']['GIT_TERMINAL_PROMPT']=='0'
        return subprocess.CompletedProcess(a,128,'','missing')
    monkeypatch.setattr(m.subprocess,'run',missing)
    assert m.load_legacy_body(compare_git=True)==(BODY.decode(),'unavailable')

def test_missing_executable_refused(retained,monkeypatch):
    def absent(*a,**k):raise FileNotFoundError('git absent')
    monkeypatch.setattr(m.subprocess,'run',absent)
    with pytest.raises(ValueError,match='executable unavailable'):m.load_legacy_body(compare_git=True)
    assert retained.read_bytes()==BODY

@pytest.mark.parametrize('source',['def broken(', 'value = 1\n'])
def test_malformed_available_object_refused(retained,monkeypatch,source):
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,0,source,''))
    with pytest.raises(ValueError,match='body malformed'):m.load_legacy_body(compare_git=True)
    assert retained.read_bytes()==BODY
