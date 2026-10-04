"""Rerunnable visual-regression RECIPE for M15 DOCX/PPTX delivery (skipped unless ATLAS_M15_VISUAL_OUT is set).
Usage: ATLAS_M15_VISUAL_OUT=/tmp/m15_vis PYTHONPATH=backend python -m pytest -q tests/modules/test_m15_visual_recipe.py
Produces FIXTURE-*.png via the real booted-app flow -> LibreOffice -> pdftoppm. Content is a LABELED FIXTURE (titles say so) so
it can never be mistaken for real user writing; outputs are NOT committed and NOT meant to be shown to users. A human/agent must
look at the PNGs; the test only asserts the pipeline produced non-empty images with some non-white pixels."""
import os
import shutil
import subprocess

import pytest

from tests.modules.test_m15_booted_app_delivery_flow import A, D, REPORT, _approve, client  # noqa: F401

OUT = os.getenv("ATLAS_M15_VISUAL_OUT")
pytestmark = pytest.mark.skipif(not OUT or not shutil.which("soffice") or not shutil.which("pdftoppm"),
                                reason="set ATLAS_M15_VISUAL_OUT and install soffice+pdftoppm")
FIG = {"id": "f1", "engine": "matplotlib", "kind": "line", "data": {"x": [1, 2, 3], "y": [20, 21, 22]},
       "options": {"title": "Depth"}, "alt_text": "FIXTURE chart alt text"}
CITE = {"key": "fix2025", "title": "LABELED FIXTURE source", "url": "https://example.invalid/x", "authors": ["Fixture Author"]}
DECK = {"title": "LABELED FIXTURE deck", "slides": [{"title": "Why", "bullets": ["clarity", "algae"], "notes": "n"},
                                                    {"title": "How", "body": "line one\nline two"}]}


def test_render_fixture_documents_to_png(client):  # noqa: F811
    c, _ = client
    os.makedirs(OUT, exist_ok=True)
    for fmt, content in (("docx", REPORT), ("pptx", DECK)):
        v = c.post(f"{D}/documents/vis-{fmt}/versions", headers=A, json={
            "title": "t", "format": fmt, "template_id": "report", "content": content, "figures": [FIG], "citations": [CITE]}).json()
        aid = c.post(f"{D}/versions/{v['id']}/export-proposals", headers=A).json()["approval_id"]
        assert _approve(c, A, aid).status_code == 200
        d = c.post(f"{D}/approvals/{aid}/deliver", headers=A).json()
        src = os.path.join(OUT, f"FIXTURE-{fmt}.{fmt}")
        open(src, "wb").write(c.get(d["download_url"], headers=A).content)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", OUT, src], capture_output=True,
                       timeout=100, env={"HOME": OUT, "PATH": "/usr/bin:/bin"}, check=True)
        subprocess.run(["pdftoppm", "-png", "-r", "60", os.path.join(OUT, f"FIXTURE-{fmt}.pdf"), os.path.join(OUT, f"FIXTURE-{fmt}")], check=True)
        pngs = sorted(p for p in os.listdir(OUT) if p.startswith(f"FIXTURE-{fmt}-") and p.endswith(".png"))
        assert pngs
        from PIL import Image
        for p in pngs:
            im = Image.open(os.path.join(OUT, p)).convert("L")
            assert im.getextrema()[0] < 200, f"{p} is blank"  # has non-white pixels (necessary, not sufficient)
