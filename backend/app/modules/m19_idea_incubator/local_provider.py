"""M19 uses an explicitly configured local model, never a paid fallback."""
import os
from urllib.parse import urlsplit
import httpx
from app.core.providers import ProviderError

async def generate_local(prompt, provider='ollama', model=None):
    if provider not in {'ollama','local'}:
        raise ProviderError('M19 supports local Ollama only; hosted providers are disabled')
    chosen=model or os.getenv('ATLAS_M19_MODEL') or os.getenv('ATLAS_OLLAMA_MODEL')
    if not chosen or any(c in chosen for c in '\r\n'):
        raise ProviderError('configure ATLAS_M19_MODEL with an installed Ollama model')
    base=os.getenv('ATLAS_M19_OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
    url=urlsplit(base)
    if url.scheme!='http' or url.hostname not in {'localhost','127.0.0.1','::1','ollama'} or url.username or url.password or url.query or url.fragment or url.path:
        raise ProviderError('M19 Ollama URL must be a local HTTP origin (loopback or compose ollama)')
    try:
        async with httpx.AsyncClient(timeout=90,trust_env=False,follow_redirects=False) as client:
            response=await client.post(base+'/api/chat',json={'model':chosen,'stream':False,'format':'json','messages':[{'role':'user','content':prompt}]})
        if response.is_error: raise ProviderError(f'local Ollama returned HTTP {response.status_code}; check installed model')
        data=response.json(); text=data['message']['content']
        if not isinstance(text,str) or not text.strip(): raise ValueError()
        return chosen,text
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        raise ProviderError('local Ollama unavailable or response invalid; no fallback used') from exc
