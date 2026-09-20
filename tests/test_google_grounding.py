import asyncio,httpx
from app.integrations.google_grounding import GoogleWorkspaceGrounder

def test_google_docs_official_api_extracts_text_with_revision_provenance():
 def handler(r):
  assert r.url.host=="docs.googleapis.com" and r.headers["Authorization"]=="Bearer owner-token"
  return httpx.Response(200,json={"title":"Projects","revisionId":"rev-9","body":{"content":[{"paragraph":{"elements":[{"textRun":{"content":"Project Atlas\n"}}]}}]}})
 async def run():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await GoogleWorkspaceGrounder("owner-token",c).document("doc1")
 out=asyncio.run(run());assert out.text=="Project Atlas" and out.provenance["revision_id"]=="rev-9"

def test_google_sheets_official_api_preserves_a1_ranges_and_values():
 def handler(r):
  assert r.url.host=="sheets.googleapis.com"
  assert r.url.params.get_list("ranges")==["Projects!A1:B2"]
  return httpx.Response(200,json={"valueRanges":[{"range":"Projects!A1:B2","majorDimension":"ROWS","values":[["name","status"],["Atlas","active"]]}]})
 async def run():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await GoogleWorkspaceGrounder("t",c).sheet("sheet1",["Projects!A1:B2"])
 out=asyncio.run(run())[0];assert out.locator=="Projects!A1:B2" and "Atlas\tactive" in out.text

def test_google_grounding_requires_owner_oauth_and_sheet_range(monkeypatch):
 monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN",raising=False);g=GoogleWorkspaceGrounder()
 try:
  try:asyncio.run(g.document("doc"))
  except RuntimeError as e:assert "not configured" in str(e)
  else:raise AssertionError("missing OAuth should fail")
  try:asyncio.run(g.sheet("s",[]))
  except ValueError as e:assert "A1 range" in str(e)
  else:raise AssertionError("empty ranges should fail")
 finally:asyncio.run(g.close())
