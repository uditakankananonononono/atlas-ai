"""Enumerated failure-record redaction, not general secret detection."""
import pytest
from app.modules.m18_side_hustle_scraper.lane_models import CollectionError

@pytest.mark.parametrize('reason',[
    'key = FIXTURE-SECRET',
    'Authorization: Bearer FIXTURE-SECRET',
    '{"access_token": "FIXTURE-SECRET"}',
    'request https://h.test/?api%5fkey=FIXTURE-SECRET',
    'request https://FIXTURE-SECRET@h.test/path',
])
def test_reason_known_credential_shapes_removed(reason):
    e=CollectionError(source='test',url='https://h.test',reason=reason)
    assert 'FIXTURE-SECRET' not in e.reason

@pytest.mark.parametrize('url',[
    'https://h.test/#access_token=FIXTURE-SECRET',
    'https://h.test/?api%255fkey=FIXTURE-SECRET',
])
def test_url_fragment_and_twice_encoded_key_removed(url):
    e=CollectionError(source='test',url=url,reason='error')
    assert 'FIXTURE-SECRET' not in e.url

def test_failure_record_fields_bounded():
    e=CollectionError(source='test',url='https://h.test/?q='+'x'*20000,reason='x'*20000)
    assert len(e.url)<=8192 and len(e.reason)<=8192

def test_malformed_url_records_refusal_not_parser_crash():
    e=CollectionError(source='test',url='https://[broken/?key=FIXTURE-SECRET',reason='error')
    assert 'FIXTURE-SECRET' not in e.url
