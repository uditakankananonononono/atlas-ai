"""Rebuild every shipped row and fail if any result differs. No writes to results."""
import argparse
import hashlib
import json
from pathlib import Path
from run import benchmark, summarize
from worlds import generate

ROOT = Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument("--suite", choices=("all", "clean", "noisy", "outside"), default="all")
args = parser.parse_args()
for name, count, seeds, noise, outside in (("clean", 100, 3, 0., False),
                                          ("noisy", 40, 2, .1, False),
                                          ("outside", 20, 2, 0., True)):
    if args.suite not in ("all", name):
        continue
    worlds = generate(91 if outside else 73, count, outside)
    rows = benchmark(worlds, seeds=seeds, noise=noise)
    text = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
    assert text == (ROOT / "results" / name / "rows.jsonl").read_text(), name
    assert summarize(rows) == (ROOT / "results" / name / "analysis.txt").read_text(), name
    print(name, "byte-identical", hashlib.sha256(text.encode()).hexdigest(), flush=True)
