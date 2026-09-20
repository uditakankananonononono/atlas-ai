import json
from pathlib import Path
def test_frontend_has_buildable_manifest_and_xyflow():
 p=json.loads(Path("frontend/package.json").read_text());assert p["scripts"]["build"]=="next build" and "@xyflow/react" in p["dependencies"]
def test_frontend_is_in_production_compose():assert "  web:" in Path("docker-compose.prod.yml").read_text()
