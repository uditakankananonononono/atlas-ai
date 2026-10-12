"""Durable private computation jobs for Claire's merged runtime.

Claim is transactional across instances. Expired running work becomes unknown,
never silently retried: a previous worker may already have acted. No adapters,
network calls, file tools or approval-consuming actions are executed here.
"""
from contextlib import contextmanager
import json
import math
import sqlite3
import time
import uuid


def _json(value):
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(body)>2_000_000:raise ValueError('job payload/result limit')
    return body


def _identifier(value):
    if type(value) is not str or not value.strip() or len(value)>200:raise ValueError('identifier required')
    return value


class DurableJobs:
    def __init__(self,path,tenant,actor,clock=time.time):
        self.path=path;self.tenant=_identifier(tenant);self.actor=_identifier(actor);self.clock=clock
        with self._db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS claire_private_jobs (
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL,
              task TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
              worker TEXT, lease_until REAL, version INTEGER NOT NULL,
              result TEXT, error TEXT, created REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS claire_private_job_owner ON claire_private_jobs(tenant,actor,status);
              CREATE TABLE IF NOT EXISTS claire_private_job_events (
              id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, kind TEXT NOT NULL,
              version INTEGER NOT NULL, observed REAL NOT NULL);''')
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def _now(self):
        value=self.clock()
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite clock required')
        return value
    def enqueue(self,task,payload):
        if task not in {'polynomial','strategy','enclosure','patent_prepare','admissions_topic_train'}:
            raise ValueError('private computation task not supported')
        ident=uuid.uuid4().hex;body=_json(payload);now=self._now()
        with self._db() as db:
            db.execute('INSERT INTO claire_private_jobs VALUES (?,?,?,?,?,?,NULL,NULL,1,NULL,NULL,?)',
                       (ident,self.tenant,self.actor,task,body,'queued',now))
            db.execute('INSERT INTO claire_private_job_events(job_id,kind,version,observed) VALUES (?,?,1,?)',(ident,'queued',now))
        return ident
    def claim(self,worker,lease_seconds=60):
        _identifier(worker)
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:raise ValueError('lease_seconds must be 1..3600')
        now=self._now()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            expired=db.execute('SELECT id,version FROM claire_private_jobs WHERE tenant=? AND actor=? AND status=? AND lease_until<=?',(self.tenant,self.actor,'running',now)).fetchall()
            for row in expired:
                db.execute('UPDATE claire_private_jobs SET status=?,version=version+1,error=? WHERE id=?',('unknown','worker lease expired; outcome not proven',row['id']))
                db.execute('INSERT INTO claire_private_job_events(job_id,kind,version,observed) VALUES (?,?,?,?)',(row['id'],'unknown',row['version']+1,now))
            row=db.execute('SELECT * FROM claire_private_jobs WHERE tenant=? AND actor=? AND status=? ORDER BY created,id LIMIT 1',(self.tenant,self.actor,'queued')).fetchone()
            if row is None:return None
            db.execute('UPDATE claire_private_jobs SET status=?,worker=?,lease_until=?,version=version+1 WHERE id=?',('running',worker,now+lease_seconds,row['id']))
            db.execute('INSERT INTO claire_private_job_events(job_id,kind,version,observed) VALUES (?,?,?,?)',(row['id'],'running',row['version']+1,now))
            return dict(row)|{'status':'running','worker':worker,'version':row['version']+1,'lease_until':now+lease_seconds,'payload':json.loads(row['payload'])}
    def finish(self,ident,worker,version,result):
        body=_json(result);now=self._now()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            cursor=db.execute('UPDATE claire_private_jobs SET status=?,result=?,version=version+1 WHERE id=? AND tenant=? AND actor=? AND status=? AND worker=? AND version=? AND lease_until>?',
                              ('done',body,ident,self.tenant,self.actor,'running',worker,version,now))
            if cursor.rowcount!=1:raise ValueError('stale, expired, unknown or unowned job')
            db.execute('INSERT INTO claire_private_job_events(job_id,kind,version,observed) VALUES (?,?,?,?)',(ident,'done',version+1,now))
    def get(self,ident):
        with self._db() as db:
            row=db.execute('SELECT * FROM claire_private_jobs WHERE id=? AND tenant=? AND actor=?',(ident,self.tenant,self.actor)).fetchone()
            if row is None:raise KeyError('job not found')
            result=dict(row);result['payload']=json.loads(result['payload']);result['result']=json.loads(result['result']) if result['result'] else None
            result['events']=[dict(e) for e in db.execute('SELECT kind,version,observed FROM claire_private_job_events WHERE job_id=? ORDER BY id',(ident,))]
            return result
