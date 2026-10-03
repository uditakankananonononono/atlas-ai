"""python -m app.modules.m23_study_abroad.official_catalog_cli import [--dir DIR] [--db PATH] [--download]
Imports the pinned NCES public files. --download fetches only https://nces.ed.gov URLs (no login/key)."""
import argparse, json
from pathlib import Path
from . import official_catalog as oc

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["import", "coverage"])
    ap.add_argument("--dir", default="backend/data/source_files")
    ap.add_argument("--db", default="backend/data/official_catalog.sqlite")
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args(argv)
    db = Path(a.db)
    if a.cmd == "coverage":
        print(json.dumps(oc.Catalog(db).coverage(), indent=1)); return
    d = Path(a.dir)
    files = oc.download_sources(d) if a.download else {k: d / Path(s["url"]).name for k, s in oc.SOURCES.items()}
    db.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(oc.import_catalog(files, db), indent=1))

if __name__ == "__main__":
    main()
