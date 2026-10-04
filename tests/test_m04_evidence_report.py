import shutil, subprocess
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist import evidence_report as er, research_loop as rl, routes
from app.modules.m04_research_scientist.schemas import PaperInput

pytestmark = pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex not installed")

def paper(i, title="Title", abstract="An abstract that is long enough to count."):
    return PaperInput(paper_id=f"arxiv:{i}", title=title, abstract=abstract, source="arxiv",
                      url=f"https://arxiv.org/abs/2610.{i:05d}", keywords=["a_b", "c&d"], published_at="2026-10-01")

def result(papers, steps=()):
    return rl.LoopResult(question="Does $x_1 & y matter?", steps=list(steps), papers={p.paper_id: p for p in papers}, stop_reason="max_steps")

def text_of(pdf, tmp_path):
    f = tmp_path / "o.pdf"; f.write_bytes(pdf)
    return subprocess.run(["pdftotext", str(f), "-"], capture_output=True, text=True).stdout

def test_special_chars_and_injection_stay_literal_and_pdf_compiles(tmp_path):
    p = paper(1, title=r"Weird $t_ {x} #%& ^ ~ \ é <b>", abstract=r"abstract \input{/etc/passwd} \write18{id} text " * 5)
    pdf, pages = er.compile_pdf(er.render_latex(result([p])))
    t = text_of(pdf, tmp_path)
    assert pdf.startswith(b"%PDF-") and pages >= 1
    flat = t.replace("\n", "").replace("-", "")
    assert "root:" not in t and "/etc/passwd" in flat and "write18" in flat
    assert "Does $x_1 & y matter?" in t

def test_page_count_scales_with_retrieved_material_and_is_labelled_not_authored(tmp_path):
    _, small = er.compile_pdf(er.render_latex(result([paper(1)])))
    big_p = [paper(i, abstract="word " * 400) for i in range(1, 25)]
    pdf, big = er.compile_pdf(er.render_latex(result(big_p)))
    assert big > small >= 1
    assert "No text in it was written by a language model" in text_of(pdf, tmp_path)

def test_empty_steps_and_no_papers_still_compile():
    pdf, pages = er.compile_pdf(er.render_latex(result([])))
    assert pdf.startswith(b"%PDF-")

def test_nonascii_is_transliterated_lossy_and_stated(tmp_path):
    pdf, _ = er.compile_pdf(er.render_latex(result([paper(1, title="Caf\u00e9 \u4e2d\u6587")])))
    t = text_of(pdf, tmp_path)
    assert "Cafe" in t and "transliterated or dropped" in t

def test_compile_failure_and_timeout_are_report_errors():
    with pytest.raises(er.ReportError):
        er.compile_pdf(r"\documentclass{article}\begin{document}\undefinedcmd\end{document}")
    with pytest.raises(er.ReportError):
        er.compile_pdf(r"\documentclass{article}\begin{document}\loop\end{document}".replace(r"\loop", r"\def\a{\a\a}\a"), timeout=1)

def test_shell_escape_is_disabled(tmp_path):
    marker = tmp_path / "pwn"
    try:
        er.compile_pdf(r"\documentclass{article}\begin{document}\immediate\write18{touch %s}x\end{document}" % marker)
    except er.ReportError:
        pass
    assert not marker.exists()

def test_route_returns_pdf_with_labels(monkeypatch):
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m04_research_scientist import arxiv_collector as ac
    ps = [paper(i, title=f"Tumor niche {i}", abstract="spatial tumor niche mapping study text " * 3) for i in range(1, 4)]
    monkeypatch.setattr(ac, "collect_arxiv", lambda q, n: ps)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    r = TestClient(app).post("/research-scientist/research-loop/report", json={"question": "immune niches tumor spatial", "max_steps": 1})
    assert r.status_code == 200 and r.content.startswith(b"%PDF-") and r.headers["x-report-kind"].endswith("not-authored")
    assert int(r.headers["x-report-pages"]) >= 1

def test_route_503_when_pdflatex_missing(monkeypatch):
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m04_research_scientist import arxiv_collector as ac
    monkeypatch.setattr(ac, "collect_arxiv", lambda q, n: [paper(1)])
    monkeypatch.setattr(er.shutil, "which", lambda x: None)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t", actor_id="u")
    r = TestClient(app).post("/research-scientist/research-loop/report", json={"question": "immune niches tumor spatial", "max_steps": 1})
    assert r.status_code == 503 and "pdflatex" not in r.text

def test_unbalanced_braces_are_escaped_not_a_compile_failure(tmp_path):
    pdf, _ = er.compile_pdf(er.render_latex(result([paper(1, title="open { brace", abstract="close } brace and { again here")])))
    assert "open { brace" in text_of(pdf, tmp_path)

def test_long_tokens_wrap_instead_of_overflowing(tmp_path):
    p = paper(1, abstract="start " + "x" * 200 + " https://example.org/" + "a" * 150 + " end")
    pdf, _ = er.compile_pdf(er.render_latex(result([p])))
    f = tmp_path / "w.pdf"; f.write_bytes(pdf)
    out = subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True, text=True).stdout
    assert max(len(line) for line in out.splitlines()) < 140  # an unwrapped 200-char token would exceed this

def test_incomplete_banner_only_when_not_complete(tmp_path):
    r = result([paper(1)])
    assert "INCOMPLETE" not in er.render_latex(r)
    r.status = "partial"
    assert "INCOMPLETE" in er.render_latex(r)

def test_long_run_gets_break_points_and_short_text_does_not():
    assert er.tex_escape("x" * 200).count(r"\allowbreak{}") == 10
    assert r"\allowbreak" not in er.tex_escape("short words only")
    assert er.tex_escape("x" * 20 + " " + "y" * 20).count(r"\allowbreak{}") == 2  # run resets at spaces

def test_quotes_dashes_and_backticks_are_not_turned_into_ligatures(tmp_path):
    p = paper(1, abstract="He said \"hi\" and ''quoted'' with `tick` and a--b and c---d and e-f ok.")
    t = text_of(er.compile_pdf(er.render_latex(result([p])))[0], tmp_path).replace("\n", " ")
    for frag in ('"hi"', "''quoted''", "`tick`", "a--b", "c---d", "e-f"):
        assert frag in t, frag

def test_long_abstract_truncated_with_visible_notice(tmp_path):
    n = er.MAX_ABSTRACT_CHARS + 777
    p = paper(1, abstract="w" * 10 + (" word" * (n // 5)))
    tex = er.render_latex(result([p]))
    assert f"showing {er.MAX_ABSTRACT_CHARS} of {len(p.abstract)} characters" in tex
    short = paper(2, abstract="short enough abstract for this paper")
    assert "truncated" not in er.render_latex(result([short]))

def test_concurrent_compiles_are_bounded():
    held = [er._SLOTS.acquire(blocking=False) for _ in range(er.MAX_CONCURRENT_COMPILES)]
    try:
        with pytest.raises(er.ReportBusy):
            er.compile_pdf(er.render_latex(result([paper(1)])))
    finally:
        for h in held:
            if h: er._SLOTS.release()
    er.compile_pdf(er.render_latex(result([paper(1)])))  # slot released again after use
