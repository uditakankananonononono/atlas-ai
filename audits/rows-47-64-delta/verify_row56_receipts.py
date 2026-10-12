"""Offline check of row56_receipts.json: per-host request spacing >= max(1s, robots Crawl-delay), full robots text
present with its SHA-256 (sha256 of the stored text bytes equals the recorded sha256 when the text is UTF-8 clean),
and outcome consistency (page_reachable only with a 200 text/html page whose bytes were read)."""
import datetime, hashlib, json, sys
from collections import defaultdict
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "audits/rows-47-64-delta/row56_receipts.json"))
by = defaultdict(list); problems = []
for r in d["results"]:
    host = r["url"].split("/")[2]
    for k in ("robots", "page"):
        if k in r:
            by[host].append((datetime.datetime.fromisoformat(r[k]["requested_at"]), r[k]["spacing_applied_s"]))
    rb = r["robots"]
    if "text" in rb and rb.get("sha256") and hashlib.sha256(rb["text"].encode()).hexdigest() != rb["sha256"]:
        problems.append("%s: robots text does not rehash to recorded sha256 (non-UTF-8 bytes replaced on decode)" % r["id"])
    if r["outcome"] == "page_reachable":
        p = r["page"]
        if not (p["status"] == 200 and "text/html" in p["content_type"].lower() and p.get("sha256") and not p.get("too_large")):
            problems.append("%s: page_reachable without a read 200 text/html page" % r["id"])
for h, v in by.items():
    v.sort()
    for (a, _), (b, sp) in zip(v, v[1:]):
        if (b - a).total_seconds() < sp - 0.05:
            problems.append("%s: gap %.2fs < required %.1fs" % (h, (b - a).total_seconds(), sp))
print("links=%d hosts=%d problems=%d" % (len(d["results"]), len(by), len(problems)))
for p in problems: print(" -", p)
sys.exit(1 if problems else 0)
