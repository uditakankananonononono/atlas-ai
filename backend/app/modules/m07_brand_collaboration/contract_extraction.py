"""Draft obligations from a contract, confirmed row by row (M07 enhancement).

A contract goes in; draft obligation rows come out. Nothing becomes an
obligation until the owner confirms that row.

- Extraction runs on a model she hosts (``local`` or ``self_hosted`` routes
  from the model layer: Ollama, a local OpenAI-compatible server, or her own
  GPU box). Contract text is private, so hosted routes - even free ones - are
  never used here; if no private route answers, extraction stops with an
  error instead of sending the contract elsewhere.
- Every draft must quote the contract verbatim. Rows whose quote does not
  appear in the contract are dropped and reported, never stored. Values the
  model claims (quantity, amount, dates) that do not appear in the quote are
  flagged on the row so confirmation is checkable.
- ``confirm`` creates the obligation with the quote as its clause text; the
  owner may correct fields but not the quote. ``reject`` records why.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

KINDS = {"deliverable", "usage_rights", "exclusivity", "disclosure", "report", "other"}
_WS = re.compile(r"\s+")
_MONTHS = "january february march april may june july august september october november december".split()


class ObligationDraftRow(Base):
    __tablename__ = "m07_obligation_drafts"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    brand_id: Mapped[str] = mapped_column(String(36), index=True)
    contract_sha256: Mapped[str] = mapped_column(String(64), index=True)
    quote: Mapped[str] = mapped_column(Text)
    fields: Mapped[dict] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON)
    extractor: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    obligation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractionError(RuntimeError):
    pass


class DraftNotFound(LookupError):
    pass


def _norm(s: str) -> str:
    return _WS.sub(" ", s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')).strip().lower()


async def private_generate(prompt: str) -> tuple[str, str, str]:
    """Model layer, restricted to routes on hardware she controls."""
    from app.core import model_catalog, providers
    from app.core.providers import ProviderError

    routes = [r for r in model_catalog.default_chain() if r.kind in {model_catalog.LOCAL, model_catalog.SELF_HOSTED}]
    errors = []
    for r in routes:
        try:
            chosen, text = await providers.generate(prompt, r.provider, r.model)
            return r.provider, chosen, text
        except ProviderError as exc:
            errors.append(f"{r.provider}: {exc}")
    raise ExtractionError("no local/self-hosted model answered; contract text is not sent to hosted models. "
                          + " | ".join(errors))


PROMPT = """You extract obligations from a brand collaboration contract for the creator who signed it.
Return ONLY a JSON array. One object per promise the creator or brand must keep:
{{"quote": "<exact sentence(s) copied character-for-character from the contract>",
  "locator": "<clause number or heading, e.g. 3.2>",
  "kind": "deliverable|usage_rights|exclusivity|disclosure|report|other",
  "title": "<short label>",
  "quantity": <integer or null>,
  "due_date": "<YYYY-MM-DD or null>",
  "ends_date": "<YYYY-MM-DD or null>",
  "amount": <number in major currency units or null>,
  "currency": "<ISO code or null>"}}
Copy quotes exactly. Do not invent dates, amounts or clauses. If none, return [].

CONTRACT:
{contract}"""


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ExtractionError("model did not return a JSON array")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise ExtractionError("model returned invalid JSON") from exc
    if not isinstance(data, list):
        raise ExtractionError("model did not return a JSON array")
    return [d for d in data if isinstance(d, dict)]


def _date_in_quote(iso: str, quote: str) -> bool:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return False
    q = _norm(quote)
    month = _MONTHS[d.month - 1]
    forms = [iso, f"{d.day} {month}", f"{month} {d.day}", f"{d.month}/{d.day}", f"{d.day}/{d.month}", f"{d.day}.{d.month}."]
    return any(f in q for f in forms)


def _number_in_quote(value: float, quote: str) -> bool:
    q = _norm(quote).replace(",", "")
    nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", q)}
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    nums |= {float(v) for w, v in words.items() if re.search(rf"\b{w}\b", q)}
    return float(value) in nums


def vet(rows: list[dict[str, Any]], contract: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep rows whose quote is verbatim in the contract; flag unsupported values."""
    body = _norm(contract)
    kept, dropped = [], []
    for r in rows:
        quote = str(r.get("quote") or "").strip()
        if len(quote) < 8 or _norm(quote) not in body:
            dropped.append({"quote": quote[:300], "reason": "quote_not_in_contract"})
            continue
        kind = str(r.get("kind") or "other").lower()
        fields = {"kind": kind if kind in KINDS else "other", "title": str(r.get("title") or quote[:80]).strip()[:500],
                  "locator": str(r.get("locator") or "").strip()[:200] or "unlabelled",
                  "quantity": None, "due_date": None, "ends_date": None, "amount_minor": None,
                  "currency": (str(r.get("currency")).upper()[:3] if r.get("currency") else None)}
        flags = []
        if r.get("quantity") is not None:
            try:
                fields["quantity"] = max(1, int(r["quantity"]))
                if not _number_in_quote(fields["quantity"], quote):
                    flags.append("quantity_not_in_quote")
            except (TypeError, ValueError):
                flags.append("quantity_unreadable")
        for src, dst in (("due_date", "due_date"), ("ends_date", "ends_date")):
            v = r.get(src)
            if v:
                try:
                    fields[dst] = date.fromisoformat(str(v)).isoformat()
                    if not _date_in_quote(fields[dst], quote):
                        flags.append(f"{dst}_not_in_quote")
                except ValueError:
                    flags.append(f"{dst}_unreadable")
        if r.get("amount") is not None:
            try:
                amt = float(r["amount"])
                fields["amount_minor"] = int(round(amt * 100))
                if not _number_in_quote(amt, quote):
                    flags.append("amount_not_in_quote")
            except (TypeError, ValueError):
                flags.append("amount_unreadable")
        if kind not in KINDS:
            flags.append("kind_unrecognised")
        kept.append({"quote": quote, "fields": fields, "flags": flags})
    return kept, dropped


class ContractExtractor:
    def __init__(self, tenant_id: str, *, tracker: Any, brands: Any,
                 generate: Callable[[str], Awaitable[tuple[str, str, str]]] = private_generate,
                 session_factory: sessionmaker = SessionLocal, clock: Callable[[], datetime] | None = None):
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id, self.tracker, self.brands = tenant_id.strip(), tracker, brands
        self.generate, self.sessions = generate, session_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        Base.metadata.create_all(engine)

    async def extract(self, *, brand_id: str, contract_text: str) -> dict[str, Any]:
        if not self.brands(brand_id):
            raise DraftNotFound(f"brand {brand_id}")
        if len(contract_text.strip()) < 40:
            raise ExtractionError("contract text is too short to extract from")
        provider, model, text = await self.generate(PROMPT.format(contract=contract_text))
        kept, dropped = vet(_parse_json_array(text), contract_text)
        digest = hashlib.sha256(contract_text.encode()).hexdigest()
        now = self.clock()
        ids = []
        with self.sessions.begin() as db:
            for row in kept:
                did = str(uuid4()); ids.append(did)
                db.add(ObligationDraftRow(tenant_id=self.tenant_id, id=did, brand_id=brand_id, contract_sha256=digest,
                                          quote=row["quote"], fields=row["fields"], flags=row["flags"],
                                          extractor={"provider": provider, "model": model}, status="pending",
                                          decision_note="", created_at=now))
        return {"contract_sha256": digest, "extractor": {"provider": provider, "model": model},
                "drafts": [self.get(i) for i in ids], "dropped": dropped,
                "note": "Drafts only. Confirm each row to create an obligation."}

    def get(self, draft_id: str) -> dict[str, Any]:
        r = self._row(draft_id)
        return {"id": r.id, "brand_id": r.brand_id, "contract_sha256": r.contract_sha256, "quote": r.quote,
                "fields": r.fields, "flags": r.flags, "extractor": r.extractor, "status": r.status,
                "obligation_id": r.obligation_id, "decision_note": r.decision_note}

    def pending(self, brand_id: str) -> list[dict[str, Any]]:
        with self.sessions() as db:
            rows = list(db.scalars(select(ObligationDraftRow).where(
                ObligationDraftRow.tenant_id == self.tenant_id, ObligationDraftRow.brand_id == brand_id,
                ObligationDraftRow.status == "pending").order_by(ObligationDraftRow.created_at, ObligationDraftRow.pk)))
        return [self.get(r.id) for r in rows]

    def confirm(self, draft_id: str, *, edits: dict[str, Any] | None = None, note: str = "") -> dict[str, Any]:
        r = self._row(draft_id)
        if r.status != "pending":
            raise ExtractionError(f"draft is already {r.status}")
        edits = dict(edits or {})
        if "quote" in edits or "clause_text" in edits:
            raise ExtractionError("the quote is the contract's own text and cannot be edited; reject and add manually instead")
        f = {**r.fields, **{k: v for k, v in edits.items() if k in r.fields}}
        if f["kind"] not in KINDS:
            raise ExtractionError("kind must be one of " + ", ".join(sorted(KINDS)))

        def dt(v):
            return datetime.fromisoformat(f"{v}T23:59:00").replace(tzinfo=timezone.utc) if v else None
        ob = self.tracker.create(brand_id=r.brand_id, kind=f["kind"], title=f["title"], clause_text=r.quote,
                                 clause_locator=f["locator"], quantity=int(f.get("quantity") or 1),
                                 due_at=dt(f.get("due_date")), ends_at=dt(f.get("ends_date")),
                                 amount_minor=int(f.get("amount_minor") or 0), currency=f.get("currency") or "USD")
        with self.sessions.begin() as db:
            row = db.scalar(select(ObligationDraftRow).where(ObligationDraftRow.tenant_id == self.tenant_id,
                                                             ObligationDraftRow.id == draft_id))
            row.status, row.obligation_id, row.fields = "confirmed", ob["id"], f
            row.decision_note, row.decided_at = note, self.clock()
        return {"draft": self.get(draft_id), "obligation": ob}

    def reject(self, draft_id: str, *, reason: str) -> dict[str, Any]:
        if len(reason.strip()) < 3:
            raise ExtractionError("rejecting a draft needs a reason")
        r = self._row(draft_id)
        if r.status != "pending":
            raise ExtractionError(f"draft is already {r.status}")
        with self.sessions.begin() as db:
            row = db.scalar(select(ObligationDraftRow).where(ObligationDraftRow.tenant_id == self.tenant_id,
                                                             ObligationDraftRow.id == draft_id))
            row.status, row.decision_note, row.decided_at = "rejected", reason.strip(), self.clock()
        return self.get(draft_id)

    def _row(self, draft_id: str) -> ObligationDraftRow:
        with self.sessions() as db:
            r = db.scalar(select(ObligationDraftRow).where(ObligationDraftRow.tenant_id == self.tenant_id,
                                                           ObligationDraftRow.id == draft_id))
        if r is None:
            raise DraftNotFound(draft_id)
        return r
