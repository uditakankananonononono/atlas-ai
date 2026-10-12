"""Private local SQLite persistence for the bounded C2 engine."""
import json
import os
from pathlib import Path
import sqlite3
from .launch_quiz_c2 import LaunchQuiz, QuizError, shared_policy_hook

UNAVAILABLE = 'FLEET_REFUSED_STORAGE'


class DurableLaunchQuiz:
    """One SQLite transaction per operation, including reads and owner checks."""
    def __init__(self, filename):
        self.path = Path(filename)
        try:
            p = self.path
            if (not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents))
                    or not p.parent.is_dir() or p.parent.stat().st_mode & 0o077):
                raise ValueError()
            fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                st = os.fstat(fd)
                import stat
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o077:
                    raise ValueError()
            finally:
                os.close(fd)
            with self._connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
                db.execute('INSERT OR IGNORE INTO state VALUES (1, ?)', ('{"sequence":0,"sessions":{}}',))
        except (OSError, ValueError, sqlite3.Error):
            raise QuizError(UNAVAILABLE) from None

    def _connect(self):
        import stat
        p = self.path
        st = p.lstat()
        if (any(x.is_symlink() for x in (p, *p.parents)) or not stat.S_ISREG(st.st_mode)
                or st.st_nlink != 1 or st.st_mode & 0o077 or p.parent.stat().st_mode & 0o077):
            raise ValueError()
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute('PRAGMA secure_delete=ON')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def _call(self, operation, *args, **kwargs):
        db = None
        try:
            db = self._connect()
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT length(CAST(body AS BLOB)) FROM state WHERE id=1').fetchone()
            if row is None or not 0 < row[0] <= 25_000_000:
                raise ValueError()
            state = json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
            if (type(state) is not dict or set(state) != {'sequence', 'sessions'}
                    or type(state['sequence']) is not int or state['sequence'] < 0
                    or type(state['sessions']) is not dict or len(state['sessions']) > 100):
                raise ValueError()
            engine = LaunchQuiz(policy_hook=shared_policy_hook)
            engine._sessions = state['sessions']
            engine._sequence = state['sequence']
            result = getattr(engine, operation)(*args, **kwargs)
            body = json.dumps({'sequence': engine._sequence, 'sessions': engine._sessions}, ensure_ascii=True)
            if len(body.encode()) > 25_000_000:
                raise ValueError()
            db.execute('UPDATE state SET body=? WHERE id=1', (body,))
            db.execute('COMMIT')
            if isinstance(result, dict) and 'scope' in result:
                scope = result['scope']
                scope['not_implemented'].remove('durable storage')
                scope['implemented'].append('private local SQLite persistence')
            return result
        except QuizError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, AttributeError):
            raise QuizError(UNAVAILABLE) from None
        finally:
            if db is not None:
                db.close()  # an uncommitted transaction rolls back

    def __getattr__(self, name):
        if name not in {'start', 'answer', 'documents', 'edit', 'plan', 'delete', 'revoke', 'profile'}:
            raise AttributeError(name)
        return lambda *args, **kwargs: self._call(name, *args, **kwargs)
