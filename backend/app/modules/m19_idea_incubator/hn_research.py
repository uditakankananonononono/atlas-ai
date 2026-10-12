"""Live read-only HN discovery using the documented Algolia API.

No arbitrary destinations, credentials, writes, scraping, or redirect following.
The sample is bounded and is not an exhaustive internet trend measurement.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import httpx
from .trend_pipeline_u03 import extract_trends

ENDPOINT = 'https://hn.algolia.com/api/v1/search_by_date'
DOCS = 'https://hn.algolia.com/api'
MAX_BYTES = 1_000_000

class ResearchUnavailable(RuntimeError):
    pass

class HNResearch:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def collect(self, query: str, *, as_of: str, limit: int = 100) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError('query is required within 200 characters')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be integer 1..100')
        stamp = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('as_of must be timezone aware')
        params = {'query': query, 'tags': 'story', 'hitsPerPage': limit,
                  'numericFilters': f'created_at_i<={int(stamp.timestamp())}', 'page': 0}
        try:
            with httpx.Client(timeout=10, follow_redirects=False, transport=self.transport,
                              headers={'User-Agent': 'AtlasResearch/1.0', 'Accept': 'application/json'}) as c:
                with c.stream('GET', ENDPOINT, params=params) as resp:
                    if resp.status_code != 200:
                        raise ResearchUnavailable('research source unavailable')
                    if 'application/json' not in resp.headers.get('content-type', '').lower():
                        raise ResearchUnavailable('unsupported research response')
                    body = bytearray()
                    for chunk in resp.iter_bytes(8192):
                        if len(body) + len(chunk) > MAX_BYTES:
                            raise ResearchUnavailable('research response exceeds bound')
                        body.extend(chunk)
            data = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(data, dict) or not isinstance(data.get('hits'), list):
                raise ValueError()
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise ResearchUnavailable('research source returned invalid data') from None
        posts, seen = [], set()
        for hit in data['hits'][:limit]:
            if not isinstance(hit, dict):
                continue
            pid, author, text, when = (hit.get(x) for x in ('objectID', 'author', 'title', 'created_at'))
            if not all(isinstance(x, str) and x.strip() for x in (pid, author, text, when)):
                continue
            if not pid.isdigit() or len(pid) > 30 or pid in seen or len(author) > 200 or len(text) > 10000:
                continue
            try:
                posted = datetime.fromisoformat(when.replace('Z', '+00:00'))
                if posted.tzinfo is None or posted > stamp:
                    continue
            except ValueError:
                continue
            seen.add(pid)
            posts.append({'post_id': pid, 'author': author, 'text': text, 'posted_at': when,
                          'platform': 'hacker_news', 'source_url': f'https://news.ycombinator.com/item?id={pid}'})
        return {'posts': posts, 'response_sha256': sha256(body).hexdigest(),
                'request_url': str(httpx.URL(ENDPOINT, params=params)), 'docs_url': DOCS,
                'sample_limit': limit, 'exhaustive': False,
                'claim': 'source-reported HN story titles, not validated business outcomes'}

    def trends(self, query: str, *, as_of: str, limit: int = 100) -> dict:
        collection = self.collect(query, as_of=as_of, limit=limit)
        measured = extract_trends(collection['posts'], as_of=as_of) if collection['posts'] else {
            'status': 'NO_SOURCE_POSTS', 'trends': [], 'as_of': as_of}
        return {'collection': collection, 'measurement': measured,
                'learned_model': False, 'external_actions_executed': False}
