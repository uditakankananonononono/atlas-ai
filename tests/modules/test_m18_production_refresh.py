import hashlib
from app.modules.m18_side_hustle_scraper.lane_http import FakeHttpClient,HttpError
from app.modules.m18_side_hustle_scraper.lane_models import SourceKind,FetchPolicy
from app.modules.m18_side_hustle_scraper import wiring

def test_production_refetcher_hashes_bytes_and_returns_cache_headers(monkeypatch):
 fake=FakeHttpClient();url='https://example.org/feed';fake.add(url,b'new bytes',headers={'etag':'v2','last-modified':'today'})
 monkeypatch.setattr(wiring,'UrllibHttpClient',lambda:fake)
 out=wiring.build_refetcher()(url,SourceKind.RSS)
 assert out=={'status':200,'not_modified':False,'content_hash':hashlib.sha256(b'new bytes').hexdigest(),'etag':'v2','last_modified':'today'}
def test_production_refetcher_returns_honest_http_failure(monkeypatch):
 fake=FakeHttpClient();url='https://example.org/dead';fake.add_error(url,HttpError(url,410,'gone'))
 monkeypatch.setattr(wiring,'UrllibHttpClient',lambda:fake)
 assert wiring.build_refetcher()(url,SourceKind.RSS)=={'status':410,'error':'gone'}
