from __future__ import annotations

import bz2
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import ipaddress
import json
import os
import re
import unicodedata
import math
import zlib
from pathlib import Path
import socket
import sqlite3
import time
from urllib.parse import unquote_plus, parse_qsl, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from bs4 import BeautifulSoup
import httpx
from warcio.archiveiterator import ArchiveIterator


WARC_CHUNK = 65536
WARC_HEADER_LINE_MAX = 65536
WARC_HEADER_BLOCK_MAX = 1_048_576
DENIED_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    'fec0::/10', '192.0.0.0/24', '192.88.99.0/24', '2001:20::/28',
    '2001::/32', '64:ff9b:1::/48', '::/96', '100.64.0.0/10', '198.18.0.0/15',
    '192.31.196.0/24', '192.52.193.0/24', '192.175.48.0/24', '2001:1::/32', '2001:3::/32', '2001:4:112::/48', '2001:30::/28',
    # Round 5: explicit IANA special-purpose entries so the denylist does not depend on the running Python's tables.
    '3fff::/20', '5f00::/16', '2001:db8::/32', '2001::/23', '2001:2::/48', '2001:10::/28', '100::/64', '2620:4f:8000::/48',
    '0.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '192.0.2.0/24', '198.51.100.0/24',
    '203.0.113.0/24', '240.0.0.0/4', '255.255.255.255/32'))
NAT64_NETWORK = ipaddress.ip_network('64:ff9b::/96')


class CollectionError(RuntimeError):
    """A policy, quota, parse, or transport stop. Never bypass a stop."""


# Everything that can go wrong while reading untrusted input, mapped to CollectionError by callers.
INGEST_ERRORS = (OSError, ValueError, EOFError, zlib.error, RecursionError, MemoryError, TypeError, AttributeError,
                 IndexError, KeyError, ET.ParseError, DefusedXmlException)


def _need(value, kind, name):
    if kind is bool:
        ok = type(value) is bool
    elif kind is int:
        ok = type(value) is int
    elif kind == 'number':
        ok = type(value) in (int, float) and math.isfinite(value)
    else:
        ok = isinstance(value, kind) and type(value) is not bool
    if not ok:
        raise CollectionError(f'{name} has the wrong type')


@dataclass(frozen=True)
class Source:
    url: str
    format: str
    license: str
    terms_url: str
    terms_accepted: bool = False
    credential: str | None = None
    owner_account: bool = False
    training_reviewed: bool = False
    text_field: str = 'text'
    dataset: str = ''

    def __post_init__(self):
        for name in ('url', 'format', 'license', 'terms_url', 'text_field', 'dataset'):
            _need(getattr(self, name), str, name)
        if self.credential is not None: _need(self.credential, str, 'credential')
        for name in ('terms_accepted', 'owner_account', 'training_reviewed'):
            _need(getattr(self, name), bool, name)


@dataclass(frozen=True)
class Limits:
    max_records: int = 100_000
    max_storage_bytes: int = 1_000_000_000
    max_download_bytes: int = 250_000_000
    max_record_bytes: int = 2_000_000
    max_parse_bytes: int = 2_000_000_000
    max_disk_bytes: int = 4_000_000_000
    shard_records: int = 10_000
    request_interval: float = 3.0
    timeout: float = 30.0

    def __post_init__(self):
        for k in ('max_records', 'max_storage_bytes', 'max_download_bytes', 'max_record_bytes', 'max_parse_bytes', 'max_disk_bytes', 'shard_records'):
            _need(getattr(self, k), int, k)
        for k in ('request_interval', 'timeout'):
            _need(getattr(self, k), 'number', k)
        if any(getattr(self, k) <= 0 for k in ('max_records', 'max_storage_bytes', 'max_download_bytes', 'max_record_bytes', 'max_parse_bytes', 'max_disk_bytes', 'shard_records', 'timeout')) or self.request_interval < 0:
            raise ValueError('limits must be positive; interval may be zero for tests')


SENSITIVE_EXACT_KEYS = frozenset(('pw', 'tkn', 'otp', 'code', 'p'))  # too short for substring matching
SENSITIVE_QUERY_TOKENS = ('token', 'secret', 'key', 'auth', 'sig', 'pass', 'pwd', 'session', 'cred', 'jwt', 'bearer', 'cookie')
_BEARER_VALUE = re.compile(r'\bbearer[\s+:=_-]*[A-Za-z0-9._~+/=-]{16,}', re.I)
_KEY_VALUES = re.compile(r'ghp_[A-Za-z0-9]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bsk-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|xox[abprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}')
_JWT_VALUE = re.compile(r'eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*')


def _decode_stable(text: str) -> str:
    """NFKC + percent-decode in a loop until stable. Raises if it never settles."""
    for _ in range(32):
        nxt = unicodedata.normalize('NFKC', unquote_plus(text))
        if nxt == text: return text
        text = nxt
    raise CollectionError('credentials in URL are forbidden')


def _bad_chars(text: str) -> bool:
    return any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs', 'Co', 'Cn') for c in text)


def _sensitive_key(key: str) -> bool:
    key = _decode_stable(key)
    if _bad_chars(key): return True
    flat = re.sub(r'[^a-z0-9]', '', key.lower())
    return flat in SENSITIVE_EXACT_KEYS or any(t in flat for t in SENSITIVE_QUERY_TOKENS)


def _sensitive_value(value: str) -> bool:
    value = _decode_stable(value)
    return _bad_chars(value) or bool(_BEARER_VALUE.search(value) or _JWT_VALUE.search(value) or _KEY_VALUES.search(value))


def _screen_url_credentials(p) -> None:
    """Defense-in-depth heuristic, NOT a guarantee: it rejects URLs whose query keys (any ';' or '&'
    separated pair), query values (Bearer/JWT shaped), or path segments look like credentials.
    Unusual encodings or opaque secrets can still pass; credentials belong in CredentialStore."""
    pairs = [x for x in re.split(r'[&;]', p.query) if x != '']
    for pair in pairs:
        key, _, value = pair.partition('=')
        if _sensitive_key(key) or _sensitive_value(value) or (_sensitive_value(key) and not value):
            raise CollectionError('credentials in URL are forbidden')
    for segment in p.path.split('/'):
        for part in segment.split(';'):
            key, eq, value = part.partition('=')
            decoded = _decode_stable(part)
            flat = re.sub(r'[^a-z0-9]', '', decoded.lower())
            if _bad_chars(decoded) or _sensitive_value(part) or (eq and _sensitive_key(key)) or flat in _SENSITIVE_SEGMENTS:
                raise CollectionError('credentials in URL are forbidden')


_SENSITIVE_SEGMENTS = frozenset(t + s for t in ('token', 'accesstoken', 'authtoken', 'bearer', 'apikey', 'secret', 'session', 'sessionid', 'auth', 'jwt', 'password', 'passwd', 'key', 'sig', 'signature', 'credentials', 'cred') for s in ('', 's'))


def origin(url: str) -> str:
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.fragment:
        raise CollectionError('require an HTTP(S) URL without credentials or fragment')
    _screen_url_credentials(p)
    try:
        port = p.port
    except ValueError as exc:
        raise CollectionError('invalid port') from exc
    host = p.hostname.lower()
    host = f'[{host}]' if ':' in host else host
    default = 443 if p.scheme == 'https' else 80
    return f'{p.scheme}://{host}' + (f':{port}' if port and port != default else '')


def normalized_license(value: str) -> str:
    """Exact-token form: surrounding whitespace stripped, ASCII-casefolded. Nothing else is
    normalized, so look-alikes ('MIT.', '-mit', 'cc-by-4.0+', zero-width or Unicode dashes) never match."""
    return str(value).strip().lower() if isinstance(value, str) else ''


# Explicit reviewed allowlist. Anything not here is never training_eligible.
_REVIEWED_LICENSES = ('cc0-1.0', 'cc-by-4.0', 'cc-by-sa-4.0', 'mit', 'apache-2.0', 'bsd-2-clause', 'bsd-3-clause', 'public-domain-explicit')
TRAINING_LICENSE_ALLOWLIST = frozenset(_REVIEWED_LICENSES)


def license_training_eligible(value: str) -> bool:
    token = normalized_license(value)
    return token.isascii() and token in TRAINING_LICENSE_ALLOWLIST


def html_text(data: bytes) -> str:
    soup = BeautifulSoup(data, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'nav']):
        tag.decompose()
    return soup.get_text('\n', strip=True)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, path)


class BoundedReader:
    def __init__(self, stream, limit, check, label='input'):
        self.label = label
        self.stream, self.limit, self.check, self.used = stream, limit, check, 0
        self.header_line_max = self.header_block_max = None
        self.in_headers, self.run, self.block = False, 0, 0

    def begin_headers(self): self.in_headers, self.run, self.block = True, 0, 0
    def end_headers(self): self.in_headers = False

    def _scan(self, data):
        if not self.in_headers or not data: return
        self.block += len(data)
        first, last = data.find(b'\n'), data.rfind(b'\n')
        if first < 0:
            self.run += len(data)
        else:
            longest = self.run + first
            if len(data) > self.header_line_max:
                longest = max([longest] + [len(x) for x in data.split(b'\n')])
            if longest > self.header_line_max: self.run = longest
            self.run = max(self.run, 0) if longest > self.header_line_max else len(data) - last - 1
        if self.run > self.header_line_max or self.block > self.header_block_max:
            raise CollectionError('WARC header line or header block too large')

    def _take(self, method, size=-1):
        self.check()
        remaining = self.limit - self.used
        size = min(size, remaining+1) if size >= 0 else remaining+1
        data = method(size); self.used += len(data)
        self._scan(data)
        if self.used > self.limit: raise CollectionError(f'expanded {self.label} byte quota exceeded')
        return data

    def read(self, size=-1): return self._take(self.stream.read, size)
    def readline(self, size=-1): return self._take(self.stream.readline, size)


class Collector:
    """One writer per local root. SQLite is authoritative; shards are snapshots."""
    agent = 'AtlasLocalCollector/1.0'

    def __init__(self, root: Path | str, *, limits: Limits | None = None, allow_loopback=False, credentials=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.limits = limits or Limits()
        self.allow_loopback = allow_loopback  # Python-only fixture switch, never API/CLI input.
        self.credentials = credentials
        for name in ('downloads', 'exports'):
            (self.root/name).mkdir(exist_ok=True, mode=0o700)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, body TEXT NOT NULL, bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS provenance (id TEXT NOT NULL, source TEXT NOT NULL, metadata TEXT NOT NULL, PRIMARY KEY(id,source));
                CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, source TEXT NOT NULL, state TEXT NOT NULL, inserted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS rates (origin TEXT PRIMARY KEY, next_request REAL NOT NULL);
            ''')
        os.chmod(self.root/'state.sqlite3', 0o600)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.root/'state.sqlite3', timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def writer(self):
        with (self.root/'writer.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                self.check_stop()
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def check_stop(self):
        if (self.root/'STOP').exists():
            raise CollectionError('kill switch active; remove STOP locally after review to resume')

    def disk_check(self, incoming=0):
        used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        if used + incoming > self.limits.max_disk_bytes:
            raise CollectionError('local disk quota exceeded; remove old exports/downloads or raise quota locally')

    def stop(self):
        (self.root/'STOP').touch(mode=0o600)

    def _address_allowed(self, address, *, embedded=False):
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if any(ip in net for net in DENIED_NETWORKS):
            return False
        if ip.version == 6:
            inner = None
            if ip.ipv4_mapped is not None:
                return self._address_allowed(str(ip.ipv4_mapped), embedded=embedded)
            if ip.sixtofour is not None:
                inner = ip.sixtofour
            elif ip in NAT64_NETWORK:
                inner = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
            # ISATAP interface id (RFC 5214): [0200|0000]:5efe:a.b.c.d. Checked for every IPv6
            # address, including the interface-id of 6to4 addresses.
            iid = int(ip) & 0xFFFFFFFFFFFFFFFF
            if (iid >> 32) in (0x00005EFE, 0x02005EFE):
                if not self._address_allowed(str(ipaddress.IPv4Address(iid & 0xFFFFFFFF)), embedded=True):
                    return False
            if inner is not None:
                return self._address_allowed(str(inner), embedded=True)
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_link_local or ip.is_private and not ip.is_loopback:
            return False
        if ip.is_loopback:
            return self.allow_loopback and not embedded
        return ip.is_global

    def _pinned_url(self, url):
        original = origin(url)
        p = urlsplit(url)
        try:
            addresses = sorted({info[4][0] for info in socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme=='https' else 80), type=socket.SOCK_STREAM)})
        except OSError as exc:
            raise CollectionError('DNS lookup failed') from exc
        if not addresses:
            raise CollectionError('no DNS addresses')
        for address in addresses:
            if not self._address_allowed(address):
                raise CollectionError('private, loopback, reserved, multicast, unspecified or link-local network target rejected')
        ip = addresses[0]
        ip = f'[{ip}]' if ':' in ip else ip
        port = f':{p.port}' if p.port else ''
        return urlunsplit((p.scheme, ip+port, p.path or '/', p.query, '')), urlsplit(original).netloc, p.hostname

    def _pace(self, url, delay=0):
        site = origin(url)
        with self.db() as db:
            row = db.execute('SELECT next_request FROM rates WHERE origin=?', (site,)).fetchone()
        until = row[0] + max(0.0, delay-self.limits.request_interval) if row else 0
        while time.time() < until:
            self.check_stop(); time.sleep(min(0.1, until-time.time()))
        self.check_stop()
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO rates VALUES (?,?)', (site, time.time()+max(self.limits.request_interval, delay)))

    @contextmanager
    def _request(self, url, *, headers=None, delay=0):
        self.check_stop()
        pinned, host, hostname = self._pinned_url(url)
        self._pace(url, delay)
        request_headers = {'User-Agent': self.agent, 'Host': host, 'Accept-Encoding': 'identity', **(headers or {})}
        try:
            with httpx.Client(timeout=self.limits.timeout, follow_redirects=False, trust_env=False) as client:
                with client.stream('GET', pinned, headers=request_headers, extensions={'sni_hostname': hostname}) as response:
                    if response.status_code in (401, 403, 429):
                        raise CollectionError(f'source blocked or throttled ({response.status_code}); stopped, no evasion')
                    yield response
        except httpx.HTTPError as exc:
            raise CollectionError('HTTP transport failed; rerun to resume') from exc

    def _robots(self, url):
        site = origin(url)
        with self._request(site+'/robots.txt') as response:
            if response.status_code == 404:
                return 0.0
            if response.status_code != 200:
                raise CollectionError('robots unavailable or redirected; refusing collection')
            buf = bytearray()
            for chunk in response.iter_bytes(8192):
                self.check_stop(); buf.extend(chunk)
                if len(buf) > 512_000:
                    raise CollectionError('robots exceeds size limit')
        parser = RobotFileParser(); parser.parse(bytes(buf).decode('utf-8', 'replace').splitlines())
        if not parser.can_fetch(self.agent, url):
            raise CollectionError('robots disallows this URL')
        delay = float(parser.crawl_delay(self.agent) or 0)
        rate = parser.request_rate(self.agent)
        if rate:
            delay = max(delay, rate.seconds/rate.requests)
        return delay

    def _validate_source(self, source):
        origin(source.url); origin(source.terms_url)
        if not source.terms_accepted or not source.license.strip():
            raise CollectionError('explicit terms review and license metadata are required')
        if source.format not in {'html', 'text', 'jsonl', 'wikipedia', 'commoncrawl', 'arxiv', 'parquet'}:
            raise CollectionError('unsupported source format')
        if source.credential and (not source.owner_account or not self.credentials):
            raise CollectionError('own-account confirmation and local encrypted credential store required')
        if source.credential and not origin(source.url).startswith('https://') and not self.allow_loopback:
            raise CollectionError('authenticated collection requires HTTPS')
        if source.owner_account and not source.credential:
            raise CollectionError('own-account sources need a scoped credential')

    def _download(self, source, key):
        target = self.root/'downloads'/f'{key}.data'
        partial = target.with_suffix('.part'); meta_path = target.with_suffix('.json')
        url = source.url
        for _ in range(6):
            delay = self._robots(url)
            auth = self.credentials.headers(source.credential, url) if source.credential else {}
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            offset = partial.stat().st_size if partial.exists() else 0
            # Unsafe partials without a strong entity validator are discarded.
            validator = meta.get('etag', '')
            if offset and (not validator or validator.startswith('W/') or meta.get('url') != url):
                partial.unlink(); offset = 0
            headers = {**auth}
            if offset:
                headers.update({'Range': f'bytes={offset}-', 'If-Range': validator})
            with self._request(url, headers=headers, delay=delay) as response:
                if response.is_redirect:
                    location = response.headers.get('location')
                    if not location:
                        raise CollectionError('redirect without location')
                    next_url = urljoin(url, location)
                    if origin(next_url) != origin(source.url):
                        raise CollectionError('cross-origin redirect requires a separately reviewed source')
                    url = next_url; continue
                if response.status_code not in (200, 206):
                    raise CollectionError(f'HTTP status {response.status_code}; stopped')
                if offset and response.status_code == 206:
                    content_range = response.headers.get('content-range', '')
                    if not content_range.startswith(f'bytes {offset}-') or response.headers.get('etag') != validator:
                        raise CollectionError('resume range/validator mismatch')
                elif response.status_code == 206:
                    raise CollectionError('unsolicited partial response')
                else:
                    offset = 0
                etag = response.headers.get('etag', '')
                atomic_json(meta_path, {'url': url, 'etag': etag})
                if offset + int(response.headers.get('content-length', '0')) > self.limits.max_download_bytes:
                    raise CollectionError('download byte quota exceeded')
                size = offset
                with partial.open('ab' if offset else 'wb') as f:
                    os.chmod(partial, 0o600)
                    for chunk in response.iter_raw(65536):
                        self.check_stop(); size += len(chunk)
                        if size > self.limits.max_download_bytes:
                            raise CollectionError('download byte quota exceeded')
                        self.disk_check(len(chunk)); f.write(chunk)
                    f.flush(); os.fsync(f.fileno())
                os.replace(partial, target)
                return target, url
        raise CollectionError('redirect limit exceeded')

    def collect(self, source: Source):
        self._validate_source(source)
        key = hashlib.sha256(json.dumps(asdict(source), sort_keys=True).encode()).hexdigest()
        with self.writer():
            with self.db() as db:
                prior = db.execute('SELECT state FROM jobs WHERE key=?', (key,)).fetchone()
                if prior and prior[0]=='complete':
                    return {'inserted': 0, 'state': 'complete', 'resumed': True}
                db.execute('INSERT OR IGNORE INTO jobs(key, source, state) VALUES (?,?,?)', (key, json.dumps(asdict(source)), 'pending'))
            path = self.root/'downloads'/f'{key}.data'
            try:
                if path.exists():
                    final_url = json.loads(path.with_suffix('.json').read_text())['url']
                else:
                    path, final_url = self._download(source, key)
                result = self._ingest(source, path, final_url)
                with self.db() as db:
                    db.execute('UPDATE jobs SET state=?,inserted=inserted+? WHERE key=?', ('complete', result['inserted'], key))
                path.unlink(missing_ok=True); path.with_suffix('.json').unlink(missing_ok=True)
                return result
            except (CollectionError, *INGEST_ERRORS) as exc:
                with self.db() as db:
                    db.execute('UPDATE jobs SET state=? WHERE key=?', ('stopped', key))
                if isinstance(exc, CollectionError): raise
                raise CollectionError('input parsing or local storage failed') from exc

    def ingest_file(self, source: Source, path: Path | str):
        """Ingest a locally downloaded/exported file without contacting any website."""
        self._validate_source(source)
        with self.writer():
            try:
                return self._ingest(source, Path(path), source.url)
            except INGEST_ERRORS as exc:
                raise CollectionError('input parsing or local storage failed') from exc

    def _open_input(self, path):
        f = path.open('rb'); magic = f.read(4); f.seek(0)
        if magic.startswith(b'\x1f\x8b'):
            f.close(); return gzip.open(path, 'rb')
        if magic.startswith(b'BZh'):
            f.close(); return bz2.open(path, 'rb')
        return f

    def _warc_rows(self, path, limit):
        """Every decompressed byte warcio pulls (WARC headers, HTTP headers, payload) is charged to
        max_parse_bytes by BoundedReader. While warcio parses the next record's headers the reader is in
        header mode: any line over WARC_HEADER_LINE_MAX or more than WARC_HEADER_BLOCK_MAX bytes
        (plus one 16 KiB warcio read-ahead block) is rejected, so a single huge header cannot be buffered."""
        parsed = count = 0
        with self._open_input(path) as raw_input:
            f = BoundedReader(raw_input, self.limits.max_parse_bytes, self.check_stop, 'WARC')
            f.header_line_max, f.header_block_max = WARC_HEADER_LINE_MAX, WARC_HEADER_BLOCK_MAX
            records = iter(ArchiveIterator(f))
            while True:
                self.check_stop()
                f.begin_headers()
                try:
                    record = next(records)
                except StopIteration:
                    if not count: raise CollectionError('no WARC records found')
                    break
                finally:
                    f.end_headers()
                count += 1
                cl = record.rec_headers.get_header('Content-Length')
                if not str(record.rec_headers.protocol or '').startswith('WARC/') or record.rec_type is None or not (cl or '').isascii() or not (cl or '').isdigit():
                    raise CollectionError('invalid WARC record header')
                stream = record.content_stream()
                kept, size = [], 0
                while True:
                    self.check_stop()
                    chunk = stream.read(min(WARC_CHUNK, self.limits.max_parse_bytes - parsed + 1))
                    if not chunk: break
                    parsed += len(chunk)
                    if parsed>self.limits.max_parse_bytes: raise CollectionError('expanded WARC byte quota exceeded')
                    if size <= limit:
                        kept.append(chunk); size += len(chunk)
                if getattr(record.raw_stream, 'limit', 0):
                    raise CollectionError('truncated WARC record')
                data = b''.join(kept)
                if record.rec_type != 'response' or not record.http_headers or record.http_headers.get_statuscode() != '200': continue
                if 'html' not in (record.http_headers.get_header('Content-Type') or ''): continue
                if len(data)>limit: raise CollectionError('WARC record byte quota exceeded')
                yield html_text(data), {'record_url': record.rec_headers.get_header('WARC-Target-URI'), 'warc_date': record.rec_headers.get_header('WARC-Date')}

    def _rows(self, source, path):
        limit = self.limits.max_record_bytes
        if source.format == 'parquet':
            parsed = 0
            import pyarrow.parquet as pq
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=64, columns=[source.text_field]):
                for row in batch.to_pylist():
                    text = row[source.text_field]
                    if not isinstance(text, str): raise CollectionError('Parquet text_field must contain strings')
                    parsed += len(text.encode('utf-8'))
                    if parsed>self.limits.max_parse_bytes: raise CollectionError('expanded Parquet byte quota exceeded')
                    yield text, {}
            return
        if source.format == 'commoncrawl':
            try:
                yield from self._warc_rows(path, limit)
            except CollectionError:
                raise
            except Exception as exc:  # warcio ArchiveLoadFailed, gzip/zlib/EOF/OS/value errors
                raise CollectionError(f'invalid WARC: {type(exc).__name__}') from exc
            return
        with self._open_input(path) as raw_input:
            f = BoundedReader(raw_input, self.limits.max_parse_bytes, self.check_stop)
            if source.format in ('html', 'text', 'arxiv'):
                data = f.read(limit+1)
                if len(data)>limit: raise CollectionError('record byte quota exceeded')
                if source.format=='html': yield html_text(data), {}
                elif source.format=='text': yield data.decode('utf-8'), {}
                else:
                    feed = ET.fromstring(data)
                    for entry in feed.findall('{http://www.w3.org/2005/Atom}entry'):
                        ns = '{http://www.w3.org/2005/Atom}'
                        title = entry.findtext(ns+'title', '')
                        summary = entry.findtext(ns+'summary', '')
                        yield title.strip()+'\n'+summary.strip(), {'record_url': entry.findtext(ns+'id'), 'title': title.strip()}
            elif source.format=='jsonl':
                while line := f.readline(limit+1):
                    self.check_stop()
                    if len(line)>limit: raise CollectionError('JSONL record byte quota exceeded')
                    if not line.strip(): continue
                    row = json.loads(line)
                    if not isinstance(row, dict): raise CollectionError('JSONL rows must be objects')
                    text = row[source.text_field]
                    if not isinstance(text, str): raise CollectionError('text_field must contain strings')
                    yield text, {'upstream_id': str(row.get('id', ''))}
            elif source.format=='wikipedia':
                # Clear completed pages to keep memory bounded by one XML page.
                # Reject DTD/entities before handing data to expat.
                root = None
                for event, element in ET.iterparse(f, events=('start', 'end'), forbid_dtd=True):
                    if root is None: root = element
                    if event != 'end': continue
                    self.check_stop()
                    if element.tag.rsplit('}',1)[-1]=='page':
                        child = lambda name: next((e for e in element if e.tag.rsplit('}',1)[-1]==name), None)
                        revision = child('revision'); title = child('title'); ident = child('id')
                        text = next((e.text or '' for e in revision if e.tag.rsplit('}',1)[-1]=='text'), '') if revision is not None else ''
                        yield text, {'title': title.text if title is not None else '', 'upstream_id': ident.text if ident is not None else ''}
                        element.clear()
                        if root is not element: root.clear()

    def _ingest(self, source, path, final_url):
        added = 0
        for text, extra in self._rows(source, path):
            self.check_stop()
            text = text.strip()
            if not text: continue
            raw = text.encode('utf-8')
            if len(raw)>self.limits.max_record_bytes: raise CollectionError('record byte quota exceeded')
            ident = hashlib.sha256(raw).hexdigest()
            provenance = {'url': source.url, 'final_url': final_url, 'dataset': source.dataset, 'format': source.format, 'collected_at': utcnow(), 'terms_url': source.terms_url, 'license': source.license, 'training_reviewed': source.training_reviewed, 'owner_account': source.owner_account, **extra}
            row = {'id': ident, 'text': text, 'license': source.license, 'training_eligible': bool(source.training_reviewed is True and license_training_eligible(source.license) and not source.owner_account and source.format!='commoncrawl'), 'provenance': provenance}
            body = json.dumps(row, ensure_ascii=False, sort_keys=True)
            size = len(body.encode('utf-8'))+1
            with self.db() as db:
                existing = db.execute('SELECT 1 FROM records WHERE id=?', (ident,)).fetchone()
                if not existing:
                    count, total = db.execute('SELECT count(*),coalesce(sum(bytes),0) FROM records').fetchone()
                    if count>=self.limits.max_records or total+size>self.limits.max_storage_bytes:
                        raise CollectionError('corpus quota exceeded; committed records retained for resume')
                    self.disk_check(size)
                    db.execute('INSERT INTO records VALUES (?,?,?)', (ident, body, size)); added += 1
                if existing and not row['training_eligible']:
                    prior_body = json.loads(db.execute('SELECT body FROM records WHERE id=?', (ident,)).fetchone()[0])
                    prior_body['training_eligible'] = False
                    db.execute('UPDATE records SET body=? WHERE id=?', (json.dumps(prior_body, ensure_ascii=False, sort_keys=True), ident))
                self.disk_check(len(json.dumps(provenance).encode('utf-8')))
                db.execute('INSERT OR REPLACE INTO provenance VALUES (?,?,?)', (ident, source.url, json.dumps(provenance, sort_keys=True)))
        return {'inserted': added, 'state': 'complete', 'resumed': False}

    def status(self):
        with self.db() as db:
            count, size = db.execute('SELECT count(*),coalesce(sum(bytes),0) FROM records').fetchone()
            jobs = dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state').fetchall())
        return {'records': count, 'record_bytes': size, 'jobs': jobs, 'stopped': (self.root/'STOP').exists(), 'limits': asdict(self.limits)}

    def export(self):
        """Versioned local snapshot, sha256 shards, atomic manifest pointer."""
        with self.writer():
            snapshot = self.root/'exports'/str(time.time_ns()); snapshot.mkdir(mode=0o700)
            shards = []; total = 0; output = None
            try:
                with self.db() as db:
                    for ident, body in db.execute('SELECT id,body FROM records ORDER BY id'):
                        self.check_stop()
                        if total%self.limits.shard_records==0:
                            if output: output.close()
                            shard = snapshot/f'part-{len(shards):06d}.jsonl'
                            output = shard.open('w', encoding='utf-8'); os.chmod(shard, 0o600)
                            shards.append({'path': str(shard.relative_to(self.root)), 'records': 0})
                        row = json.loads(body)
                        row['provenance_all'] = [json.loads(x[0]) for x in db.execute('SELECT metadata FROM provenance WHERE id=? ORDER BY source', (ident,))]
                        line = json.dumps(row, ensure_ascii=False, sort_keys=True)+'\n'
                        self.disk_check(len(line.encode('utf-8')))
                        output.write(line)
                        shards[-1]['records'] += 1; total += 1
                if output: output.close(); output = None
                for item in shards:
                    path = self.root/item['path']
                    digest = hashlib.sha256()
                    with path.open('rb') as f:
                        while chunk := f.read(1024*1024): digest.update(chunk)
                    item.update(sha256=digest.hexdigest(), bytes=path.stat().st_size)
                manifest = {'schema_version': 1, 'created_at': utcnow(), 'records': total, 'shards': shards, 'format': 'jsonl', 'training_filter': 'training_eligible == true', 'license_warning': 'Metadata is not a license grant. Review every source and rights before training.', 'limits': asdict(self.limits)}
                atomic_json(snapshot/'manifest.json', manifest)
                atomic_json(self.root/'manifest.json', manifest)
                return manifest
            finally:
                if output: output.close()
