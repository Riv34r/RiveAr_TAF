"""
Domain client for authentication endpoints (/auth/*).

    auth = AuthClient(api)
    response = auth.register(email, password, full_name)
    response = auth.login(email, password)
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

    def login(self, email: str, password: str) -> requests.Response:
        return self.api.post("/auth/login", json={"email": email, "password": password})

    def refresh(self, refresh_token: str) -> requests.Response:
        return self.api.post("/auth/refresh", json={"refresh_token": refresh_token})

    def logout(self, refresh_token: str) -> requests.Response:
        return self.api.post("/auth/logout", json={"refresh_token": refresh_token})

    def get_current_user(self, token: str) -> requests.Response:
        """Identity behind a token, via GET /auth/me ("who am I")."""
        return self.api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    def update_profile(self, token: str, full_name: str) -> requests.Response:
        return self.api.patch(
            "/auth/me",
            json={"full_name": full_name},
            headers={"Authorization": f"Bearer {token}"},
        )

    def change_password(
        self, token: str, current_password: str, new_password: str
    ) -> requests.Response:
        return self.api.post(
            "/auth/change-password",
            json={"current_password": current_password, "new_password": new_password},
            headers={"Authorization": f"Bearer {token}"},
        )
