"""Tenant-scoped durable reports. Explicit database path; no global latest report."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from .policy import Refusal, text

class ReportStore:
    def __init__(self,path):
        self.path=path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS venture_reports (tenant TEXT NOT NULL, unit TEXT NOT NULL, run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, report TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS venture_tenant_unit ON venture_reports (tenant, unit, created_at)')

    def save(self,tenant,unit,report):
        text(tenant); text(unit); rid=str(uuid4()); created=datetime.now(timezone.utc).isoformat()
        report=dict(report,run_id=rid,created_at=created)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO venture_reports VALUES (?,?,?,?,?)',(tenant,unit,rid,created,json.dumps(report,allow_nan=False)))
        return report

    def get(self,tenant,unit,run_id=None):
        text(tenant); text(unit)
        with sqlite3.connect(self.path) as db:
            if run_id:
                row=db.execute('SELECT report FROM venture_reports WHERE tenant=? AND unit=? AND run_id=?',(tenant,unit,run_id)).fetchone()
            else:
                row=db.execute('SELECT report FROM venture_reports WHERE tenant=? AND unit=? ORDER BY created_at DESC, run_id DESC LIMIT 1',(tenant,unit)).fetchone()
        if row is None: raise KeyError('report not found')
        return json.loads(row[0])
