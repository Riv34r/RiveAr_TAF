"""Fixtures for the UI suite."""

import json
import os
from string import Template

import pytest

from ui.pages.login_page import LoginPage
from ui.pages.order_history_page import OrderHistoryPage
from utils.helpers import assert_status_code


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
    if "customer_page" in request.fixturenames:
        tokens = request.getfixturevalue("customer_tokens")
        return new_context(storage_state=session_state(tokens))
    if "rejected_session_page" in request.fixturenames:
        tokens = request.getfixturevalue("rejected_session_tokens")
        return new_context(storage_state=session_state(tokens))
    return new_context()


@pytest.fixture
def customer_page(page):
    """The test's page, signed in as the seeded CUSTOMER - see context."""
    return page


@pytest.fixture
def rejected_session_page(page):
    """The test's page, starting with a token pair the API rejects - see context."""
    return page


@pytest.fixture
def rejected_session_tokens(expired_access_token) -> dict:
    """An expired access token and a malformed refresh token."""
    return {"access_token": expired_access_token, "refresh_token": "not.a.token"}


@pytest.fixture
def customer_tokens(auth_client, customer) -> dict:
    """A fresh token pair for the seeded CUSTOMER, taken over the API."""
    response = auth_client.login(customer["email"], customer["password"])
    assert_status_code(response, 200)
    return response.json()


@pytest.fixture
def login_page(page) -> LoginPage:
    """The login screen, opened in this test's page."""
    return LoginPage(page).open()


@pytest.fixture
def order_history_page(page) -> OrderHistoryPage:
    """The customer's order history, opened in this test's page."""
    return OrderHistoryPage(page).open()
