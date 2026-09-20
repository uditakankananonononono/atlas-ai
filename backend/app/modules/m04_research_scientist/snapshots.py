from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .models import Cluster, EvidenceGap, Paper, SearchQuery, utcnow_iso
from .reproducibility import content_hash


@dataclass(frozen=True, slots=True)
class SurveillanceSnapshot:
    snapshot_id: str
    created_at: str
    query: dict
    papers: tuple[dict, ...]
    clusters: tuple[dict, ...]
    candidate_gaps: tuple[dict, ...]

    def write(self, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(self), sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return path


def create_snapshot(query: SearchQuery, papers: Iterable[Paper], clusters: Iterable[Cluster], gaps: Iterable[EvidenceGap]) -> SurveillanceSnapshot:
    paper_data = tuple(p.to_dict() for p in sorted(papers, key=lambda item: item.paper_id))
    cluster_data = tuple(asdict(c) for c in sorted(clusters, key=lambda item: item.cluster_id))
    gap_data = tuple(asdict(g) for g in sorted(gaps, key=lambda item: item.gap_id))
    query_data = asdict(query)
    identity = content_hash({"query": query_data, "papers": paper_data, "clusters": cluster_data, "gaps": gap_data})[7:23]
    return SurveillanceSnapshot(f"snapshot-{identity}", utcnow_iso(), query_data, paper_data, cluster_data, gap_data)
