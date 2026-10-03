import hashlib, io, json, os, zipfile, urllib.request
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad import official_catalog as oc

H = {"x-atlas-tenant": "cat-a", "x-atlas-actor": "student"}
HD = ("UNITID,INSTNM,IALIAS,CITY,STABBR,ZIP,SECTOR,ICLEVEL,CONTROL,DEGGRANT,CYACTIVE,WEBADDR,LATITUDE,LONGITUD\n"
      '1,"Alpha University","AU","Town","CA","90000",1,1,1,1,1,"www.alpha.edu/",34.0,-118.0\n'
      '2,"Beta College","","Ville","NY","10000",2,1,2,1,1,"https://beta.edu",40.0,-74.0\n'
      '3,"Closed Tech","","X","CA","90001",6,2,3,0,3,"-2",-999,-999\n'
      '4,"No Site 100%_ College","","Y","TX","75000",4,2,1,1,1," ",30.0,-97.0\n')
COMP = ("UNITID,CIPCODE,MAJORNUM,AWLEVEL,CTOTALT\n"
        '1,"26.0101",1,5,10\n1,"26.0101",2,5,2\n1,"26.0101",1,12,12\n1,"11.0701",1,7,4\n1,"99",1,5,100\n'
        '2,"26.0101",1,5,0\n2,"45.0601",1,5,7\n9,"26.0101",1,5,3\n')
CIP = ('"CIPFamily","CIPCode","Action","TextChange","CIPTitle"\n'
       '="26",="26.0101","x","no","Biology/Biological Sciences, General."\n'
       '="11",="11.0701","x","no","Computer Science."\n'
       '="45",="45.0601","x","no","Economics, General."\n="26",="26","x","no","FAMILY ROW."\n')


def zipped(name, csvname, text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(csvname, "\ufeff" + text)
    return name, b.getvalue()


@pytest.fixture()
def fx(tmp_path):
    for n, c, t in (("HD2024.zip", "HD2024.csv", HD), ("C2024_A.zip", "C2024_a.csv", COMP)):
        n, b = zipped(n, c, t)
        (tmp_path / n).write_bytes(b)
    (tmp_path / "CIPCode2020.csv").write_text(CIP)
    files = {"hd": tmp_path / "HD2024.zip", "completions": tmp_path / "C2024_A.zip", "cip": tmp_path / "CIPCode2020.csv"}
    db = tmp_path / "cat.sqlite"
    cov = oc.import_catalog(files, db, retrieved_at="2026-10-03T00:00:00+00:00")
    return files, db, cov


def test_coverage_counts_and_skips_are_exact(fx):
    _, db, cov = fx
    assert cov["institutions"] == 4 and cov["institutions_active"] == 3 and cov["institutions_with_official_url"] == 2
    # kept: u1 26.0101 bach (10+2 summed, total-level row 12 dropped), u1 11.0701, u2 45.0601; u2 zero-completion dropped
    assert cov["program_rows"] == 3 and cov["cip_titles"] == 3
    assert cov["skipped"]["program_rows_aggregate_or_total"] == 2 and cov["skipped"]["program_rows_unknown_unitid"] == 1
    assert "scholarships" in " ".join(cov["not_covered"]) and "not a global database" in cov["scope"]
    assert all(len(s["sha256"]) == 64 for s in cov["sources"])
    assert cov["licence"]["url"] == "https://nces.ed.gov/about/public-access-research"
    assert cov["licence"]["status"] == "UNCONFIRMED for these files" and "expressly excludes" in cov["licence"]["caveat"]
    assert "does not pertain to information at websites other than" in cov["licence"]["statement"]


def test_major_numbers_are_summed_and_titles_attached(fx):
    c = oc.Catalog(fx[1])
    p = {x["cip"]: x for x in c.programs("1")}
    assert p["26.0101"]["completions_2023_24"] == 12 and p["26.0101"]["title"] == "Biology/Biological Sciences, General"
    assert p["26.0101"]["award"] == "bachelor"


def test_search_filters_and_default_hides_closed_and_non_degree(fx):
    c = oc.Catalog(fx[1])
    assert {r["name"] for r in c.search_institutions()["results"]} == {"Alpha University", "Beta College", "No Site 100%_ College"}
    assert [r["name"] for r in c.search_institutions(state="ca")["results"]] == ["Alpha University"]
    assert [r["name"] for r in c.search_institutions(cip_keyword="economics")["results"]] == ["Beta College"]
    assert [r["name"] for r in c.search_institutions(q="AU")["results"]] == ["Alpha University"]  # alias
    assert len(c.search_institutions(active_only=False)["results"]) == 4
    assert [r["name"] for r in c.search_institutions(control="private_nonprofit")["results"]] == ["Beta College"]
    assert c.search_institutions(cip_keyword="biology", award="master")["total_matches"] == 0


def test_like_wildcards_are_escaped_and_bad_input_rejected(fx):
    c = oc.Catalog(fx[1])
    assert c.search_institutions(q="A%")["total_matches"] == 0
    assert [r["name"] for r in c.search_institutions(q="100%_")["results"]] == ["No Site 100%_ College"]
    for bad in ({"state": "California"}, {"control": "x"}, {"award": "phd"}):
        with pytest.raises(oc.CatalogError):
            c.search_institutions(**bad)


def test_every_result_carries_file_hash_provenance(fx):
    c = oc.Catalog(fx[1])
    prov = c.search_institutions()["provenance"]
    assert set(prov["files"]) == {"hd", "completions", "cip"} and all(len(v["sha256"]) == 64 for v in prov["files"].values())
    assert c.institution("1")["provenance"]["terms_url"] == oc.TERMS["url"] and c.institution("1")["provenance"]["terms_status"].startswith("UNCONFIRMED")


def test_url_normalisation_and_missing_url(fx):
    c = oc.Catalog(fx[1])
    assert c.institution("1")["official_url"] == "https://www.alpha.edu/" and c.institution("4")["official_url"] is None
    assert [s["id"] for s in c.schools_for_match(["1", "4", "999"])] == ["1"]  # no URL / unknown dropped, not invented
    s = c.schools_for_match(["1"])[0]
    assert s["annual_cost_usd"] is None and "Computer Science" in s["programs"]


def test_importer_rejects_schema_drift_and_missing_member(fx, tmp_path):
    files, _, _ = fx
    bad = dict(files)
    n, b = zipped("x.zip", "HD2024.csv", "A,B\n1,2\n")
    (tmp_path / "x.zip").write_bytes(b)
    bad["hd"] = tmp_path / "x.zip"
    with pytest.raises(oc.CatalogError, match="missing expected columns"):
        oc.import_catalog(bad, tmp_path / "o.sqlite")
    n, b = zipped("y.zip", "other.csv", HD)
    (tmp_path / "y.zip").write_bytes(b)
    bad["hd"] = tmp_path / "y.zip"
    with pytest.raises(oc.CatalogError, match="expected member"):
        oc.import_catalog(bad, tmp_path / "o2.sqlite")
    assert not (tmp_path / "o.sqlite").exists() and not (tmp_path / "o2.sqlite").exists()
    with pytest.raises(oc.CatalogError):
        oc.import_catalog({"hd": files["hd"]}, tmp_path / "o3.sqlite")


def test_sources_are_pinned_to_nces_https_only():
    for s in oc.SOURCES.values():
        assert s["url"].startswith("https://nces.ed.gov/")


def test_download_refuses_offhost_redirect_and_disables_proxy(tmp_path, monkeypatch):
    seen = {}
    class Cap:
        def open(self, req, timeout=0):
            raise RuntimeError("stop")
    monkeypatch.setattr(oc.urllib.request, "build_opener", lambda *handlers: (seen.setdefault("h", handlers), Cap())[1])
    with pytest.raises(RuntimeError):
        oc.download_sources(tmp_path)
    ph = [h for h in seen["h"] if isinstance(h, oc.urllib.request.ProxyHandler)]
    assert ph and ph[0].proxies == {}  # explicit empty proxy map: HTTP(S)_PROXY env ignored
    redirect = [h for h in seen["h"] if isinstance(h, type)][0]()
    for bad in ("https://evil.example/a.zip", "http://nces.ed.gov/a.zip"):
        with pytest.raises(oc.CatalogError, match="refused redirect"):
            redirect.redirect_request(None, None, 302, "", {}, bad)


class _Resp:
    def __init__(self, data):
        self.b = io.BytesIO(data)
    def read(self, n=-1):
        return self.b.read(n)
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _opener(data):
    class Op:
        def open(self, req, timeout=0):
            return _Resp(data)
    return Op()


def test_download_rejects_hash_mismatch_and_leaves_nothing(tmp_path):
    with pytest.raises(oc.CatalogError, match="!= pinned"):
        oc.download_sources(tmp_path, opener=_opener(b"tampered"))
    assert list(tmp_path.iterdir()) == []


def test_download_enforces_size_cap_while_streaming(tmp_path, monkeypatch):
    monkeypatch.setitem(oc.SOURCES["hd"], "max_bytes", 100)
    with pytest.raises(oc.CatalogError, match="size cap"):
        oc.download_sources(tmp_path, opener=_opener(b"x" * 100_000))
    assert list(tmp_path.iterdir()) == []


def test_download_accepts_exact_pinned_content(tmp_path, monkeypatch):
    data = b"fixture-bytes"
    for s in oc.SOURCES.values():
        monkeypatch.setitem(s, "sha256", hashlib.sha256(data).hexdigest())
    got = oc.download_sources(tmp_path, opener=_opener(data))
    assert set(got) == set(oc.SOURCES) and all(p.read_bytes() == data for p in got.values())
    assert not list(tmp_path.glob("*.part"))


def test_pins_are_full_sha256_and_sizes_bounded():
    for s in oc.SOURCES.values():
        assert len(s["sha256"]) == 64 and 0 < s["max_bytes"] <= 20_000_000


def test_routes_503_when_not_imported_then_work(fx, monkeypatch, tmp_path):
    client = TestClient(app)
    monkeypatch.setenv("ATLAS_CATALOG_DB", str(tmp_path / "nope.sqlite"))
    r = client.get("/api/v1/study-abroad/catalog/schools", headers=H)
    assert r.status_code == 503 and "not imported" in r.json()["detail"]
    monkeypatch.setenv("ATLAS_CATALOG_DB", str(fx[1]))
    r = client.get("/api/v1/study-abroad/catalog/schools?state=NY", headers=H).json()
    assert r["results"][0]["name"] == "Beta College"
    assert client.get("/api/v1/study-abroad/catalog/schools?state=NYC", headers=H).status_code == 422
    assert client.get("/api/v1/study-abroad/catalog/schools/999", headers=H).status_code == 404
    assert client.get("/api/v1/study-abroad/catalog/programs?q=comp", headers=H).json()["results"][0]["cip"] == "11.0701"
    assert client.get("/api/v1/study-abroad/catalog/programs?q=x", headers=H).status_code == 422
    assert client.get("/api/v1/study-abroad/catalog/coverage", headers=H).json()["institutions"] == 4


def test_school_match_from_catalog_uses_catalog_schools_and_reports_unresolved(fx, monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("ATLAS_CATALOG_DB", str(fx[1]))
    body = {"profile": {"goals": ["economics"], "annual_budget_usd": 1000}, "unitids": ["1", "2", "4", "999"]}
    r = client.post("/api/v1/study-abroad/school-match-from-catalog", headers=H, json=body).json()
    assert r["matches"][0]["name"] == "Beta College" and r["matches"][0]["affordable"] is None
    assert r["unresolved_unitids"] == ["4", "999"] and r["not_an_admission_prediction"] is True
    assert "No cost data" in r["catalog_note"]
    assert client.post("/api/v1/study-abroad/school-match-from-catalog", headers=H, json={"profile": {}, "unitids": ["999"]}).status_code == 404


REAL = Path(os.environ.get("ATLAS_REAL_CATALOG", "/nonexistent"))


@pytest.mark.skipif(not REAL.exists(), reason="real catalog not built here (set ATLAS_REAL_CATALOG); fixture tests above do not prove real-data behaviour")
def test_real_catalog_smoke():
    c = oc.Catalog(REAL)
    cov = c.coverage()
    assert cov["institutions"] > 5000 and cov["program_rows_without_cip_title"] == 0
    assert any("Stanford" in r["name"] for r in c.search_institutions(q="Stanford University", state="CA")["results"])
