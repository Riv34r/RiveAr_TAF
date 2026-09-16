"""Fixtures for the UI suite."""

import json
import os
from decimal import Decimal
from string import Template

import pytest

from ui.pages.cart_page import CartLine
from ui.pages.home_page import HomePage
from ui.pages.login_page import LoginPage
from ui.pages.order_history_page import OrderHistoryPage
from ui.pages.product_details_page import ProductDetailsPage
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
    if "unrenewable_session_page" in request.fixturenames:
        tokens = request.getfixturevalue("unrenewable_session_tokens")
        return new_context(storage_state=session_state(tokens))
    if "lapsed_session_page" in request.fixturenames:
        tokens = request.getfixturevalue("lapsed_session_tokens")
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
def unrenewable_session_page(page):
    """The test's page, signed in as the seeded CUSTOMER with no way to renew."""
    return page


@pytest.fixture
def unrenewable_session_tokens(customer_tokens) -> dict:
    """The seeded CUSTOMER's working access token and a malformed refresh token."""
    return {**customer_tokens, "refresh_token": "not.a.token"}


@pytest.fixture
def lapsed_session_page(page):
    """The test's page, starting with the seeded CUSTOMER's access token lapsed."""
    return page


@pytest.fixture
def lapsed_session_tokens(customer_tokens, expired_access_token) -> dict:
    """The seeded CUSTOMER's token pair, its access token swapped for an expired one."""
    return {**customer_tokens, "access_token": expired_access_token}


@pytest.fixture
def customer_tokens(auth_client, customer) -> dict:
    """A fresh token pair for the seeded CUSTOMER, taken over the API."""
    response = auth_client.login(customer["email"], customer["password"])
    assert_status_code(response, 200)
    return response.json()


@pytest.fixture
def home_page(page) -> HomePage:
    """The storefront home, opened in this test's page."""
    return HomePage(page).open()


@pytest.fixture
def login_page(page) -> LoginPage:
    """The login screen, opened in this test's page."""
    return LoginPage(page).open()


@pytest.fixture
def order_history_page(page) -> OrderHistoryPage:
    """The customer's order history, opened in this test's page."""
    return OrderHistoryPage(page).open()


@pytest.fixture
def new_product_line(new_product):
    """new_product_line(quantity) - the cart line the throwaway product makes."""

    def _line(quantity: int) -> CartLine:
        return CartLine(
            name=new_product["attributes"]["name"],
            quantity=quantity,
            line_total=Decimal(new_product["attributes"]["price"]) * quantity,
        )

    return _line


@pytest.fixture
def refused_guest_cart(login_page, new_product, out_of_stock_product):
    """The guest cart holds one in-stock and one out-of-stock product."""
    lines = [
        {"product_id": new_product["entity_id"], "quantity": 1},
        {"product_id": out_of_stock_product["entity_id"], "quantity": 1},
    ]
    login_page.page.evaluate(
        "lines => localStorage.setItem('rivear_guest_cart', JSON.stringify(lines))",
        lines,
    )


@pytest.fixture
def product_details_page(page, new_product) -> ProductDetailsPage:
    """The throwaway product's page, opened in this test's page."""
    return ProductDetailsPage(page).open(id=new_product["entity_id"])
