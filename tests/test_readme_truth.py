from pathlib import Path

def test_readme_does_not_call_live_modules_stubs_or_claim_finished():
    text=Path('README.md').read_text()
    assert '|Stub|' not in text
    assert 'not a finished production service' in text
    assert 'docs/IMPLEMENTATION_AUDIT.md' in text
    assert 'docs/FALLBACK_AUDIT.md' in text

def test_catalog_requires_explicit_status():
    text=Path('backend/app/modules/catalog.py').read_text()
    assert 'status: str = "stub"' not in text
