"""Real official adapter methods with httpx.MockTransport, never live posting."""
import asyncio
import unittest
import httpx
from app.modules.m06_social_media_manager.adapters import LinkedInAdapter,TikTokContentPostingAdapter,PublishRequest,AdapterResponseError

class ReceiptBoundary(unittest.TestCase):
 def linkedin(self,headers=None,status=201,body=b''):
  transport=httpx.MockTransport(lambda req:httpx.Response(status,headers=headers,content=body))
  return LinkedInAdapter(access_token='synthetic',organization_id='synthetic',transport=transport)
 def li_request(self):return PublishRequest('linkedin','Synthetic','article_post')
 def tt_request(self):return PublishRequest('tiktok','Synthetic','video',media_urls=('https://example.invalid/video',))
 def tiktok(self,body,seen=None):
  def handle(req):
   if seen is not None:seen.append(req)
   return httpx.Response(200,json=body)
  return TikTokContentPostingAdapter(access_token='synthetic',transport=httpx.MockTransport(handle))
 def test_linkedin_empty_body_creation_header_is_success(self):
  a=asyncio.run(self.linkedin({'X-RestLi-Id':'urn:li:share:123'}).publish(self.li_request()))
  self.assertEqual(a.external_id,'urn:li:share:123');self.assertFalse(a.draft_only)
 def test_linkedin_missing_or_empty_header_not_success(self):
  for headers in [None,{'x-restli-id':''},{'x-restli-id':' '},{'x-restli-id':'x'*513}]:
   with self.subTest(headers=headers is None):
    with self.assertRaises(AdapterResponseError):asyncio.run(self.linkedin(headers).publish(self.li_request()))
 def test_linkedin_body_id_not_substitute_for_creation_header(self):
  with self.assertRaises(AdapterResponseError):asyncio.run(self.linkedin(body=b'{"id":"synthetic"}').publish(self.li_request()))
 def test_linkedin_non_creation_status_not_success(self):
  with self.assertRaises(AdapterResponseError):asyncio.run(self.linkedin({'x-restli-id':'synthetic'},status=200).publish(self.li_request()))
 def test_tiktok_missing_or_invalid_id_is_not_success(self):
  for value in [None,'',' ',True,[],{},'x'*65]:
   with self.subTest(kind=type(value).__name__):
    with self.assertRaises(AdapterResponseError):asyncio.run(self.tiktok({'error':{'code':'ok'},'data':{'publish_id':value}}).publish(self.tt_request()))
 def test_tiktok_missing_or_error_envelope_is_not_success(self):
  for body in [{},{'data':{'publish_id':'synthetic'}},{'error':{'code':'invalid_param'},'data':{'publish_id':'synthetic'}},{'error':{'code':'ok'},'data':[]},{'error':[],'data':{'publish_id':'synthetic'}}]:
   with self.assertRaises(AdapterResponseError):asyncio.run(self.tiktok(body).publish(self.tt_request()))
 def test_tiktok_official_init_endpoint_and_draft_receipt(self):
  seen=[]
  a=asyncio.run(self.tiktok({'data':{'publish_id':'v_pub_123'},'error':{'code':'ok'}},seen).publish(self.tt_request()))
  self.assertEqual(a.external_id,'v_pub_123');self.assertTrue(a.draft_only)
  self.assertEqual(seen[0].url.path,'/v2/post/publish/inbox/video/init/')
  self.assertEqual(seen[0].method,'POST')
 def test_missing_credentials_still_refuse_without_transport(self):
  calls=[]
  def send(req):calls.append(req);raise AssertionError('must not dispatch')
  from app.modules.m06_social_media_manager.adapters import AdapterAuthError
  a=LinkedInAdapter(access_token=None,organization_id='synthetic',transport=httpx.MockTransport(send))
  with self.assertRaises(AdapterAuthError):asyncio.run(a.publish(self.li_request()))
  self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
