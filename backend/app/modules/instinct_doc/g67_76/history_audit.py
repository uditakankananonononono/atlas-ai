"""Group 74: audit historic chat requests against repo evidence.

Parses a WhatsApp export ("[d/m/yy, h:mm:ss AM] Name: text" or
"d/m/yy, h:mm - Name: text"), keeps the owner's request-like lines, then
searches the repo tree for evidence tokens. Verdict is FOUND only when >=2
distinctive tokens hit in the same file; otherwise NO_EVIDENCE. This measures
textual evidence, not whether the feature works.
"""
from __future__ import annotations
import os, re
from collections import Counter

LINE = re.compile(r"^(?:\[(\d{1,2}/\d{1,2}/\d{2,4}),? [^\]]*\]|(\d{1,2}/\d{1,2}/\d{2,4}),? [\d:]+(?: [AP]M)? -) ([^:]+): (.*)$")
REQ = re.compile(r"\b(build|make|add|implement|create|deploy|integrate|fix|ensure|apply|find|send|set up|delete)\b", re.I)
STOP = set("the and for you that with this have not all can will from your are but our any into then them what when also more only make build add".split())


def parse(text, owner):
    out = []
    for ln in text.splitlines():
        m = LINE.match(ln)
        if m and m.group(3).strip().lower() == owner.lower() and REQ.search(m.group(4)):
            out.append({"date": m.group(1) or m.group(2), "text": m.group(4).strip()})
    return out


def _index(root, exts=(".py", ".ts", ".tsx", ".md")):
    files = {}
    for d, _, fs in os.walk(root):
        if ".git" in d or "node_modules" in d:
            continue
        for f in fs:
            if f.endswith(exts):
                p = os.path.join(d, f)
                try:
                    files[p] = set(re.findall(r"[a-z][a-z0-9]{3,}", open(p, errors="ignore").read().lower()))
                except OSError:
                    pass
    return files


def audit(requests, root):
    files = _index(root)
    df = Counter(t for s in files.values() for t in s)
    rows = []
    for r in requests:
        toks = [t for t in set(re.findall(r"[a-z][a-z0-9]{3,}", r["text"].lower())) if t not in STOP]
        toks = [t for t in toks if 0 < df[t] <= max(3, len(files) // 20)]  # distinctive only
        best, best_n = None, 0
        for p, s in files.items():
            n = sum(1 for t in toks if t in s)
            if n > best_n:
                best, best_n = p, n
        rows.append({**r, "tokens": sorted(toks), "verdict": "FOUND" if best_n >= 2 else "NO_EVIDENCE",
                     "file": best if best_n >= 2 else None, "hits": best_n})
    return {"total": len(rows), "found": sum(r["verdict"] == "FOUND" for r in rows), "rows": rows}
