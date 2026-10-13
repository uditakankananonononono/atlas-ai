"""S6.1 SQLite supplied company snapshots. No fetching or live watch loop.

Trusted host selects the database path; tenant/company identities scope each
transaction. Public-looking URLs are syntax checked, never source-authenticated.
Partial snapshots never infer deletion. Removal means missing from a supplied
complete snapshot, not proof the company removed anything on its public site.
"""
from datetime import date
import ipaddress
import json
import sqlite3
from urllib.parse import urlsplit
from app.modules.c30 import policy

_FORBIDDEN = {'send':'outreach','submit':'outreach','spend':'spend','scrape':'scrape',
              'trade':'trade','autopost':'autopost','fake_accounts':'fakeacct'}


def fail(reason):
    raise ValueError('INTEL_REFUSED_' + reason)


def text(value, field, cap):
    return policy.clean_text(value, 'INTEL', field, cap, allow_ws=field == 'text')


def record(value, fields, field, optional=()):
    if type(value) is not dict:
        fail('BAD_TYPE:' + field)
    if len(value) > 32:
        fail('OVERSIZE:' + field)
    for key in value:
        text(key, 'key', 128)
        rule = _FORBIDDEN.get(key.casefold().replace('-', '_'))
        if rule:
            policy.check(rule, 'INTEL')
    if set(value) - set(fields) - set(optional) or set(fields) - set(value):
        fail('BAD_SHAPE:' + field)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def safe_url(value):
    value = text(value, 'url', 2000)
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or not u.hostname or u.username or u.password
                or u.port not in (None,443) or u.hostname == 'localhost'
                or u.hostname.endswith(('.localhost','.local'))):
            fail('BAD_URL')
        try:
            ipaddress.ip_address(u.hostname)
        except ValueError:
            if '.' not in u.hostname or any(c.isspace() for c in u.hostname):
                fail('BAD_URL')
        else:
            fail('BAD_URL')  # no IP-literal company source URLs
    except ValueError:
        fail('BAD_URL')
    return value


class CompanyMonitor:
    """Host-only path injection, schema initialization and SQLite transactions.

    Snapshot ledger preserves all reports; history reads are bounded. Host
    must handle retention/storage quotas, backups and filesystem authority.
    No HTTP constructor, caller-chosen path API, fetcher or notifier exists.
    """
    def __init__(self, path, *, tenant_id):
        self.tenant_id = text(tenant_id, 'tenant_id', 128)
        self._db = sqlite3.connect(path, timeout=10)
        self._db.execute('PRAGMA busy_timeout=10000')
        self._db.execute('''CREATE TABLE IF NOT EXISTS company_monitor_state (
            tenant TEXT NOT NULL, company TEXT NOT NULL, as_of TEXT NOT NULL,
            revision INTEGER NOT NULL, records TEXT NOT NULL,
            PRIMARY KEY (tenant, company))''')
        self._db.execute('''CREATE TABLE IF NOT EXISTS company_monitor_history (
            tenant TEXT NOT NULL, company TEXT NOT NULL, revision INTEGER NOT NULL,
            report TEXT NOT NULL, PRIMARY KEY (tenant, company, revision))''')
        self._db.commit()

    def close(self):
        self._db.close()

    def record(self, snapshot):
        record(snapshot, ('company_id','as_of','snapshot_complete','records'), 'snapshot', ('allow_empty_complete',))
        company = text(snapshot['company_id'], 'company_id', 128)
        as_of = text(snapshot['as_of'], 'as_of', 10)
        try:
            if len(as_of) != 10 or date.fromisoformat(as_of).isoformat() != as_of:
                fail('BAD_DATE')
        except ValueError:
            fail('BAD_DATE')
        complete = snapshot['snapshot_complete']
        if type(complete) is not bool:
            fail('BAD_TYPE:snapshot_complete')
        ack = snapshot.get('allow_empty_complete', False)
        if type(ack) is not bool:
            fail('BAD_TYPE:allow_empty_complete')
        rows = snapshot['records']
        if type(rows) is not list:
            fail('BAD_TYPE:records')
        if complete and not rows and not ack:
            fail('EMPTY_COMPLETE')
        if len(rows) > 1000:
            fail('OVERSIZE:records')
        supplied, total = {}, 0
        for row in rows:
            record(row, ('id','kind','url','title','text'), 'record')
            iid = text(row['id'], 'record_id', 128)
            kind = text(row['kind'], 'kind', 32)
            if kind not in ('filing','press','repository'):
                fail('BAD_KIND')
            normalized = {'id':iid,'kind':kind,'url':safe_url(row['url']),
                          'title':text(row['title'], 'title', 500),
                          'text':text(row['text'], 'text', 10000)}
            total += len(normalized['text'])
            if total > 1000000:
                fail('OVERSIZE:total_text')
            if iid in supplied:
                fail('DUPLICATE:record_id')
            supplied[iid] = normalized
        # Entire payload admitted before any write or transaction.
        self._db.execute('BEGIN IMMEDIATE')
        try:
            old = self._db.execute('SELECT as_of, revision, records FROM company_monitor_state WHERE tenant=? AND company=?',
                                   (self.tenant_id,company)).fetchone()
            if old and as_of < old[0]:
                fail('STALE_SNAPSHOT')
            before = json.loads(old[2]) if old else {}
            revision = old[1]+1 if old else 1
            added = [supplied[i] for i in sorted(set(supplied)-set(before))]
            changed = [{'id':i,'before':before[i],'after':supplied[i]} for i in sorted(set(supplied)&set(before))
                       if supplied[i] != before[i]]
            unchanged = [i for i in sorted(set(supplied)&set(before)) if supplied[i] == before[i]]
            absent = sorted(set(before)-set(supplied))
            removed = [before[i] for i in absent] if complete else []
            merged = supplied if complete else {**before,**supplied}
            result = {'company_id':company,'as_of':as_of,'revision':revision,
                      'snapshot_complete':complete,'empty_complete_acknowledged':complete and not supplied and ack,'added':added,'changed':changed,'removed':removed,
                      'unchanged_ids':unchanged,'not_observed_ids':[] if complete else absent,
                      'coverage':{'supplied_records':len(supplied),'added':len(added),'changed':len(changed),
                                  'removed':len(removed),'unchanged':len(unchanged)},
                      'source_authentication':'unverified_supplied',
                      'summary':{'basis':'exact supplied field differences, not semantic significance',
                                 'added_ids':[r['id'] for r in added],'changed_ids':[r['id'] for r in changed],
                                 'removed_ids':[r['id'] for r in removed]},
                      'scope':policy.scope(['durable supplied company-record snapshots and exact diffs'],
                          ['fetching','live monitoring','source authentication','semantic significance','notifications','routes'],
                          'supplied unverified records',as_of)}
            self._db.execute('INSERT INTO company_monitor_state VALUES (?,?,?,?,?) ON CONFLICT(tenant,company) DO UPDATE SET as_of=excluded.as_of,revision=excluded.revision,records=excluded.records',
                             (self.tenant_id,company,as_of,revision,encode(merged)))
            self._db.execute('INSERT INTO company_monitor_history VALUES (?,?,?,?)',
                             (self.tenant_id,company,revision,encode(result)))
            self._db.commit()
            return json.loads(encode(result))
        except BaseException:
            self._db.rollback()
            raise

    def current(self, company_id):
        company = text(company_id, 'company_id', 128)
        row = self._db.execute('SELECT as_of,revision,records FROM company_monitor_state WHERE tenant=? AND company=?',
                               (self.tenant_id,company)).fetchone()
        if row is None:
            return None
        records = json.loads(row[2])
        return {'company_id':company,'as_of':row[0],'revision':row[1],
                'records':[records[i] for i in sorted(records)]}

    def history(self, company_id, *, limit=50):
        company = text(company_id, 'company_id', 128)
        if type(limit) is not int or not 1 <= limit <= 1000:
            fail('BAD_TYPE:limit')
        # One query snapshot: count and selected reports cannot drift between reads.
        rows = self._db.execute('SELECT report,count(*) OVER () FROM company_monitor_history WHERE tenant=? AND company=? ORDER BY revision DESC LIMIT ?',
                                (self.tenant_id,company,limit)).fetchall()
        count = rows[0][1] if rows else 0
        return {'company_id':company,'revisions':count,'items':[json.loads(r[0]) for r in rows],
                'truncated':count>limit}
