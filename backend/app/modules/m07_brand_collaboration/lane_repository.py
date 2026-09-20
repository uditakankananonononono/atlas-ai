from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from threading import RLock
from typing import Sequence

from .lane_models import Campaign, CampaignEvent, CampaignStatus, Deliverable, Evidence, EvidenceKind


class BrandCollaborationRepository:
    """SQLite persistence. Caller owns connection lifecycle."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._lock = RLock()

    def migrate(self) -> None:
        with self._lock, self.connection:
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS m07_evidence (
              id TEXT PRIMARY KEY, brand_name TEXT NOT NULL, kind TEXT NOT NULL,
              source_url TEXT NOT NULL, claim TEXT NOT NULL, excerpt TEXT NOT NULL,
              observed_at TEXT NOT NULL, confidence REAL NOT NULL,
              metadata_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_m07_evidence_brand ON m07_evidence(brand_name);
            CREATE TABLE IF NOT EXISTS m07_campaigns (
              id TEXT PRIMARY KEY, brand_name TEXT NOT NULL, title TEXT NOT NULL,
              status TEXT NOT NULL, currency TEXT NOT NULL, agreed_fee_minor INTEGER NOT NULL,
              start_at TEXT, due_at TEXT, payment_due_at TEXT, deliverables_json TEXT NOT NULL,
              owner TEXT, notes TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_m07_campaign_status ON m07_campaigns(status);
            CREATE TABLE IF NOT EXISTS m07_campaign_events (
              id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES m07_campaigns(id) ON DELETE CASCADE,
              kind TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_m07_events_campaign ON m07_campaign_events(campaign_id, occurred_at);
            """)

    def save_evidence(self, item: Evidence) -> None:
        with self._lock, self.connection:
            self.connection.execute("""INSERT OR REPLACE INTO m07_evidence
            (id,brand_name,kind,source_url,claim,excerpt,observed_at,confidence,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?)""", (item.id,item.brand_name,item.kind.value,item.source_url,item.claim,item.excerpt,item.observed_at.isoformat(),item.confidence,json.dumps(dict(item.metadata), sort_keys=True)))

    def list_evidence(self, brand_name: str) -> list[Evidence]:
        rows = self.connection.execute("SELECT * FROM m07_evidence WHERE brand_name=? ORDER BY observed_at DESC", (brand_name,)).fetchall()
        return [Evidence(r["id"],r["brand_name"],EvidenceKind(r["kind"]),r["source_url"],r["claim"],r["excerpt"],datetime.fromisoformat(r["observed_at"]),r["confidence"],json.loads(r["metadata_json"])) for r in rows]

    def save_campaign(self, item: Campaign) -> None:
        deliverables = [asdict(d) for d in item.deliverables]
        with self._lock, self.connection:
            self.connection.execute("""INSERT OR REPLACE INTO m07_campaigns
            (id,brand_name,title,status,currency,agreed_fee_minor,start_at,due_at,payment_due_at,deliverables_json,owner,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (item.id,item.brand_name,item.title,item.status.value,item.currency,item.agreed_fee_minor,
            item.start_at.isoformat() if item.start_at else None,item.due_at.isoformat() if item.due_at else None,item.payment_due_at.isoformat() if item.payment_due_at else None,
            json.dumps(deliverables, sort_keys=True),item.owner,item.notes,item.created_at.isoformat(),item.updated_at.isoformat()))

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        r = self.connection.execute("SELECT * FROM m07_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not r: return None
        dt = lambda value: datetime.fromisoformat(value) if value else None
        return Campaign(r["id"],r["brand_name"],r["title"],CampaignStatus(r["status"]),r["currency"],r["agreed_fee_minor"],dt(r["start_at"]),dt(r["due_at"]),dt(r["payment_due_at"]),tuple(Deliverable(**x) for x in json.loads(r["deliverables_json"])),r["owner"],r["notes"],dt(r["created_at"]),dt(r["updated_at"]))

    def save_event(self, item: CampaignEvent) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO m07_campaign_events VALUES (?,?,?,?,?)", (item.id,item.campaign_id,item.kind,item.occurred_at.isoformat(),json.dumps(dict(item.payload), sort_keys=True)))

    def list_events(self, campaign_id: str) -> list[CampaignEvent]:
        rows = self.connection.execute("SELECT * FROM m07_campaign_events WHERE campaign_id=? ORDER BY occurred_at,id", (campaign_id,)).fetchall()
        return [CampaignEvent(r["id"],r["campaign_id"],r["kind"],datetime.fromisoformat(r["occurred_at"]),json.loads(r["payload_json"])) for r in rows]
