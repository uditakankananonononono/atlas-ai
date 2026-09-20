import os
from abc import ABC, abstractmethod
import httpx

class EmbeddingError(RuntimeError):
    pass

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("ATLAS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingError("OPENAI_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post("https://api.openai.com/v1/embeddings", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "input": texts, "dimensions": 1024})
        if response.is_error:
            raise EmbeddingError(f"OpenAI embeddings failed ({response.status_code})")
        return [item["embedding"] for item in sorted(response.json()["data"], key=lambda item: item["index"])]

class OllamaBGEEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("ATLAS_OLLAMA_URL", "http://ollama:11434")).rstrip("/")
        self.model = model or os.getenv("ATLAS_OLLAMA_EMBEDDING_MODEL", "bge-m3")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts, "truncate": True})
        if response.is_error:
            raise EmbeddingError(f"Ollama embeddings failed ({response.status_code})")
        return response.json()["embeddings"]

def get_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    selected = (name or os.getenv("ATLAS_EMBEDDING_PROVIDER", "openai")).lower()
    if selected == "openai":
        return OpenAIEmbeddingProvider()
    if selected in {"ollama", "bge", "local"}:
        return OllamaBGEEmbeddingProvider()
    raise EmbeddingError(f"unsupported embedding provider: {selected}")
