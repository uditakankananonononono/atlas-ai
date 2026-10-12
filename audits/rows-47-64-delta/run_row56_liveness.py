"""Row 56 receipts runner. Read-only, public pages only. Run from backend/:
    python ../audits/rows-47-64-delta/run_row56_liveness.py ../audits/rows-47-64-delta/row56_receipts.json
For each of the 20 publisher links: fetch robots.txt first (refuse if not 200 or disallowed), then the page.
No redirects followed, bodies bounded (decoded-retained bound; transport peak not bounded), 1s spacing between
HTTP requests, no content stored beyond a SHA-256 and byte count, robots text kept (<=20KB) as the receipt.
Challenges, 403s and redirects are recorded and NOT bypassed."""
import datetime
import hashlib
import json
import sys
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.modules.m23_study_abroad.admitted_cases import USER_AGENT, cases
from app.modules.m23_study_abroad.admitted_cases_bounded import (PAGE_LIMIT_BYTES, ROBOTS_LIMIT_BYTES, TIMEOUT_SECONDS,
                                                                  BodyTooLarge, read_bounded)

LAST = [0.0]


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def get(client, url, limit):
    wait = 1.0 - (time.monotonic() - LAST[0])
    if wait > 0:
        time.sleep(wait)
    started, t0 = stamp(), time.monotonic()
    LAST[0] = t0
    rec = {"url": url, "requested_at": started}
    with client.stream("GET", url) as r:
        rec.update(status=r.status_code, content_type=r.headers.get("content-type", ""), location=r.headers.get("location"))
        if r.status_code == 200:
            try:
                body = read_bounded(r, limit)
            except BodyTooLarge:
                rec["too_large"] = True
                return rec, None
            rec.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            return rec, body
    return rec, None


def main(out):
    results = []
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        for c in cases():
            p = urlparse(c["url"])
            row = {"id": c["id"], "publisher": c["publisher"], "url": c["url"]}
            try:
                rrec, rbody = get(client, f"{p.scheme}://{p.netloc}/robots.txt", ROBOTS_LIMIT_BYTES)
                row["robots"] = {k: v for k, v in rrec.items() if k != "url"}
                if rbody is None:
                    row["outcome"] = "robots_unverified"
                else:
                    text = rbody.decode("utf-8", errors="replace")
                    row["robots"]["text"] = text[:20000]
                    rp = RobotFileParser(); rp.parse(text.splitlines())
                    if not rp.can_fetch(USER_AGENT, c["url"]):
                        row["outcome"] = "robots_denied"
                    else:
                        prec, pbody = get(client, c["url"], PAGE_LIMIT_BYTES)
                        row["page"] = {k: v for k, v in prec.items() if k != "url"}
                        row["outcome"] = ("page_reachable" if prec["status"] == 200 and "text/html" in prec["content_type"].lower()
                                          else "unavailable_or_unsupported")
            except (httpx.HTTPError, ValueError, UnicodeError) as exc:
                row["outcome"] = "fetch_failed"; row["error_class"] = type(exc).__name__
            results.append(row)
    json.dump({"run_at": stamp(), "user_agent": USER_AGENT, "results": results}, open(out, "w"), indent=1)
    from collections import Counter
    print(Counter(r["outcome"] for r in results))


if __name__ == "__main__":
    main(sys.argv[1])
