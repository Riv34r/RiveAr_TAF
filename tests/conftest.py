"""
Shared pytest fixtures.

    api_url      -> base URL + version prefix, read from the environment
    api          -> an unauthenticated ApiClient pointed at it
    auth_client  -> AuthClient wrapping api, for /auth/* operations
"""

import os

import pytest
from dotenv import load_dotenv

from core.api_client import ApiClient
from core.auth_client import AuthClient

load_dotenv(override=False)


@pytest.fixture(scope="session")
def api_url() -> str:
    host = os.environ["BASE_URL"].rstrip("/")
    prefix = os.environ["API_PREFIX"].strip("/")
    return f"{host}/{prefix}"


@pytest.fixture(scope="session")
def api(api_url) -> ApiClient:
    return ApiClient(api_url)


@pytest.fixture(scope="session")
def auth_client(api) -> AuthClient:
    return AuthClient(api)
