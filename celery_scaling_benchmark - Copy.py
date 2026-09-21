#!/usr/bin/env python3
import argparse,time
from concurrent.futures import ThreadPoolExecutor
from app.workers.tasks import dispatch_due_collection_sources
def main():
 p=argparse.ArgumentParser();p.add_argument('--requests',type=int,default=1000);p.add_argument('--concurrency',type=int,default=8);a=p.parse_args();start=time.perf_counter()
 with ThreadPoolExecutor(a.concurrency) as pool:list(pool.map(lambda _:dispatch_due_collection_sources.run(0),range(a.requests)))
 elapsed=time.perf_counter()-start;print({'requests':a.requests,'concurrency':a.concurrency,'seconds':elapsed,'throughput':a.requests/elapsed})
if __name__=='__main__':main()
