"""Configured Google OAuth refresh exchange. Never logs tokens or response bodies."""
from __future__ import annotations
import os
import httpx
from .google_calendar import UpstreamServiceError


class GoogleRefreshExchange:
    def __init__(self, client: httpx.AsyncClient, client_id: str | None = None,
                 client_secret: str | None = None) -> None:
        self.client = client
        self.client_id = client_id if client_id is not None else os.getenv("ATLAS_GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret if client_secret is not None else os.getenv("ATLAS_GOOGLE_CLIENT_SECRET", "")

    async def access_token(self, refresh_token: str) -> str:
        if not self.client_id or not self.client_secret:
            raise UpstreamServiceError("Google OAuth client configuration missing")
        try:
            response = await self.client.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "refresh_token", "refresh_token": refresh_token,
                "client_id": self.client_id, "client_secret": self.client_secret})
            if not 200 <= response.status_code < 300:
                raise UpstreamServiceError("Google OAuth refresh rejected")
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamServiceError("Google OAuth refresh failed") from exc
        token = data.get("access_token") if isinstance(data, dict) else None
        if (not isinstance(token, str) or not token or token == refresh_token
                or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in token)
                or str(data.get("token_type", "")).lower() != "bearer"):
            raise UpstreamServiceError("Google OAuth returned invalid access token")
        return token
