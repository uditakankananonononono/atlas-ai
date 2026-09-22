from pathlib import Path

import fitz
import pytest

from app.auth.session import RefreshSessionStore
from app.platform.document_processing import extract_pdf, partition_layout
from app.platform.secrets import SecretError, VaultLiteralProvider


def test_a18_pymupdf_extracts_real_pdf_text_and_page_provenance(tmp_path):
    path=tmp_path/'text.pdf';document=fitz.open();page=document.new_page();page.insert_text((72,72),'Atlas evidence text');document.save(path)
    output=extract_pdf(str(path))
    assert output['page_count']==1 and output['pages']==[{'page':1,'text':'Atlas evidence text','method':'pymupdf'}]
    assert output['requires_review'] is False


def test_a19_blank_scanned_pdf_enters_tesseract_path_and_flags_empty_ocr(monkeypatch,tmp_path):
    path=tmp_path/'scan.pdf';document=fitz.open();document.new_page();document.save(path)
    called=[]
    monkeypatch.setattr('pytesseract.image_to_string',lambda image: called.append(image.size) or '')
    output=extract_pdf(str(path),ocr=True)
    assert called and output['pages'][0]['method']=='tesseract' and output['requires_review'] is True


def test_a20_unstructured_partitions_real_file_with_metadata(tmp_path):
    path=tmp_path/'layout.txt';path.write_text('Atlas heading\n\nBody paragraph')
    blocks=partition_layout(str(path))
    assert len(blocks)>=2 and {b['text'] for b in blocks}=={'Atlas heading','Body paragraph'}
    assert all(b['type'] and b['metadata']['filename']=='layout.txt' for b in blocks)


def test_a22_refresh_session_rotates_once_rejects_replay_and_tenant_is_bound():
    store=RefreshSessionStore();token=store.issue('subject','tenant-a',ttl_seconds=300)
    rotated=store.rotate(token)
    assert rotated!=token
    with pytest.raises(PermissionError,match='replayed'):
        store.rotate(token)
    key=__import__('hashlib').sha256(rotated.encode()).hexdigest()
    assert store._records[key].tenant_id=='tenant-a' and store._records[key].subject=='subject'


def test_a23_vault_provider_requests_literal_key_and_never_returns_path_or_token():
    calls=[]
    provider=VaultLiteralProvider('secret',lambda mount,name:calls.append((mount,name)) or {'value':'s3cr3t'})
    assert provider.get('API_KEY')=='s3cr3t' and calls==[('secret','API_KEY')]
    with pytest.raises(SecretError,match='literal key'):
        provider.get('../other/path')
    with pytest.raises(SecretError,match='unavailable'):
        VaultLiteralProvider('secret',lambda mount,name:{}).get('MISSING')
