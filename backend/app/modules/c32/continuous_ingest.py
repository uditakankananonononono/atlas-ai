"""Supplied JSONL ingestion with transactional disk-backed checkpoints/dedupe.

One local worker at a time. Every batch commits counts, hashes and byte offset
in the same SQLite transaction. The JSON state file is a diagnostic mirror,
not the recovery authority. No fetching, scheduling or live-source integration.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
import time

PREFIX = 'INGEST'
MAX_BATCH = 10000
MAX_LINE = 100000  # bytes, including newline
MAX_PENDING_REPORT = 1000
MAX_LEGACY_BYTES = 8 * 1024 * 1024
STATE_VERSION = 2
MAX_FINGERPRINT = 8 * 1024 * 1024


def _err(code, detail=None):
    raise ValueError('%s_REFUSED_%s%s' % (PREFIX, code, ':' + detail if detail else ''))


def _record_hash(line):
    return hashlib.sha256(line.encode('utf-8')).hexdigest()


def _fingerprint(stream, length):
    """Streaming hash, at most 8 MiB, with bounded 64 KiB transient chunks."""
    position = stream.tell()
    stream.seek(0)
    remaining = min(length, MAX_FINGERPRINT)
    digest = hashlib.sha256()
    try:
        while remaining:
            chunk = stream.read(min(remaining, 65536))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
        return digest.hexdigest()
    finally:
        stream.seek(position)


def _save_state(state_path, state):
    """Atomic diagnostic mirror. Recovery always uses the SQLite transaction."""
    fd, tmp = tempfile.mkstemp(prefix='.ingest-', dir=os.path.dirname(os.path.abspath(state_path)))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, state_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def _database(state_path):
    # This lock covers initialization and the whole run, including mirrors.
    lock_path = state_path + '.lock'
    db_path = state_path + '.sqlite3'
    for path in (state_path, lock_path, db_path):
        if os.path.islink(path):
            _err('PATH', 'symlink')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    conn = None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _err('BUSY')
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('PRAGMA cache_size=-2048')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS files (
                name TEXT PRIMARY KEY, device INTEGER, inode INTEGER,
                offset INTEGER NOT NULL, done INTEGER NOT NULL,
                size INTEGER, mtime_ns INTEGER, prefix_hash TEXT);
            CREATE TABLE IF NOT EXISTS quarantine (
                name TEXT PRIMARY KEY, device INTEGER, inode INTEGER,
                size INTEGER, mtime_ns INTEGER, reason TEXT);
            CREATE TABLE IF NOT EXISTS ledger (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), runs INTEGER,
                records_ingested INTEGER, records_deduped INTEGER,
                bytes_ingested INTEGER, elapsed_s REAL);
        ''')
        if conn.execute('SELECT 1 FROM ledger').fetchone() is None:
            _migrate(conn, state_path)
        yield conn
    finally:
        if conn is not None:
            conn.close()
        os.close(fd)


def _migrate(conn, state_path):
    """Import bounded legacy JSON once; malformed/oversized state fails closed."""
    old = None
    if os.path.exists(state_path):
        with open(state_path, 'rb') as stream:
            raw = stream.read(MAX_LEGACY_BYTES + 1)
        if len(raw) > MAX_LEGACY_BYTES:
            _err('OVERSIZE', 'legacy_state')
        try:
            old = json.loads(raw)
        except (ValueError, UnicodeError):
            _err('STATE')
        if type(old) is not dict or old.get('version') != 1:
            _err('STATE')
    ledger = (old or {}).get('ledger', {})
    keys = ('runs', 'records_ingested', 'records_deduped', 'bytes_ingested')
    values = [ledger.get(k, 0) for k in keys]
    elapsed = ledger.get('elapsed_s', 0.0)
    if any(type(x) is not int or x < 0 for x in values) or type(elapsed) not in (int, float) or not 0 <= elapsed < 1e100:
        _err('STATE')
    seen = (old or {}).get('seen', [])
    files = (old or {}).get('files', {})
    if type(seen) is not list or type(files) is not dict:
        _err('STATE')
    if any(type(h) is not str or len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in seen):
        _err('STATE')
    with conn:
        conn.execute('INSERT INTO ledger VALUES (1,?,?,?,?,?)', (*values, elapsed))
        conn.executemany('INSERT OR IGNORE INTO seen VALUES (?)', ((h,) for h in seen))
        for name, state in files.items():
            if type(name) is not str or type(state) is not dict or type(state.get('offset')) is not int or state['offset'] < 0:
                _err('STATE')
            # Legacy text-mode offsets are compatible for these UTF-8 newline files.
            conn.execute('INSERT INTO files VALUES (?,NULL,NULL,?,?,NULL,NULL,NULL)',
                         (name, state['offset'], int(bool(state.get('done')))))


def _ledger(conn):
    row = conn.execute('SELECT runs,records_ingested,records_deduped,bytes_ingested,elapsed_s FROM ledger').fetchone()
    return dict(zip(('runs', 'records_ingested', 'records_deduped', 'bytes_ingested', 'elapsed_s'), row))


def _mirror(conn, state_path, pending):
    files = {}
    for name in pending:
        row = conn.execute('SELECT offset,done FROM files WHERE name=?', (name,)).fetchone()
        if row:
            files[name] = {'offset': row[0], 'done': bool(row[1])}
    _save_state(state_path, {'version': STATE_VERSION, 'files': files,
                            'ledger': _ledger(conn),
                            'dedupe_count': conn.execute('SELECT count(*) FROM seen').fetchone()[0],
                            'recovery_authority': 'sqlite3 sidecar'})


def _commit(conn, name, stat, offset, done, batch, byte_count, prefix_hash, poison=False):
    counts = {'records': 0, 'deduped': 0, 'malformed': 0, 'bytes': byte_count}
    with conn:
        for line in batch:
            try:
                text = line.decode('utf-8').strip()
                if not text:
                    continue
                json.loads(text)
            except (ValueError, UnicodeError):
                counts['malformed'] += 1
                continue
            inserted = conn.execute('INSERT OR IGNORE INTO seen VALUES (?)', (_record_hash(text),)).rowcount
            counts['records' if inserted else 'deduped'] += 1
        conn.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?)',
                     (name, stat.st_dev, stat.st_ino, offset, int(done), stat.st_size, stat.st_mtime_ns, prefix_hash))
        conn.execute('UPDATE ledger SET records_ingested=records_ingested+?, records_deduped=records_deduped+?, bytes_ingested=bytes_ingested+? WHERE singleton=1',
                     (counts['records'], counts['deduped'], byte_count))
        if poison:
            conn.execute('INSERT OR REPLACE INTO quarantine VALUES (?,?,?,?,?,?)',
                         (name, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                          'INGEST_REFUSED_OVERSIZE:line'))
        else:
            conn.execute('DELETE FROM quarantine WHERE name=?', (name,))
    return counts


def run(inbox_dir, state_path, batch_size=1000, max_pending=64,
        max_files_per_run=None, clock=None):
    """Drain bounded supplied-file batches. SQLite sidecar must stay with state.

    Partial final lines wait for a newline. Changed completed files are reopened;
    replacement/truncation restarts at zero, preserving content dedupe. Same-inode
    same-size same-mtime edits and in-place rewrites of an active prefix are not
    detected outside the first 8 MiB. Inputs must be append-only until completed, then immutable except
    append/replacement/truncation. Symlink inputs are refused. Local Linux only.
    """
    if type(inbox_dir) is not str or not os.path.isdir(inbox_dir) or os.path.islink(inbox_dir):
        _err('PATH', 'inbox')
    if type(state_path) is not str or not state_path:
        _err('PATH', 'state')
    for value, label, cap in ((batch_size, 'batch_size', MAX_BATCH), (max_pending, 'max_pending', MAX_PENDING_REPORT)):
        if type(value) is not int or not 1 <= value <= cap:
            _err('BAD_TYPE', label)
    if max_files_per_run is not None and (type(max_files_per_run) is not int or max_files_per_run < 1):
        _err('BAD_TYPE', 'max_files_per_run')
    clock = clock or time.monotonic
    pending = []
    with os.scandir(inbox_dir) as entries:
        for entry in entries:
            if entry.name.endswith('.jsonl'):
                if len(pending) >= MAX_PENDING_REPORT:
                    _err('OVERSIZE', 'pending')
                if not entry.is_file(follow_symlinks=False):
                    _err('PATH', 'input')
                pending.append(entry.name)
    pending.sort()
    stats = {'files_completed': 0, 'files_touched': 0, 'records': 0, 'deduped': 0,
             'bytes': 0, 'malformed': 0, 'resumed_files': 0}
    with _database(state_path) as conn:
        started = clock()
        processed = 0
        for name in pending:
            path = os.path.join(inbox_dir, name)
            stat = os.stat(path, follow_symlinks=False)
            prior = conn.execute('SELECT device,inode,offset,done,size,mtime_ns,prefix_hash FROM files WHERE name=?', (name,)).fetchone()
            if prior and prior[3] and (prior[0], prior[1], prior[4]) == (stat.st_dev, stat.st_ino, stat.st_size):
                if prior[5] == stat.st_mtime_ns:
                    continue
                # mtime-only touch is free of duplicate recount; small-file
                # fingerprints cover all bytes, larger files only 8 MiB.
                probe_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(probe_fd, 'rb') as probe:
                    actual = os.fstat(probe.fileno())
                    if (actual.st_dev, actual.st_ino) != (stat.st_dev, stat.st_ino):
                        _err('PATH', 'changed_input')
                    fingerprint = _fingerprint(probe, prior[2])
                if prior[6] is not None and fingerprint == prior[6]:
                    with conn:
                        conn.execute('UPDATE files SET mtime_ns=? WHERE name=?', (stat.st_mtime_ns, name))
                    continue
            held = conn.execute('SELECT device,inode,size,mtime_ns FROM quarantine WHERE name=?', (name,)).fetchone()
            if held == (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
                continue
            if max_files_per_run is not None and processed >= max_files_per_run:
                break
            processed += 1
            offset = prior[2] if prior else 0
            replaced = prior and prior[0] is not None and (prior[0], prior[1]) != (stat.st_dev, stat.st_ino)
            # A same-size changed completed file may have been overwritten.
            overwritten = prior and prior[3] and stat.st_size <= offset
            if replaced or overwritten or stat.st_size < offset:
                offset = 0
            stats['resumed_files'] += int(bool(offset))
            stats['files_touched'] += 1
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                actual = os.fstat(stream.fileno())
                if (actual.st_dev, actual.st_ino) != (stat.st_dev, stat.st_ino):
                    _err('PATH', 'changed_input')
                if prior and offset and prior[6] is not None:
                    fingerprint = _fingerprint(stream, offset)
                    if fingerprint != prior[6]:
                        offset = 0
                def prefix_hash():
                    position = stream.tell()
                    stream.seek(0)
                    fingerprint = _fingerprint(stream, offset)
                    stream.seek(position)
                    return fingerprint
                stream.seek(offset)
                batch, byte_count = [], 0
                done = False
                poison = False
                while True:
                    line = stream.readline(MAX_LINE + 1)
                    if len(line) > MAX_LINE:
                        poison = True
                        break
                    if not line:
                        done = True
                        break
                    if not line.endswith(b'\n'):
                        break  # Do not checkpoint an incomplete final record.
                    offset = stream.tell()
                    byte_count += len(line)
                    batch.append(line)
                    if len(batch) >= batch_size:
                        changes = _commit(conn, name, stat, offset, False, batch, byte_count, prefix_hash())
                        for k, v in changes.items():
                            stats[k] += v
                        _mirror(conn, state_path, pending)
                        batch, byte_count = [], 0
                changes = _commit(conn, name, stat, offset, done, batch, byte_count, prefix_hash(), poison=poison)
                for k, v in changes.items():
                    stats[k] += v
                _mirror(conn, state_path, pending)
                stats['files_completed'] += int(done)
        elapsed = max(0.0, clock() - started)
        with conn:
            conn.execute('UPDATE ledger SET runs=runs+1, elapsed_s=elapsed_s+? WHERE singleton=1', (elapsed,))
        _mirror(conn, state_path, pending)
        ledger = _ledger(conn)
        quarantined = []
        for name in pending:
            held = conn.execute('SELECT reason FROM quarantine WHERE name=?', (name,)).fetchone()
            if held:
                quarantined.append({'file': name, 'reason': held[0]})
        pending_after = sum(not (row and row[0]) for name in pending
                            for row in [conn.execute('SELECT done FROM files WHERE name=?', (name,)).fetchone()])
    ledger['records_per_s'] = round(ledger['records_ingested'] / ledger['elapsed_s'], 1) if ledger['elapsed_s'] > 0 else None
    ledger['mb_per_s'] = round(ledger['bytes_ingested'] / ledger['elapsed_s'] / 1e6, 3) if ledger['elapsed_s'] > 0 else None
    return {'run': stats, 'backpressure': len(pending) > max_pending,
            'pending_before': len(pending), 'pending_after': pending_after, 'quarantined': quarantined,
            'cumulative': ledger,
            'memory_bound': 'one batch (%d records) in memory; SQLite cache 2 MiB; up to %d current filenames' % (batch_size, MAX_PENDING_REPORT),
            'limits': ['Supplied append-only JSONL files only; nothing fetched or scheduled.',
                       'Single local Linux worker; SQLite sidecar is required for recovery.',
                       'Dedupe hashes and historical file checkpoints stay on disk; disk use grows.',
                       'Each line is bounded to 100000 bytes including newline; partial lines await completion.',
                       'Oversize-line files are quarantined until stat metadata changes; later files continue. Good prefixes commit without consuming the poison line.',
                       'Throughput excludes time lost before a crash; committed record/byte counts survive.',
                       'Only the first 8 MiB of an active prefix are fingerprinted; other in-place edits and same-size same-mtime rewrites are not detected; changed mtime checks only the first 8 MiB (entire file when at most 8 MiB).',
                       'Legacy state migration is capped at 8 MiB; larger archives require a separate migration.']}
