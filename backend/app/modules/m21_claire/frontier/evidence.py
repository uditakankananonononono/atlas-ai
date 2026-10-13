from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import exp, log
from typing import Any
from urllib.parse import urlparse
import hashlib


def _parse_time(value: str | None) -> datetime | None:
    if not value: return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None: result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
            return result.astimezone(timezone.utc) if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except Exception: return None


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."): host = host[4:]
    # Conservative approximation only; production should use the Public Suffix List.
    parts = host.split(".")
    if len(parts) >= 3 and parts[-1] in {"uk", "au", "in", "jp", "nz", "sg"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class EvidenceLattice:
    """Evidence-aware claim grading with domain de-duplication and explicit uncertainty.

    It does not decide truth; it grades corroboration inside the supplied evidence set.
    `authority` is a reviewer-supplied input, not inferred from a domain name.
    """
    def adjudicate(self, claim: str, evidence: list[dict[str, Any]], *, now: datetime | None = None,
                   half_life_days: float = 365.0) -> dict[str, Any]:
        if not claim.strip(): raise ValueError("claim is required")
        if len(evidence) > 500: raise ValueError("maximum 500 evidence records per claim")
        if half_life_days <= 0: raise ValueError("half_life_days must be positive")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        domain_items: dict[str, list[dict[str, Any]]] = {}
        skipped=[]
        for item in evidence:
            url=str(item.get("url", "")); stance=str(item.get("stance", "neutral")).lower()
            excerpt=str(item.get("excerpt", "")).strip(); source_id=str(item.get("source_id", ""))
            if stance not in {"supports", "refutes", "neutral"}:
                skipped.append({"source_id": source_id, "reason": "invalid_stance"}); continue
            host = _domain(url) if url.startswith(("https://", "http://")) else ""
            if not host or not excerpt or not source_id:
                skipped.append({"source_id": source_id, "reason": "missing_source_url_id_or_excerpt"}); continue
            authority=max(0.0,min(1.0,float(item.get("authority",0.5))))
            dt=_parse_time(item.get("published_at"))
            age_days=max(0.0,(now-dt).total_seconds()/86400) if dt else 365.0
            freshness=exp(-log(2)*age_days/half_life_days)
            digest=hashlib.sha256((excerpt.casefold().strip()).encode()).hexdigest()
            weight=authority*freshness
            candidate={"source_id":source_id,"url":url,"domain":host,"stance":stance,"weight":weight,
                       "authority":authority,"freshness":freshness,"published_at":item.get("published_at"),"excerpt_sha256":digest}
            domain_items.setdefault(host,[]).append(candidate)
        # One contribution per domain, resolved independent of input order. Stances are
        # tracked separately: a domain holding both a supporting and a refuting item is a
        # conflict (never silently resolved); otherwise the strongest non-neutral item
        # represents the domain; neutral only if nothing else is present.
        by_domain={}
        for host,items in domain_items.items():
            key=lambda x:(x["weight"],x["source_id"])
            sup=[x for x in items if x["stance"]=="supports"]; ref=[x for x in items if x["stance"]=="refutes"]
            if sup and ref:
                rep=dict(max(sup+ref,key=key)); rep["stance"]="neutral"; rep["intra_domain_conflict"]=True
            elif sup or ref: rep=max(sup or ref,key=key)
            else: rep=max(items,key=key)
            by_domain[host]=rep
        support=sum(x["weight"] for x in by_domain.values() if x["stance"]=="supports")
        refute=sum(x["weight"] for x in by_domain.values() if x["stance"]=="refutes")
        neutral=sum(x["weight"] for x in by_domain.values() if x["stance"]=="neutral")
        total=support+refute+neutral
        margin=(support-refute)/total if total else 0.0
        distinct=len(by_domain)
        conflicted=any(x.get("intra_domain_conflict") for x in by_domain.values())
        if conflicted or (support>0.25 and refute>0.25): grade="contested"
        elif distinct>=2 and support>=0.8 and margin>=0.55: grade="corroborated_in_supplied_evidence"
        elif distinct>=2 and refute>=0.8 and margin<=-0.55: grade="contradicted_in_supplied_evidence"
        elif support>refute and support>0: grade="weakly_supported"
        elif refute>support and refute>0: grade="weakly_refuted"
        else: grade="insufficient_evidence"
        return {"claim":claim,"grade":grade,"score":{"support":round(support,4),"refute":round(refute,4),
                 "neutral":round(neutral,4),"signed_margin":round(margin,4)},
                "independent_domain_count":distinct,"evidence":sorted(by_domain.values(),key=lambda x:(-x["weight"],x["domain"])),
                "skipped":skipped,"limitations":["This is not a truth oracle.","Authority scores are supplied, not automatically validated.",
                    "Domain de-duplication approximates registrable domains; review cross-domain ownership.",
                    "Source quality, selection bias, and claim entailment still need human or independent-model review."]}
