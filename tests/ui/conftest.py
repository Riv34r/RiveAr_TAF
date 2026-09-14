"""Fixtures for the UI suite."""

import json
import os
import time
from string import Template
from urllib.parse import urlparse

import pytest

from api.clients.order_client import OrderClient
from core.api.api_client import ApiClient
from ui.pages.home_page import HomePage
from ui.pages.login_page import LoginPage
from ui.pages.order_detail_page import OrderDetailPage
from ui.pages.order_history_page import OrderHistoryPage

# The localStorage keys data/session_state.json fills in
# (frontend/src/api/tokenStorage.ts), for reading and changing a session mid-visit.
TOKEN_KEYS = {
    "access_token": "rivear_access_token",
    "refresh_token": "rivear_refresh_token",
}

MALFORMED_TOKEN = "not.a.token"

# Each page fixture that starts signed in, and the token pair its context holds.
SESSIONS = {
    "customer_page": "customer_tokens",
    "rejected_session_page": "rejected_session_tokens",
    "unrenewable_session_page": "unrenewable_session_tokens",
    "lapsed_session_page": "lapsed_session_tokens",
}


@pytest.fixture(scope="session")
def base_url() -> str:
    """The front end's own URL - what pytest-playwright resolves page.goto() against."""
    return os.environ["UI_BASE_URL"].rstrip("/")


@pytest.fixture(scope="session")
def session_state(pytestconfig, base_url):
    """session_state(tokens) - data/session_state.json filled in for this front end."""
    path = pytestconfig.rootpath / "data" / "session_state.json"
    template = Template(path.read_text(encoding="utf-8"))

    def _fill(tokens: dict) -> dict:
        return json.loads(template.substitute(origin=base_url, **tokens))

    return _fill


@pytest.fixture
def context(new_context, session_state, request):
    """The test's context - holding the session its page fixture asks for."""
    for page_fixture, tokens_fixture in SESSIONS.items():
        if page_fixture in request.fixturenames:
            tokens = request.getfixturevalue(tokens_fixture)
            return new_context(storage_state=session_state(tokens))
    return new_context()


@pytest.fixture
def customer_page(page):
    """The test's page, signed in as the seeded CUSTOMER - see context."""
    return page


@pytest.fixture
def customer_tokens(auth_client, customer) -> dict:
    """Fresh tokens for the seeded CUSTOMER, so a logout revokes only this pair."""
    response = auth_client.login(customer["email"], customer["password"])
    assert (
        response.status_code == 200
    ), f"Could not log the seeded customer in: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture(scope="session")
def expired_access_token(api, customer) -> str:
    """An access token for the seeded CUSTOMER that has already expired."""
    response = api.post(
        "/test/token", json={"email": customer["email"], "ttl_seconds": 1}
    )
    assert (
        response.status_code == 200
    ), f"Could not mint a short-lived token: {response.status_code} {response.text}"
    time.sleep(1.5)
    return response.json()["access_token"]


@pytest.fixture
def rejected_session_page(page):
    """The test's page, starting with a token pair the API rejects outright."""
    return page


@pytest.fixture
def rejected_session_tokens(expired_access_token) -> dict:
    """An expired access token and a malformed refresh token."""
    return {"access_token": expired_access_token, "refresh_token": MALFORMED_TOKEN}


@pytest.fixture
def unrenewable_session_page(page):
    """The test's page, signed in as the seeded CUSTOMER with no way to renew."""
    return page


@pytest.fixture
def unrenewable_session_tokens(customer_tokens) -> dict:
    """The seeded CUSTOMER's working access token, with a malformed refresh token."""
    return {**customer_tokens, "refresh_token": MALFORMED_TOKEN}


@pytest.fixture
def lapsed_session_page(page):
    """The test's page, starting with the seeded CUSTOMER's access token lapsed."""
    return page


@pytest.fixture
def lapsed_session_tokens(customer_tokens, expired_access_token) -> dict:
    """The seeded CUSTOMER's token pair, its access token swapped for an expired one."""
    return {**customer_tokens, "access_token": expired_access_token}


@pytest.fixture
def stored_tokens(page):
    """stored_tokens() -> the token pair the front end holds now, None if gone."""

    def _read() -> dict:
        return {
            name: page.evaluate("key => localStorage.getItem(key)", key)
            for name, key in TOKEN_KEYS.items()
        }

    return _read


@pytest.fixture
def replace_access_token(page):
    """replace_access_token(token) - swap the stored access token mid-visit."""

    def _replace(token: str) -> None:
        page.evaluate(
            "([key, token]) => localStorage.setItem(key, token)",
            [TOKEN_KEYS["access_token"], token],
        )

    return _replace


@pytest.fixture
def requests_to(page):
    """requests_to("/auth/refresh") -> URLs of the requests the page sent there."""
    urls = []
    page.on("request", lambda request: urls.append(request.url))

    def _matching(path: str) -> list[str]:
        return [url for url in urls if urlparse(url).path.endswith(path)]

    return _matching


@pytest.fixture
def customer_order(api_url, customer_tokens) -> dict:
    """The seeded CUSTOMER's most recent order, from the API."""
    orders = OrderClient(ApiClient(api_url, customer_tokens["access_token"]))
    response = orders.list_orders(page_size=1, sort_by="created_at", sort_order="desc")
    assert response.status_code == 200, (
        f"Could not list the seeded customer's orders: "
        f"{response.status_code} {response.text}"
    )
    items = response.json()["items"]
    assert items, "The seeded customer has no orders"
    return items[0]


@pytest.fixture
def login_page(page) -> LoginPage:
    """The login screen, bound to this test's page."""
    return LoginPage(page)


@pytest.fixture
def home_page(page) -> HomePage:
    """The storefront home, bound to this test's page."""
    return HomePage(page)


@pytest.fixture
def order_history_page(page) -> OrderHistoryPage:
    """The customer's order history, bound to this test's page."""
    return OrderHistoryPage(page)


@pytest.fixture
def order_detail_page(page) -> OrderDetailPage:
    """A single order's page, bound to this test's page."""
    return OrderDetailPage(page)
