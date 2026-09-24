"""Atlas training data for the shared Needle LoRA pipeline, from M07.

Only drafts Udita confirmed (status == "confirmed") become rows; pending and
rejected drafts are never read. Each row teaches Needle to turn a verbatim
contract quote into a ``log_obligation`` call. Arguments are included only when
their exact text appears in the quote (Needle's finetuning rule, also enforced
by ``instinct_models.training.check_row``); anything else is omitted rather
than guessed. Rows are private: the manifest marks the set train-locally-only.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from instinct_models.training.dataset import ExampleRow

from .contract_extraction import KINDS, ObligationDraftRow

LOG_OBLIGATION_TOOL = {
    "name": "log_obligation",
    "description": "Record one deliverable or term from a brand contract clause.",
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "Obligation kind word as written in the clause", "enum": sorted(KINDS)},
            "quantity": {"type": "string", "description": "How many, exactly as written"},
            "due_date": {"type": "string", "description": "Due date, exactly as written"},
            "ends_date": {"type": "string", "description": "End date, exactly as written"},
            "amount": {"type": "string", "description": "Money amount, exactly as written"},
            "currency": {"type": "string", "description": "Currency code or symbol, exactly as written"},
        },
        "required": [],
    },
}

_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]


def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.I)
    return m.group(0) if m else None


def _literal_date(iso: str | None, quote: str) -> str | None:
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return None
    mon = _MONTHS[d.month - 1]
    mon_re = rf"(?:{mon}|{mon[:3]}\.?)"
    for pat in (re.escape(iso), rf"\b{d.day}(?:st|nd|rd|th)?\s+{mon_re}(?:,?\s+{d.year})?",
                rf"\b{mon_re}\s+{d.day}(?:st|nd|rd|th)?(?:,?\s+{d.year})?\b"):
        hit = _find(pat, quote)
        if hit:
            return hit
    return None


def _literal_number(value: float | int | None, quote: str) -> str | None:
    if value is None:
        return None
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", quote):
        try:
            if float(m.group(0).replace(",", "")) == float(value):
                return m.group(0)
        except ValueError:
            continue
    return None


def draft_to_row(d: ObligationDraftRow) -> ExampleRow:
    quote, f = d.quote, dict(d.fields or {})
    args: dict[str, str] = {}
    kind = f.get("kind")
    if kind and kind != "other" and re.search(rf"\b{re.escape(kind)}", quote, re.I):
        args["kind"] = kind
    q = _literal_number(f.get("quantity"), quote)
    if q:
        args["quantity"] = q
    for key in ("due_date", "ends_date"):
        lit = _literal_date(f.get(key), quote)
        if lit:
            args[key] = lit
    amt = f.get("amount_minor")
    a = _literal_number(amt / 100 if isinstance(amt, (int, float)) else None, quote)
    if a:
        args["amount"] = a
    cur = f.get("currency")
    if cur and re.search(rf"\b{re.escape(cur)}\b", quote, re.I):
        args["currency"] = _find(rf"\b{re.escape(cur)}\b", quote)
    return ExampleRow(query=quote, tools=[LOG_OBLIGATION_TOOL], answers=[{"name": "log_obligation", "arguments": args}],
                      confirmed=d.status == "confirmed", source_ref=f"m07_obligation_drafts:{d.tenant_id}:{d.id}",
                      private=True, product="atlas", meta={"brand_id": d.brand_id, "obligation_id": d.obligation_id})


class AtlasObligationDataset:
    """``DomainDataset`` for ``instinct_models.training.build_needle_jsonl``."""
    product = "atlas"

    def __init__(self, session: Session, tenant_id: str):
        self.session, self.tenant_id = session, tenant_id

    def rows(self) -> Iterable[ExampleRow]:
        stmt = (select(ObligationDraftRow)
                .where(ObligationDraftRow.tenant_id == self.tenant_id, ObligationDraftRow.status == "confirmed")
                .order_by(ObligationDraftRow.pk))
        for d in self.session.scalars(stmt):
            yield draft_to_row(d)
