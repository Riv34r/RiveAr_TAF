"""
Shared pytest fixtures.

    api_url         -> base URL + version prefix, read from the environment
    api             -> an unauthenticated ApiClient pointed at it
    auth_client     -> AuthClient wrapping api, for /auth/* operations
    seed_manifest   -> seeded accounts and their real password, from the SUT
    customer        -> the seeded CUSTOMER account (email, role, ...)
    admin_client    -> AdminClient authenticated as the seeded ADMIN account
    factory         -> creates disposable test data via /test/factory/*,
                       cleaned up automatically after each test
    new_customer    -> a fresh throwaway customer via factory("customer")
    logged_in_customer -> (new_customer, token pair) for a fresh,
                       already-logged-in throwaway customer
    customer_client -> AdminClient authenticated as a throwaway customer,
                       for permission-boundary negative tests
"""

import os
import uuid

import pytest
from dotenv import load_dotenv

from core.admin_client import AdminClient
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
def admin_client(api_url, auth_client, seed_manifest) -> AdminClient:
    admin = seeded_account(seed_manifest, "ADMIN")
    response = auth_client.login(admin["email"], seed_manifest["password"])
    assert (
        response.status_code == 200
    ), f"Could not authenticate as admin: {response.status_code} {response.text}"
    return AdminClient(ApiClient(api_url, response.json()["access_token"]))


@pytest.fixture
def run_id() -> str:
    return f"pytest-{uuid.uuid4().hex[:12]}"


@pytest.fixture
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


@pytest.fixture
def new_customer(factory):
    return factory("customer")


@pytest.fixture
def logged_in_customer(new_customer, auth_client):
    token_pair = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    ).json()
    return new_customer, token_pair


@pytest.fixture
def customer_client(api_url, logged_in_customer) -> AdminClient:
    _, token_pair = logged_in_customer
    return AdminClient(ApiClient(api_url, token_pair["access_token"]))
