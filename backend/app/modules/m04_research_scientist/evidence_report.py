"""Evidence compendium PDF from a research-loop result (REAL LaTeX compile, no authored prose).

What it is: retrieved metadata and full abstracts for papers the loop actually fetched, the
query trail, and corpus-relative term gaps, typeset by pdflatex. Page count follows the amount
of retrieved material.
What it is NOT: a written manuscript, review or analysis. No language model writes any text
here, so this does not meet a "40 page research paper" requirement. Non-ASCII characters are
transliterated or dropped (lossy); that is stated in the document.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata
from pathlib import Path

from .research_loop import LoopResult

_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
            "^": r"\textasciicircum{}", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}",
            "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}", '"': r"\textquotedbl{}",
            "'": r"\textquotesingle{}", "`": r"\textasciigrave{}", "-": "{-}"}  # no quote/dash ligatures


MAX_ABSTRACT_CHARS = 5000   # per paper; longer abstracts are cut WITH a visible notice
MAX_CONCURRENT_COMPILES = 2
_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_COMPILES)


class ReportError(RuntimeError):
    pass


class ReportBusy(ReportError):
    pass


def tex_escape(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    ascii_text = "".join(c if c in "\n\t" or 32 <= ord(c) < 127 else " " for c in ascii_text)
    out, run = [], 0
    for c in ascii_text:
        run = 0 if c.isspace() else run + 1
        out.append(_SPECIAL.get(c, c))
        if run and run % 20 == 0:
            out.append(r"\allowbreak{}")  # lets very long tokens and URLs wrap instead of overflowing
    return "".join(out)


def render_latex(res: LoopResult, gaps: list[dict] | None = None) -> str:
    out = [r"\documentclass[11pt]{article}", r"\usepackage[margin=1in]{geometry}",
           r"\usepackage[T1]{fontenc}",
           r"\IfFileExists{lmodern.sty}{\usepackage{lmodern}\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}\pdfgentounicode=1}{}}{}",
           r"\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}\sloppy\emergencystretch=3em",
           r"\begin{document}",
           r"\section*{Literature evidence compendium}",
           r"\textbf{Question:} " + tex_escape(res.question),
           r"\par\textbf{Status:} " + tex_escape(res.status) + " (" + tex_escape(res.stop_reason or "n/a") + r")",
           *([r"\par\textbf{INCOMPLETE:} the loop stopped early, so this list is partial."] if res.status != "complete" else []),
           r"\par This document lists retrieved records only. No text in it was written by a language model "
           r"and it contains no analysis, review or conclusion. Non-ASCII characters were transliterated or dropped. Text is typeset, not byte-faithful: the font may substitute ligatures such as fi and fl, and long words may be split. Copy and search extraction maps ligatures back to letters only when the lmodern font package is installed; without it, ff, fi and fl can be lost.",
           r"\section*{Query trail}"]
    out.append(r"\begin{itemize}" if res.steps else "No query steps were recorded.")
    for s in res.steps:
        out.append(rf"\item step {s.index}, {tex_escape(s.source)}: ``{tex_escape(s.query)}'' fetched {s.fetched}, new {len(s.new_paper_ids)}")
    out += [r"\end{itemize}" if res.steps else "", r"\section*{Retrieved papers (" + str(len(res.papers)) + ")}"]
    for p in res.papers.values():
        out.append(r"\subsection*{" + tex_escape(p.title) + "}")
        out.append(r"\textbf{ID:} " + tex_escape(p.paper_id) + r" \quad \textbf{Source:} " + tex_escape(p.source)
                   + r" \quad \textbf{Published:} " + tex_escape(p.published_at or "unknown"))
        if p.url:
            out.append(r"\par \textbf{URL:} " + tex_escape(str(p.url)))
        if p.keywords:
            out.append(r"\par \textbf{Keywords:} " + tex_escape(", ".join(p.keywords)))
        ab = p.abstract
        if len(ab) > MAX_ABSTRACT_CHARS:
            out.append(rf"\par \textbf{{Abstract (CLIPPED to {MAX_ABSTRACT_CHARS} of {len(ab)} characters, not full text):}} "
                       + tex_escape(ab[:MAX_ABSTRACT_CHARS]) + r" \textbf{[clipped]}")
        else:
            out.append(r"\par \textbf{Abstract (as retrieved):} " + tex_escape(ab))
    if gaps:
        out += [r"\section*{Corpus-relative term gaps (heuristic)}",
                r"Counts within the retrieved set only; not evidence of global novelty.", r"\begin{itemize}"]
        out += [r"\item " + tex_escape(g["statement"]) for g in gaps]
        out.append(r"\end{itemize}")
    out.append(r"\end{document}")
    return "\n".join(out)


def compile_pdf(tex: str, *, timeout: int = 60) -> tuple[bytes, int]:
    exe = shutil.which("pdflatex")
    if not exe:
        raise ReportError("pdflatex not installed")
    if not _SLOTS.acquire(blocking=False):
        raise ReportBusy("too many concurrent report compiles")
    try:
        return _compile(exe, tex, timeout)
    finally:
        _SLOTS.release()


def _compile(exe: str, tex: str, timeout: int) -> tuple[bytes, int]:
    with tempfile.TemporaryDirectory(prefix="atlas-tex-") as d:
        (Path(d) / "r.tex").write_text(tex, encoding="ascii")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": d, "openout_any": "p", "openin_any": "p",
               "TEXMFOUTPUT": d}
        try:
            proc = subprocess.run([exe, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
                                   "-output-directory", d, "r.tex"], cwd=d, env=env, capture_output=True,
                                  timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise ReportError("LaTeX compile timed out") from exc
        pdf = Path(d) / "r.pdf"
        if proc.returncode != 0 or not pdf.exists():
            raise ReportError("LaTeX compile failed")
        m = re.search(rb"\((\d+) pages?", proc.stdout)
        return pdf.read_bytes(), int(m.group(1)) if m else 0
