"""Fixtures for the UI suite."""

import json
import os

import pytest

# The front end reads its session from these two localStorage keys
# (frontend/src/api/tokenStorage.ts).
ACCESS_TOKEN_KEY = "rivear_access_token"
REFRESH_TOKEN_KEY = "rivear_refresh_token"


@pytest.fixture(scope="session")
def base_url() -> str:
    """The front end's own URL - what pytest-playwright resolves page.goto() against."""
    return os.environ["UI_BASE_URL"].rstrip("/")


@pytest.fixture
def sign_in(page):
    """sign_in(token_pair) - hand the browser a session instead of the login form."""

    def _sign_in(token_pair: dict) -> None:
        page.add_init_script(
            f"localStorage.setItem({json.dumps(ACCESS_TOKEN_KEY)}, "
            f"{json.dumps(token_pair['access_token'])});"
            f"localStorage.setItem({json.dumps(REFRESH_TOKEN_KEY)}, "
            f"{json.dumps(token_pair['refresh_token'])});"
        )

    return _sign_in


@pytest.fixture(scope="session")
def customer_tokens(auth_client, customer, seed_manifest) -> dict:
    """A token pair for the seeded CUSTOMER, taken over the API."""
    response = auth_client.login(customer["email"], seed_manifest["password"])
    assert (
        response.status_code == 200
    ), f"Could not log the seeded customer in: {response.status_code} {response.text}"
    return response.json()
