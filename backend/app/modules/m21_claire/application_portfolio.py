"""Tenant-scoped application and competition portfolio.

This module prepares reviewable application packets from explicitly supplied facts
and listings. It never submits forms, emails people, pays fees, or fabricates user
achievements. Listing/profile facts remain marked as user/provider supplied, not
independently verified.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse
from uuid import uuid4


STATUSES = {
    "discovered", "researching", "preparing", "needs_user_review",
    "user_approved_to_submit", "submitted_confirmed", "decision_received", "archived"
}
TRANSITIONS = {
    "discovered": {"researching", "archived"},
    "researching": {"preparing", "discovered", "archived"},
    "preparing": {"needs_user_review", "researching", "archived"},
    "needs_user_review": {"preparing", "user_approved_to_submit", "archived"},
    "user_approved_to_submit": {"preparing", "submitted_confirmed", "archived"},
    "submitted_confirmed": {"decision_received", "archived"},
    "decision_received": {"archived"},
    "archived": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        p = urlparse(value.strip())
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def _safe_list(value: Any, *, max_items: int = 500) -> list[Any]:
    return list(value[:max_items]) if isinstance(value, list) else []


def build_application_packet(profile: dict[str, Any], listing: dict[str, Any], *, notes: str = "") -> dict[str, Any]:
    """Build a readiness report and truthful drafting scaffold from explicit inputs."""
    title = str(listing.get("title", "")).strip()
    url = str(listing.get("official_url", "")).strip()
    if not title or not _https_url(url):
        raise ValueError("listing must include a title and official HTTPS URL")
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")

    supplied_fields = {str(k) for k, v in profile.items() if v not in (None, "", [], {})}
    explicitly_required = [str(x) for x in _safe_list(listing.get("required_profile_fields"), max_items=100)]
    missing_fields = sorted(set(explicitly_required) - supplied_fields)

    eligibility = {}
    criteria = listing.get("eligibility", {})
    if not isinstance(criteria, dict):
        criteria = {}
    for criterion, profile_key in (
        ("country", "country"), ("age", "age"), ("grade", "school_level"),
        ("citizenship", "citizenship"), ("financial_aid_need", "financial_aid_need"),
        ("test_policy", "testing"),
    ):
        required = criteria.get(criterion)
        actual = profile.get(profile_key)
        if required in (None, "", [], {}) or actual in (None, "", [], {}):
            state = "unknown"
        elif isinstance(required, list):
            actual_values = actual if isinstance(actual, list) else [actual]
            state = "matches_supplied_criteria" if any(str(v).lower() in {str(r).lower() for r in required} for v in actual_values) else "conflict_check_required"
        elif isinstance(required, dict):
            state = "needs_manual_rule_check"
        else:
            state = "compare_supplied_values"
        eligibility[criterion] = {"state": state, "profile_field": profile_key,
                                  "profile_value_present": actual not in (None, "", [], {}),
                                  "listing_criterion_present": required not in (None, "", [], {})}

    required_docs = [str(x) for x in _safe_list(listing.get("required_documents"), max_items=100)]
    documents = profile.get("documents", {}) if isinstance(profile.get("documents", {}), dict) else {}
    document_checklist = []
    for doc in required_docs:
        exists = doc in documents and bool(documents.get(doc))
        document_checklist.append({"document": doc, "provided": exists,
                                   "status": "provided_unverified" if exists else "missing",
                                   "verification_required": True})

    prompt_rows = _safe_list(listing.get("essay_prompts"), max_items=50)
    essay_scaffolds = []
    verified_facts = []
    fact_rows = _safe_list(profile.get("facts"), max_items=500)
    for fact in fact_rows:
        if not isinstance(fact, dict):
            continue
        claim = str(fact.get("claim", "")).strip()
        source = str(fact.get("source", "")).strip()
        if claim:
            verified_facts.append({"claim": claim, "source": source or None,
                                   "verification_status": "user_supplied_unverified"})
    for prompt in prompt_rows:
        p = str(prompt.get("prompt", "") if isinstance(prompt, dict) else prompt).strip()
        if not p:
            continue
        essay_scaffolds.append({
            "prompt": p,
            "status": "outline_needed",
            "outline_questions": [
                "Which specific experience from your own records answers this prompt?",
                "What did you personally do, decide, or change?",
                "What evidence supports each factual claim?",
                "What reflection is genuinely yours rather than an invented lesson?",
            ],
            "available_user_facts": verified_facts,
            "warning": "This is not a finished essay. Do not use any claim that you cannot personally verify."
        })

    deadline = str(listing.get("deadline", "")).strip() or None
    tasks = [
        {"task": "Open the official listing and confirm current rules, deadline, and fees", "status": "todo"},
        {"task": "Resolve unknown eligibility fields against official rules", "status": "todo"},
        {"task": "Check all required documents and application components", "status": "todo"},
        {"task": "Review every biographical and achievement claim against source records", "status": "todo"},
        {"task": "Review essays for accuracy, originality, and personal voice", "status": "todo"},
        {"task": "Obtain explicit human approval before any external submission", "status": "required_gate"},
    ]
    if listing.get("fee") not in (None, "", 0, "0"):
        tasks.insert(1, {"task": "Confirm fee and check official fee-waiver policy before paying", "status": "todo"})
    ready = not missing_fields and all(d["provided"] for d in document_checklist) and bool(prompt_rows or listing.get("application_components"))
    packet = {
        "packet_id": str(uuid4()), "created_at": _now(), "listing": {"title": title, "organization": listing.get("organization"),
            "official_url": url, "deadline": deadline, "source_status": "user_or_provider_supplied_not_independently_verified"},
        "profile_hash": _hash(profile), "listing_hash": _hash(listing), "eligibility_review": eligibility,
        "required_profile_fields": explicitly_required, "missing_profile_fields": missing_fields,
        "documents": document_checklist, "available_claims": verified_facts, "essay_scaffolds": essay_scaffolds,
        "application_components": _safe_list(listing.get("application_components"), max_items=100),
        "tasks": tasks, "notes": notes[:5000], "readiness": "ready_for_human_review" if ready else "incomplete_or_needs_verification",
        "external_submission_performed": False,
        "limitations": ["No application was submitted.", "Eligibility, deadlines, document authenticity and funding were not independently verified.",
                        "No award, acceptance or scholarship outcome is guaranteed."],
    }
    packet["packet_hash"] = _hash(packet)
    return packet


class ApplicationPortfolioStore:
    """SQLite persistence with strict tenant scoping for profile and application records."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.lock = threading.RLock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS application_profiles(
                tenant_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, profile_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS application_items(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, listing_json TEXT NOT NULL,
                status TEXT NOT NULL, notes TEXT NOT NULL, packet_json TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, listing_url TEXT NOT NULL, UNIQUE(tenant_id, listing_url))""")
            # The URL column is added at creation so uniqueness applies per tenant.
            cols = {r[1] for r in db.execute("PRAGMA table_info(application_items)").fetchall()}
            if "listing_url" not in cols:
                db.execute("ALTER TABLE application_items ADD COLUMN listing_url TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS ix_application_tenant_updated ON application_items(tenant_id,updated_at)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=20, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=20000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save_profile(self, tenant_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        if not tenant_id or not isinstance(profile, dict):
            raise ValueError("tenant_id and profile object are required")
        encoded = _json(profile)
        if len(encoded.encode("utf-8")) > 250_000:
            raise ValueError("profile exceeds 250 KB")
        digest = _hash(profile); now = _now()
        with self.lock, self._connect() as db:
            db.execute("""INSERT INTO application_profiles VALUES(?,?,?,?)
                ON CONFLICT(tenant_id) DO UPDATE SET profile_json=excluded.profile_json,
                profile_hash=excluded.profile_hash,updated_at=excluded.updated_at""",
                (tenant_id, encoded, digest, now))
        return {"saved": True, "profile_hash": digest, "updated_at": now,
                "warning": "Facts are user supplied until independently verified."}

    def get_profile(self, tenant_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM application_profiles WHERE tenant_id=?", (tenant_id,)).fetchone()
        if not row: return None
        return {"profile": json.loads(row["profile_json"]), "profile_hash": row["profile_hash"], "updated_at": row["updated_at"]}

    def erase_profile(self, tenant_id: str) -> bool:
        with self.lock, self._connect() as db:
            cur = db.execute("DELETE FROM application_profiles WHERE tenant_id=?", (tenant_id,))
        return cur.rowcount > 0

    def add_listing(self, tenant_id: str, listing: dict[str, Any], *, notes: str = "") -> dict[str, Any]:
        title = str(listing.get("title", "")).strip()
        url = str(listing.get("official_url", "")).strip()
        if not tenant_id or not title or not _https_url(url):
            raise ValueError("tenant_id, title, and official HTTPS URL are required")
        if len(_json(listing).encode("utf-8")) > 100_000:
            raise ValueError("listing exceeds 100 KB")
        ident = str(uuid4()); now = _now()
        with self.lock, self._connect() as db:
            existing = db.execute("SELECT * FROM application_items WHERE tenant_id=? AND listing_url=?", (tenant_id, url)).fetchone()
            if existing:
                return {"id": existing["id"], "created": False, "status": existing["status"], "duplicate": True}
            db.execute("INSERT INTO application_items(id,tenant_id,listing_json,status,notes,packet_json,created_at,updated_at,listing_url) VALUES(?,?,?,?,?,?,?,?,?)",
                        (ident, tenant_id, _json(listing), "discovered", notes[:5000], None, now, now, url))
        return {"id": ident, "created": True, "status": "discovered", "duplicate": False}

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "listing": json.loads(row["listing_json"]), "status": row["status"],
                "notes": row["notes"], "packet": json.loads(row["packet_json"]) if row["packet_json"] else None,
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def list_applications(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM application_items WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?", (tenant_id, max(1,min(500,limit)))).fetchall()
        return [self._row(r) for r in rows]

    def get_application(self, tenant_id: str, application_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM application_items WHERE tenant_id=? AND id=?", (tenant_id, application_id)).fetchone()
        if not row: raise KeyError(application_id)
        return self._row(row)

    def prepare(self, tenant_id: str, application_id: str, *, notes: str = "") -> dict[str, Any]:
        app = self.get_application(tenant_id, application_id)
        profile = self.get_profile(tenant_id)
        if profile is None: raise ValueError("save a profile before preparing an application packet")
        packet = build_application_packet(profile["profile"], app["listing"], notes=notes or app["notes"])
        now = _now()
        new_status = "needs_user_review"
        with self.lock, self._connect() as db:
            cur = db.execute("UPDATE application_items SET packet_json=?,status=?,updated_at=? WHERE tenant_id=? AND id=?",
                             (_json(packet), new_status, now, tenant_id, application_id))
            if cur.rowcount != 1: raise KeyError(application_id)
        return packet

    def update_status(self, tenant_id: str, application_id: str, status: str, *, note: str = "",
                      submission_receipt_url: str | None = None, manual_confirmation: bool = False) -> dict[str, Any]:
        if status not in STATUSES: raise ValueError(f"status must be one of {sorted(STATUSES)}")
        app = self.get_application(tenant_id, application_id)
        current = app["status"]
        if status not in TRANSITIONS[current]:
            raise ValueError(f"invalid status transition: {current} -> {status}")
        if status == "user_approved_to_submit" and current != "needs_user_review":
            raise ValueError("an application packet must be reviewed before approval")
        if status == "submitted_confirmed" and not (manual_confirmation or _https_url(submission_receipt_url)):
            raise ValueError("confirm a real submission manually or provide its HTTPS receipt URL")
        if status == "submitted_confirmed" and current != "user_approved_to_submit":
            raise ValueError("submission can only be recorded after user approval")
        now = _now(); new_note = (app["notes"] + "\n" + note).strip()[:5000] if note else app["notes"]
        with self.lock, self._connect() as db:
            cur = db.execute("UPDATE application_items SET status=?,notes=?,updated_at=? WHERE tenant_id=? AND id=? AND status=?",
                             (status, new_note, now, tenant_id, application_id, current))
            if cur.rowcount != 1: raise RuntimeError("application changed concurrently; reload and retry")
        return {"id": application_id, "previous_status": current, "status": status,
                "submission_performed_by_system": False, "submission_receipt_url": submission_receipt_url if status == "submitted_confirmed" else None}
