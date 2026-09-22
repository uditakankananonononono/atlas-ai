import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.core import providers
from app.platform.integrations import RedisStreamBus


class Redis:
    def __init__(self): self.rows=[]
    def xadd(self,stream,fields,**kwargs):
        event_id=f'{len(self.rows)+1}-0';self.rows.append((event_id,fields));return event_id
    def xread(self,cursors,**kwargs):
        last=int(next(iter(cursors.values())).split('-')[0])
        return [('atlas.events',[(i,f) for i,f in self.rows if int(i.split('-')[0])>last])]


def test_a12_real_redis_stream_adapter_serializes_and_resumes_after_cursor():
    client=Redis();bus=RedisStreamBus(client=client)
    first=bus.publish('atlas.events',{'type':'created','id':1})
    second=bus.publish('atlas.events',{'type':'created','id':2})
    assert first=='1-0' and second=='2-0'
    assert bus.read('atlas.events',last_id=first)==[{'id':'2-0','event':{'type':'created','id':2}}]
    assert json.loads(client.rows[0][1]['json'])=={'type':'created','id':1}


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,key,url,response,expected',[
 ('openai','OPENAI_API_KEY','api.openai.com',{'choices':[{'message':{'content':'openai ok'}}],'usage':{}},'openai ok'),
 ('anthropic','ANTHROPIC_API_KEY','api.anthropic.com',{'content':[{'type':'text','text':'anthropic ok'}],'usage':{}},'anthropic ok'),
 ('gemini','GEMINI_API_KEY','generativelanguage.googleapis.com',{'candidates':[{'content':{'parts':[{'text':'gemini ok'}]}}],'usageMetadata':{}},'gemini ok'),
 ('deepseek','DEEPSEEK_API_KEY','api.deepseek.com',{'choices':[{'message':{'content':'deepseek ok'}}],'usage':{}},'deepseek ok'),
])
async def test_a15_provider_adapters_send_real_provider_schema(monkeypatch,provider,key,url,response,expected):
    monkeypatch.setenv(key,'test-key')
    seen=[]
    async def fake_post(name,target,**kwargs): seen.append((name,target,kwargs));return response
    monkeypatch.setattr(providers,'_post',fake_post)
    _,text=await providers.generate('hello',provider)
    assert text==expected and seen[0][0] in {provider,'gemini'} and url in seen[0][1]
    payload=seen[0][2]['payload']
    assert ('messages' in payload) or ('contents' in payload)


@pytest.mark.asyncio
async def test_a15_ollama_uses_local_chat_endpoint_and_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv('ATLAS_OLLAMA_URL','http://ollama.test:11434')
    seen=[]
    async def fake_post(name,target,**kwargs): seen.append(target);return {'message':{'content':'local ok'}}
    monkeypatch.setattr(providers,'_post',fake_post)
    _,text=await providers.generate('hello','ollama','llama3.1:70b')
    assert text=='local ok' and seen==['http://ollama.test:11434/api/chat']
    with pytest.raises(providers.ProviderError,match='Unsupported provider'):
        await providers.generate('hello','invented-provider')


def test_a16_playwright_dependency_and_real_browser_e2e_config():
    package=json.loads(Path('frontend/package.json').read_text())
    config=Path('frontend/playwright.config.ts').read_text()
    journey=Path('frontend/e2e/guided-journeys.spec.ts').read_text()
    assert package['devDependencies']['@playwright/test'].startswith('^1.')
    assert "name:'chromium'" in config and 'webServer' in config
    assert 'page.goto' in journey and 'page.route' in journey and 'expect(' in journey


def test_a17_selenium_is_installed_as_fallback_not_default_browser_path():
    assert int(__import__('importlib').metadata.version('selenium').split('.')[0])==4
    config=Path('frontend/playwright.config.ts').read_text()
    assert 'chromium' in config and 'selenium' not in config.lower()
