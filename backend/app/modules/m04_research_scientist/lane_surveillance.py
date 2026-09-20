from __future__ import annotations

import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

from .models import Paper, SearchQuery, normalize_doi, utcnow_iso


class SurveillanceStore:
    """SQLite-backed query and result store with deterministic deduplication."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS queries (
              query_id TEXT PRIMARY KEY, text TEXT NOT NULL, sources TEXT NOT NULL,
              since TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS papers (
              paper_id TEXT PRIMARY KEY, title TEXT NOT NULL, abstract TEXT NOT NULL,
              authors TEXT NOT NULL, published_at TEXT, doi TEXT, url TEXT,
              source TEXT NOT NULL, metadata TEXT NOT NULL, observed_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS papers_doi_unique
              ON papers(doi) WHERE doi IS NOT NULL;
            CREATE TABLE IF NOT EXISTS query_results (
              query_id TEXT NOT NULL, paper_id TEXT NOT NULL, first_seen_at TEXT NOT NULL,
              PRIMARY KEY(query_id, paper_id),
              FOREIGN KEY(query_id) REFERENCES queries(query_id),
              FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
            );
            """
        )

    def save_query(self, query: SearchQuery) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO queries VALUES (?, ?, ?, ?, ?)",
                (query.query_id, query.text, json.dumps(query.sources), query.since, query.created_at),
            )

    def ingest(self, query_id: str, papers: Iterable[Paper]) -> list[Paper]:
        now = utcnow_iso()
        inserted: list[Paper] = []
        with self.connection:
            if self.connection.execute("SELECT 1 FROM queries WHERE query_id=?", (query_id,)).fetchone() is None:
                raise KeyError(f"unknown query: {query_id}")
            for paper in papers:
                existing = None
                if paper.doi:
                    existing = self.connection.execute("SELECT paper_id FROM papers WHERE doi=?", (paper.doi,)).fetchone()
                canonical_id = existing[0] if existing else paper.paper_id
                existed = self.connection.execute("SELECT 1 FROM papers WHERE paper_id=?", (canonical_id,)).fetchone()
                if not existed:
                    self.connection.execute(
                        "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (canonical_id, paper.title, paper.abstract, json.dumps(paper.authors), paper.published_at,
                         paper.doi, paper.url, paper.source, json.dumps(paper.metadata, sort_keys=True), now),
                    )
                    inserted.append(paper)
                self.connection.execute(
                    "INSERT OR IGNORE INTO query_results VALUES (?, ?, ?)", (query_id, canonical_id, now)
                )
        return inserted

    def list_results(self, query_id: str) -> list[Paper]:
        rows = self.connection.execute(
            """SELECT p.* FROM papers p JOIN query_results r ON p.paper_id=r.paper_id
               WHERE r.query_id=? ORDER BY COALESCE(p.published_at, '') DESC, p.paper_id""", (query_id,)
        ).fetchall()
        return [Paper(r["paper_id"], r["title"], r["abstract"], tuple(json.loads(r["authors"])),
                      r["published_at"], r["doi"], r["url"], r["source"], json.loads(r["metadata"])) for r in rows]


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def parse_syndication_feed(payload: bytes | str, source: str) -> list[Paper]:
    """Parse RSS 2 or Atom without executing or fetching embedded content."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    root = ET.fromstring(payload)
    atom = root.tag.endswith("feed")
    entries = list(root) if atom else root.findall("./channel/item")
    papers: list[Paper] = []
    for entry in entries:
        children = {child.tag.rsplit("}", 1)[-1]: child for child in list(entry)}
        title = _text(children.get("title"))
        link_node = children.get("link")
        url = (link_node.get("href") if link_node is not None else None) or _text(link_node)
        identifier = _text(children.get("id")) or _text(children.get("guid")) or url
        if not title or not identifier:
            continue
        doi = None
        for candidate in (identifier, url or ""):
            if "10." in candidate and ("doi" in candidate.lower() or candidate.lower().startswith("10.")):
                doi = normalize_doi(candidate)
                break
        abstract = _text(children.get("summary")) or _text(children.get("description"))
        published = _text(children.get("published")) or _text(children.get("pubDate")) or _text(children.get("updated"))
        authors = tuple(_text(node) for node in list(entry) if node.tag.rsplit("}", 1)[-1] in {"author", "creator"})
        paper_id = hashlib.sha256(f"{source}\0{identifier}".encode()).hexdigest()[:24]
        papers.append(Paper(paper_id, title, abstract, tuple(a for a in authors if a), published or None,
                            doi, url or None, source, {"feed_identifier": identifier}))
    return papers


def validate_public_feed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("feed URL must be HTTP(S)")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("local feed URLs are not allowed")
