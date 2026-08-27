"""
HTTP client for the API under test.

    api = ApiClient("http://localhost:8000/api/v1")
    api.get("/health")

    customer = ApiClient("http://localhost:8000/api/v1", token)
    customer.get("/auth/me")
    customer.post("/cart/items", json={"product_id": pid, "quantity": 2})
"""

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10


class ApiClient:
    """An HTTP client bound to one base URL and one identity."""

    def __init__(
        self,
        base_url: str,
        token: str = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)  # a caller's own timeout still wins

        response = self.session.request(method, url, **kwargs)

        logger.info(
            "%s %s -> %s (request_id=%s)",
            method,
            url,
            response.status_code,
            response.headers.get("X-Request-ID", "-"),
        )
        return response

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._request("DELETE", path, **kwargs)

    def __repr__(self) -> str:
        identity = (
            "authenticated" if "Authorization" in self.session.headers else "anonymous"
        )
        return f"ApiClient({self.base_url!r}, {identity})"
