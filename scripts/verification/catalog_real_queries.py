import json, os, sys
from fastapi.testclient import TestClient
os.environ["ATLAS_CATALOG_DB"] = sys.argv[1]
from app.main import app
c = TestClient(app); H = {"x-atlas-tenant": "real-run", "x-atlas-actor": "student"}; B = "/api/v1/study-abroad/"
def show(t, r): print("##", t, r.status_code); return r.json()
j = show("search Stanford CA", c.get(B + "catalog/schools?q=Stanford&state=CA", headers=H)); print(json.dumps(j["results"], indent=1)[:900], j["total_matches"])
j = show("economics bachelor, public, NY", c.get(B + "catalog/schools?program=economics&award=bachelor&control=public&state=NY&limit=5", headers=H)); print([r["name"] for r in j["results"]], j["total_matches"])
j = show("programs 'computer science'", c.get(B + "catalog/programs?q=computer science&limit=3", headers=H)); print(json.dumps(j["results"], indent=1))
ids = [r["unitid"] for r in c.get(B + "catalog/schools?program=economics&award=bachelor&state=NY&limit=6", headers=H).json()["results"]]
j = show("match", c.post(B + "school-match-from-catalog", headers=H, json={"profile": {"goals": ["economics"], "interests": ["policy"]}, "unitids": ids}))
print([(m["name"], m["score"], m["affordable"], m["official_url"]) for m in j["matches"]]); print(j["catalog_note"])
show("unknown", c.get(B + "catalog/schools/0", headers=H))
