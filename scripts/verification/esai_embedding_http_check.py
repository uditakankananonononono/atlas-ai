"""Real local embedding model through the real HTTP route (TestClient), one prompt. No quality claim."""
import json, os
from fastapi.testclient import TestClient
from app.main import app
ev = [{"label": "Shelter", "description": "I walk dogs at the animal shelter every weekend", "values": []},
      {"label": "Robotics", "description": "I rebuilt our robot's drive train overnight before regionals", "values": []},
      {"label": "Pantry", "description": "I schedule volunteers at the neighborhood food pantry", "values": []}]
r = TestClient(app).post("/api/v1/study-abroad/essay-tools/topics", headers={"x-atlas-tenant": "real-emb", "x-atlas-actor": "student"},
                         json={"prompt": "Tell us about a time you overcame a setback.", "evidence": ev})
j = r.json()
print(r.status_code, os.environ.get("INSTINCT_EMBED_MODEL"), j["match_mode"],
      [(c["label"], c.get("embedding_similarity")) for c in j["candidates"]])
