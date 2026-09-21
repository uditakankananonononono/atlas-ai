"""Server-side rotating refresh sessions; bearer access identity still comes from OIDC."""
from __future__ import annotations
import hashlib,secrets,time
from dataclasses import dataclass
@dataclass
class RefreshRecord:subject:str;tenant_id:str;expires_at:int;rotated:bool=False
class RefreshSessionStore:
 def __init__(self):self._records={}
 def issue(self,subject:str,tenant_id:str,ttl_seconds:int=2592000):
  if not subject or not tenant_id or ttl_seconds<=0:raise ValueError('subject, tenant and positive ttl required')
  token=secrets.token_urlsafe(48);self._records[hashlib.sha256(token.encode()).hexdigest()]=RefreshRecord(subject,tenant_id,int(time.time())+ttl_seconds);return token
 def rotate(self,token:str):
  key=hashlib.sha256(token.encode()).hexdigest();record=self._records.get(key);now=int(time.time())
  if record is None or record.rotated or record.expires_at<=now:raise PermissionError('refresh token invalid, expired or replayed')
  record.rotated=True;return self.issue(record.subject,record.tenant_id,record.expires_at-now)
 def revoke(self,token:str):
  record=self._records.get(hashlib.sha256(token.encode()).hexdigest())
  if record:record.rotated=True
