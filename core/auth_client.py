"""
Domain client for authentication endpoints (/auth/*).

    auth = AuthClient(api)
    response = auth.register(email, password, full_name)
    me = auth.get_current_user(tokens.access_token)
"""

import requests

from core.api_client import ApiClient


class AuthClient:
    """Wraps an ApiClient to expose /auth/* operations without inline payloads."""

    def __init__(self, api: ApiClient):
        self.api = api

    def register(self, email: str, password: str, full_name: str) -> requests.Response:
        return self.api.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )

    def get_current_user(self, token: str) -> requests.Response:
        """Identity behind a token, via GET /auth/me ("who am I")."""
        return self.api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
