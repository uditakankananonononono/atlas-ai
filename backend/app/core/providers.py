import os
import httpx

class ProviderError(RuntimeError):
    pass

async def generate(prompt: str, provider: str, model: str | None = None) -> tuple[str, str]:
    """Call an LLM with a user-supplied environment key. Keys are never returned or logged."""
    provider = provider.lower()
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ProviderError("OPENAI_API_KEY is not configured")
        chosen = model or os.getenv("ATLAS_OPENAI_MODEL", "gpt-4o-mini")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": chosen, "messages": [{"role": "user", "content": prompt}]},
            )
        if response.is_error:
            raise ProviderError(f"OpenAI request failed ({response.status_code})")
        return chosen, response.json()["choices"][0]["message"]["content"]
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured")
        chosen = model or os.getenv("ATLAS_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": chosen, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]},
            )
        if response.is_error:
            raise ProviderError(f"Anthropic request failed ({response.status_code})")
        return chosen, "".join(block["text"] for block in response.json()["content"] if block["type"] == "text")
    raise ProviderError(f"Unsupported provider: {provider}")
