#!/usr/bin/env python3
"""Bounded stdlib load probe; use only against an explicitly approved target."""
import argparse,concurrent.futures,json,time,urllib.request
p=argparse.ArgumentParser(); p.add_argument("url"); p.add_argument("--requests",type=int,default=20); p.add_argument("--concurrency",type=int,default=4); a=p.parse_args()
if not 1<=a.requests<=10000 or not 1<=a.concurrency<=100: p.error("bounded positive requests/concurrency required")
def hit(_):
 t=time.perf_counter()
 try:
  with urllib.request.urlopen(a.url,timeout=10) as r: return r.status,time.perf_counter()-t
 except Exception:return 0,time.perf_counter()-t
with concurrent.futures.ThreadPoolExecutor(a.concurrency) as ex: out=list(ex.map(hit,range(a.requests)))
lat=sorted(x[1] for x in out); ok=sum(200<=s<500 for s,_ in out)
print(json.dumps({"requests":len(out),"successful":ok,"p95_seconds":lat[max(0,int(len(lat)*.95)-1)]},sort_keys=True))
