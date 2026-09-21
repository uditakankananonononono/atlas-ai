#!/usr/bin/env python3
"""Bring up the local stack and prove health, then always clean it up."""
import subprocess,time,urllib.request
project='atlas-acceptance'
try:
 subprocess.run(['docker','compose','-p',project,'up','-d','--build'],check=True)
 for _ in range(60):
  try:
   if urllib.request.urlopen('http://localhost:8000/health',timeout=2).status==200:break
  except Exception:time.sleep(2)
 else:raise SystemExit('API health did not become ready')
 subprocess.run(['docker','compose','-p',project,'ps'],check=True);print('compose acceptance passed')
finally:subprocess.run(['docker','compose','-p',project,'down','-v'],check=False)
