"""
Shared pytest fixtures.

    api_url         -> base URL + version prefix, read from the environment
    api             -> an unauthenticated ApiClient pointed at it
    auth_client     -> AuthClient wrapping api, for /auth/* operations
    seed_manifest   -> seeded accounts and their real password, from the SUT
    customer        -> the seeded CUSTOMER account (email, role, ...)
    admin_client    -> ApiClient authenticated as the seeded ADMIN account
    factory         -> creates disposable test data via /test/factory/*,
                       cleaned up automatically at the end of the session
"""

import os
import uuid

import pytest
from dotenv import load_dotenv

from core.api_client import ApiClient
from core.auth_client import AuthClient
from utils.helpers import seeded_account

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


@pytest.fixture(scope="session")
def seed_manifest(api) -> dict:
    response = api.get("/test/seed-manifest")
    assert (
        response.status_code == 200
    ), f"Could not read the seed manifest: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture(scope="session")
def customer(seed_manifest) -> dict:
    return seeded_account(seed_manifest, "CUSTOMER")


@pytest.fixture(scope="session")
def admin_client(api_url, auth_client, seed_manifest) -> ApiClient:
    admin = seeded_account(seed_manifest, "ADMIN")
    response = auth_client.login(admin["email"], seed_manifest["password"])
    assert (
        response.status_code == 200
    ), f"Could not authenticate as admin: {response.status_code} {response.text}"
    return ApiClient(api_url, response.json()["access_token"])


@pytest.fixture(scope="session")
def run_id() -> str:
    return f"pytest-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="session")
def factory(api, run_id):
    def _create(entity_type: str, **overrides) -> dict:
        response = api.post(
            f"/test/factory/{entity_type}", json={"run_id": run_id, **overrides}
        )
        assert response.status_code == 201, (
            f"Factory could not create a {entity_type}: "
            f"{response.status_code} {response.text}"
        )
        return response.json()

    yield _create

    api.delete("/test/cleanup", params={"run_id": run_id})
