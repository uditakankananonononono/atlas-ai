"""Fixed, patch-independent line mutant generator (frozen before any scoring)."""
import ast
import re

SUBS = [(" < ", " <= "), (" <= ", " < "), (" > ", " >= "), (" >= ", " > "),
        (" == ", " != "), (" != ", " == "), (" + ", " - "), (" - ", " + "),
        (" * ", " + "), (" // ", " / "), (" and ", " or "), (" or ", " and "),
        ("True", "False"), ("False", "True"), (" not in ", " in "),
        ("max(", "min("), ("min(", "max("), ("sorted(", "list("), ('.strip("-")', ""),
        ("-kv[1]", "kv[1]"), (" += ", " -= "), ("reversed(", "list(")]


def generate(src: str):
    lines = src.split("\n")
    seen = {}
    for l in lines:
        seen[l] = seen.get(l, 0) + 1
    out = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("def ", "import ", "from ", "#", "@")) or seen[line] > 1:
            continue
        cands = []
        for a, b in SUBS:
            if a in line:
                cands.append(line.replace(a, b, 1))
        r = re.match(r"(\s*)return (.+)$", line)
        if r and r.group(2) not in ("None", "True", "False"):
            cands.append(r.group(1) + "return None")
        m = re.search(r"(?<![\w.\[])(\d+)(?![\w.])", line)
        if m:
            cands.append(line[:m.start()] + str(int(m.group(1)) + 1) + line[m.end():])
        for c in cands:
            if c == line:
                continue
            new_src = src.replace("\n" + line, "\n" + c, 1) if ("\n" + line) in src else None
            if new_src is None:
                continue
            try:
                ast.parse(new_src)
            except SyntaxError:
                continue
            out.append(("\n" + line, "\n" + c))
    return out
