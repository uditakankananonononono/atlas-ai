import asyncio, httpx
from app.core.embeddings import OllamaBGEEmbeddingProvider, OpenAIEmbeddingProvider, get_embedding_provider

def test_default_provider_is_openai(monkeypatch):
    monkeypatch.delenv("ATLAS_EMBEDDING_PROVIDER", raising=False)
    assert isinstance(get_embedding_provider(), OpenAIEmbeddingProvider)

def test_ollama_adapter(monkeypatch):
    real = httpx.AsyncClient
    def handler(request):
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
    monkeypatch.setattr("app.core.embeddings.httpx.AsyncClient", lambda **_: real(transport=httpx.MockTransport(handler)))
    assert asyncio.run(OllamaBGEEmbeddingProvider("http://local").embed(["text"])) == [[0.1, 0.2]]
