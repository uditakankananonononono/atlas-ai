"""Bounded importer + runtime lookup for an OFFICIAL public US school/program catalog.

Sources (NCES IPEDS Data Center bulk CSV files + NCES CIP code list). Public bulk
files only: no login, no API key, no sign-up, no paid call. The importer works on
local zip/csv files; `download_sources` fetches only the pinned https nces.ed.gov
URLs below and refuses redirects to any other host.

HONEST LIMITS (also returned by `coverage`):
- US Title-IV-universe institutions only (IPEDS). Not a global database; no non-US schools.
- Program lists are DERIVED from 2023-24 award completions: a program with no
  completions that year is absent, so this is not a list of every offered major.
- No tuition/net-price/admission data (IPEDS HD has none; College Scorecard
  bulk files were not reachable from this environment). Budget fit stays None.
- No scholarship source was verified, so scholarships are NOT covered.
- Redistribution/licence status of the files is UNCONFIRMED (see TERMS); private local use only.
- Website/URL fields are institution-reported in IPEDS; they are not re-verified live.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOST = "nces.ed.gov"
BASE = "https://nces.ed.gov/ipeds/datacenter/data/"
SOURCES = {
    "hd": {"url": BASE + "HD2024.zip", "member": "HD2024.csv", "what": "IPEDS Institutional Characteristics directory, collection year 2024",
           "sha256": "d98425c123d7c0e872aec6e83960dfb501884818bf17385c340790f3d1f28345", "max_bytes": 5_000_000},
    "completions": {"url": BASE + "C2024_A.zip", "member": "C2024_a.csv", "what": "IPEDS Completions by CIP code and award level, 2023-24 awards",
              "sha256": "03234cc27fe4e7eb835a66d4f37aaec11bdac8dfa278f971584e1b20d03e1159", "max_bytes": 20_000_000},
    "cip": {"url": "https://nces.ed.gov/ipeds/cipcode/Files/CIPCode2020.csv", "member": None, "what": "NCES CIP 2020 program titles",
            "sha256": "6cf0882c1f5beb94981d0a1a72285ab5cf633759f45433fb909afbfb6d6b2657", "max_bytes": 5_000_000},
}
TERMS = {
    "url": "https://nces.ed.gov/about/public-access-research",
    "requested_url": "https://nces.ed.gov/help/disclaimer.asp (HTTP 301 to the url above)",
    "statement": ("Verbatim: \"Unless stated otherwise, all information on the U.S. Department of Education's IES website at "
                  "http://ies.ed.gov is in the public domain and may be reproduced, published, linked to, or otherwise used "
                  "without IES' permission. This statement does not pertain to information at websites other than "
                  "http://ies.ed.gov, whether funded by or linked to from IES.\" Cite: U.S. Department of Education. "
                  "Institute of Education Sciences."),
    "checked_on": "2026-10-03",
    "status": "UNCONFIRMED for these files",
    "caveat": ("The statement names ies.ed.gov and expressly excludes other websites; it does not name nces.ed.gov, "
               "where these files are hosted. Whether the files are public domain / freely redistributable is NOT "
               "settled and no file-specific grant was found. Treat as private/local use of public downloads with "
               "attribution; do not redistribute the data or claim a licence until NCES clarifies the terms."),
}
SECTOR = {"0": "Administrative unit", "1": "Public, 4-year or above", "2": "Private not-for-profit, 4-year or above",
          "3": "Private for-profit, 4-year or above", "4": "Public, 2-year", "5": "Private not-for-profit, 2-year",
          "6": "Private for-profit, 2-year", "7": "Public, less-than 2-year",
          "8": "Private not-for-profit, less-than 2-year", "9": "Private for-profit, less-than 2-year"}
CONTROL = {"1": "public", "2": "private_nonprofit", "3": "private_forprofit"}
AWARD = {"1": "certificate <1yr", "2": "certificate 1-<2yr", "3": "associate", "4": "certificate 2-<4yr", "5": "bachelor",
         "6": "postbaccalaureate certificate", "7": "master", "8": "post-master certificate",
         "17": "doctor research", "18": "doctor professional", "19": "doctor other",
         "20": "certificate <12wk", "21": "certificate 12wk-<1yr"}
AGGREGATE_AWARDS = {"12", "13", "14", "15"}  # totals rows; excluded to avoid double counting

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(key TEXT PRIMARY KEY,url TEXT,sha256 TEXT,bytes INTEGER,retrieved_at TEXT,what TEXT,member TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS institutions(unitid TEXT PRIMARY KEY,name TEXT,alias TEXT,city TEXT,state TEXT,zip TEXT,
 sector TEXT,sector_label TEXT,control TEXT,level TEXT,degree_granting INTEGER,active INTEGER,official_url TEXT,
 latitude REAL,longitude REAL);
CREATE TABLE IF NOT EXISTS programs(unitid TEXT,cip TEXT,award TEXT,completions INTEGER,PRIMARY KEY(unitid,cip,award));
CREATE TABLE IF NOT EXISTS cip_titles(cip TEXT PRIMARY KEY,title TEXT);
CREATE INDEX IF NOT EXISTS ix_inst_state ON institutions(state);
CREATE INDEX IF NOT EXISTS ix_prog_cip ON programs(cip);
"""


class CatalogError(ValueError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_sources(dest: Path, *, opener=None) -> dict[str, Path]:
    """Download the pinned public files. Only https://nces.ed.gov; off-host redirects refused; proxies explicitly
    disabled (environment proxy settings are NOT honoured); streamed with a hard size cap; the sha256 must equal the
    pinned value or the file is discarded. A hash mismatch means NCES published a different file: review it, then
    update the pin deliberately. Nothing is written to `dest` unless it verified."""
    dest.mkdir(parents=True, exist_ok=True)

    class _NoOffHost(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            p = urlparse(newurl)
            if p.scheme != "https" or p.hostname != ALLOWED_HOST:
                raise CatalogError(f"refused redirect to {newurl}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    op = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoOffHost)
    out = {}
    for key, s in SOURCES.items():
        p = urlparse(s["url"])
        if p.scheme != "https" or p.hostname != ALLOWED_HOST:
            raise CatalogError("source not on allowed host")
        target = dest / Path(p.path).name
        part = Path(str(target) + ".part")
        h, n = hashlib.sha256(), 0
        try:
            with op.open(urllib.request.Request(s["url"], headers={"User-Agent": "atlas-catalog-importer/1"}), timeout=60) as r, open(part, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    n += len(chunk)
                    if n > s["max_bytes"]:
                        raise CatalogError(f"{key}: exceeds size cap {s['max_bytes']} bytes")
                    h.update(chunk)
                    f.write(chunk)
            if h.hexdigest() != s["sha256"]:
                raise CatalogError(f"{key}: sha256 {h.hexdigest()} != pinned {s['sha256']}; file changed upstream, review before re-pinning")
            part.replace(target)
        finally:
            part.unlink(missing_ok=True)
        out[key] = target
    return out


def _rows(path: Path, member: str | None):
    if path.suffix.lower() == ".zip":
        z = zipfile.ZipFile(path)
        names = {n.lower(): n for n in z.namelist()}
        want = (member or "").lower()
        if want not in names:
            raise CatalogError(f"{path.name}: expected member {member}, found {z.namelist()}")
        raw = z.read(names[want])
    else:
        raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("latin-1")
    return csv.DictReader(io.StringIO(text))


def _norm_url(u: str) -> str | None:
    u = (u or "").strip()
    if not u or u.lower() in {"-2", "-1", "-3"}:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    pu = urlparse(u)
    return u if pu.hostname and "." in pu.hostname and pu.scheme in {"http", "https"} else None


def _need(row: dict, cols: list[str], label: str):
    miss = [c for c in cols if c not in row]
    if miss:
        raise CatalogError(f"{label}: missing expected columns {miss}")


def import_catalog(files: dict[str, Path], db_path: Path, *, retrieved_at: str | None = None) -> dict:
    """Build the catalog from LOCAL files (keys hd, completions, cip). Returns the coverage report."""
    if set(files) != set(SOURCES):
        raise CatalogError(f"need files for {sorted(SOURCES)}")
    stamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = Path(str(db_path) + ".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    skipped = {"institutions_no_unitid": 0, "program_rows_unknown_unitid": 0, "program_rows_aggregate_or_total": 0,
               "program_rows_bad_number": 0}
    for key, s in SOURCES.items():
        p = files[key]
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?)",
                   (key, s["url"], _sha(p), p.stat().st_size, stamp, s["what"], s["member"]))
    # institutions
    n_inst = 0
    for r in _rows(files["hd"], SOURCES["hd"]["member"]):
        r = {k.lstrip("\ufeff").lstrip("ï»¿"): v for k, v in r.items()}
        _need(r, ["UNITID", "INSTNM", "STABBR", "SECTOR", "CONTROL", "CYACTIVE", "WEBADDR"], "HD")
        uid = (r["UNITID"] or "").strip()
        if not uid:
            skipped["institutions_no_unitid"] += 1
            continue
        def f(k):
            try:
                v = float(r.get(k, ""))
                return v if abs(v) <= 180 else None
            except ValueError:
                return None
        level = {"1": "4-year+", "2": "2-year", "3": "<2-year"}.get((r.get("ICLEVEL") or "").strip())
        db.execute("INSERT INTO institutions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (uid, r["INSTNM"].strip(), (r.get("IALIAS") or "").strip() or None, (r.get("CITY") or "").strip(),
                    r["STABBR"].strip(), (r.get("ZIP") or "").strip(), r["SECTOR"].strip(),
                    SECTOR.get(r["SECTOR"].strip()), CONTROL.get(r["CONTROL"].strip()), level,
                    1 if (r.get("DEGGRANT") or "").strip() == "1" else 0, 1 if r["CYACTIVE"].strip() == "1" else 0,
                    _norm_url(r["WEBADDR"]), f("LATITUDE"), f("LONGITUD")))
        n_inst += 1
    known = {u for (u,) in db.execute("SELECT unitid FROM institutions")}
    # cip titles
    n_cip = 0
    for r in _rows(files["cip"], None):
        code = (r.get("CIPCode") or "").replace("=", "").replace('"', "").strip()
        if re.fullmatch(r"\d\d\.\d{4}", code):
            db.execute("INSERT OR REPLACE INTO cip_titles VALUES(?,?)", (code, (r.get("CIPTitle") or "").strip().rstrip(".")))
            n_cip += 1
    # programs
    n_prog = 0
    for r in _rows(files["completions"], SOURCES["completions"]["member"]):
        r = {k.lstrip("\ufeff"): v for k, v in r.items()}
        _need(r, ["UNITID", "CIPCODE", "AWLEVEL", "CTOTALT"], "Completions")
        uid, cip, aw = r["UNITID"].strip(), r["CIPCODE"].strip().strip('"'), r["AWLEVEL"].strip()
        if aw in AGGREGATE_AWARDS or cip.startswith("99") or not re.fullmatch(r"\d\d\.\d{4}", cip):
            skipped["program_rows_aggregate_or_total"] += 1
            continue
        if uid not in known:
            skipped["program_rows_unknown_unitid"] += 1
            continue
        try:
            n = int(r["CTOTALT"])
        except ValueError:
            skipped["program_rows_bad_number"] += 1
            continue
        if n <= 0:
            continue
        db.execute("INSERT INTO programs VALUES(?,?,?,?) ON CONFLICT(unitid,cip,award) DO UPDATE SET completions=completions+excluded.completions",
                   (uid, cip, aw, n))
        n_prog += 1
    cov = _coverage_from(db, skipped)
    db.execute("INSERT INTO meta VALUES('coverage',?)", (json.dumps(cov),))
    db.execute("INSERT INTO meta VALUES('imported_at',?)", (stamp,))
    db.commit()
    db.close()
    tmp.replace(db_path)
    return cov


def _coverage_from(db, skipped=None) -> dict:
    q = lambda s: db.execute(s).fetchone()[0]
    srcs = [dict(zip(("key", "url", "sha256", "bytes", "retrieved_at", "what"), row))
            for row in db.execute("SELECT key,url,sha256,bytes,retrieved_at,what FROM sources ORDER BY key")]
    return {
        "scope": "US institutions in the NCES IPEDS 2024 directory only; not a global database",
        "data_vintage": "IPEDS HD collection year 2024; completions = 2023-24 awards; CIP 2020 titles (files on nces.ed.gov dated 2025-09-21)",
        "institutions": q("SELECT count(*) FROM institutions"),
        "institutions_active": q("SELECT count(*) FROM institutions WHERE active=1"),
        "institutions_degree_granting": q("SELECT count(*) FROM institutions WHERE degree_granting=1"),
        "institutions_with_official_url": q("SELECT count(*) FROM institutions WHERE official_url IS NOT NULL"),
        "institutions_with_any_program": q("SELECT count(DISTINCT unitid) FROM programs"),
        "program_rows": q("SELECT count(*) FROM programs"),
        "cip_titles": q("SELECT count(*) FROM cip_titles"),
        "program_rows_without_cip_title": q("SELECT count(*) FROM programs p LEFT JOIN cip_titles c ON c.cip=p.cip WHERE c.cip IS NULL"),
        "skipped": skipped or {},
        "not_covered": ["non-US institutions", "tuition / net price / admission data", "scholarships (no official bulk source verified)",
                        "programs with zero 2023-24 completions", "live re-verification of websites"],
        "program_basis": "derived from 2023-24 completions, not an offered-majors list",
        "licence": TERMS,
        "sources": srcs,
    }


class Catalog:
    def __init__(self, db_path: Path | str):
        self.path = Path(db_path)
        if not self.path.exists():
            raise CatalogError("catalog not imported")
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
        self.db.row_factory = sqlite3.Row

    def coverage(self) -> dict:
        cov = json.loads(self.db.execute("SELECT value FROM meta WHERE key='coverage'").fetchone()[0])
        cov["imported_at"] = self.db.execute("SELECT value FROM meta WHERE key='imported_at'").fetchone()[0]
        return cov

    @staticmethod
    def _like(s: str) -> str:
        return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    def _prov(self) -> dict:
        return {"source": "NCES IPEDS 2024 (public bulk files)", "terms_url": TERMS["url"], "terms_status": TERMS["status"],
                "files": {k: {"url": u, "sha256": h, "retrieved_at": t}
                          for k, u, h, t in self.db.execute("SELECT key,url,sha256,retrieved_at FROM sources")}}

    def search_institutions(self, *, q: str | None = None, state: str | None = None, control: str | None = None,
                            cip_keyword: str | None = None, award: str | None = None, active_only: bool = True,
                            limit: int = 25) -> dict:
        limit = max(1, min(int(limit), 100))
        where, args = ["1=1"], []
        if active_only:
            where.append("i.active=1 AND i.degree_granting=1")
        if q:
            where.append("(i.name LIKE ? ESCAPE '\\' OR i.alias LIKE ? ESCAPE '\\')")
            args += [self._like(q)] * 2
        if state:
            if not re.fullmatch(r"[A-Za-z]{2}", state):
                raise CatalogError("state must be a 2-letter code")
            where.append("i.state=?")
            args.append(state.upper())
        if control:
            if control not in CONTROL.values():
                raise CatalogError(f"control must be one of {sorted(CONTROL.values())}")
            where.append("i.control=?")
            args.append(control)
        if cip_keyword or award:
            sub = ["p.unitid=i.unitid"]
            if cip_keyword:
                sub.append("p.cip IN (SELECT cip FROM cip_titles WHERE title LIKE ? ESCAPE '\\')")
                args.append(self._like(cip_keyword))
            if award:
                codes = [k for k, v in AWARD.items() if v == award]
                if not codes:
                    raise CatalogError(f"award must be one of {sorted(AWARD.values())}")
                sub.append("p.award=?")
                args.append(codes[0])
            where.append("EXISTS(SELECT 1 FROM programs p WHERE " + " AND ".join(sub) + ")")
        rows = self.db.execute(f"SELECT i.* FROM institutions i WHERE {' AND '.join(where)} ORDER BY i.name LIMIT ?", args + [limit]).fetchall()
        total = self.db.execute(f"SELECT count(*) FROM institutions i WHERE {' AND '.join(where)}", args).fetchone()[0]
        return {"total_matches": total, "returned": len(rows), "results": [self._inst(r) for r in rows], "provenance": self._prov()}

    def _inst(self, r) -> dict:
        d = {k: r[k] for k in ("unitid", "name", "city", "state", "sector_label", "control", "level", "official_url")}
        d["id"] = r["unitid"]
        return d

    def programs(self, unitid: str, *, limit: int = 300) -> list[dict]:
        rows = self.db.execute("""SELECT p.cip,c.title,p.award,p.completions FROM programs p LEFT JOIN cip_titles c ON c.cip=p.cip
                                  WHERE p.unitid=? ORDER BY p.completions DESC LIMIT ?""", (unitid, max(1, min(limit, 1000)))).fetchall()
        return [{"cip": r["cip"], "title": r["title"], "award": AWARD.get(r["award"], r["award"]), "completions_2023_24": r["completions"]} for r in rows]

    def institution(self, unitid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM institutions WHERE unitid=?", (unitid,)).fetchone()
        if not r:
            return None
        d = self._inst(r)
        d["programs"] = self.programs(unitid)
        d["provenance"] = self._prov()
        return d

    def search_programs(self, q: str, limit: int = 25) -> dict:
        if not q or len(q.strip()) < 2:
            raise CatalogError("query too short")
        rows = self.db.execute("""SELECT c.cip,c.title,count(DISTINCT p.unitid) schools,sum(p.completions) comps FROM cip_titles c
            JOIN programs p ON p.cip=c.cip WHERE c.title LIKE ? ESCAPE '\\' GROUP BY c.cip ORDER BY schools DESC LIMIT ?""",
                               (self._like(q.strip()), max(1, min(limit, 100)))).fetchall()
        return {"results": [{"cip": r["cip"], "title": r["title"], "institutions_with_2023_24_completions": r["schools"],
                             "completions_2023_24": r["comps"]} for r in rows], "provenance": self._prov(),
                "basis": "CIP titles with at least one 2023-24 completion; not an offered-majors list"}

    def schools_for_match(self, unitids: list[str]) -> list[dict]:
        """Shape catalog rows for AdvisingService.school_match. annual_cost_usd is None: the catalog has no cost data."""
        out = []
        for u in unitids[:500]:
            inst = self.db.execute("SELECT * FROM institutions WHERE unitid=?", (u,)).fetchone()
            if not inst or not inst["official_url"]:
                continue
            progs = self.programs(u, limit=1000)
            out.append({"id": u, "name": inst["name"], "official_url": inst["official_url"], "annual_cost_usd": None,
                        "programs": sorted({p["title"] for p in progs if p["title"]}),
                        "catalog_source": "NCES IPEDS 2024; programs derived from 2023-24 completions"})
        return out
