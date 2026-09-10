"""Fixtures for the API suite."""

import os
import uuid

import pytest
from dotenv import load_dotenv

from api.clients.admin_client import AdminClient
from api.clients.auth_client import AuthClient
from api.clients.cart_client import CartClient
from api.clients.inventory_client import InventoryClient
from api.clients.order_client import OrderClient
from api.clients.product_client import ProductClient
from core.api.api_client import ApiClient
from utils.helpers import seeded_account

load_dotenv(override=False)


@pytest.fixture(scope="session")
def api_url() -> str:
    """Base URL + version prefix, read from the environment."""
    host = os.environ["BASE_URL"].rstrip("/")
    prefix = os.environ["API_PREFIX"].strip("/")
    return f"{host}/{prefix}"


@pytest.fixture(scope="session")
def api(api_url) -> ApiClient:
    """An unauthenticated ApiClient pointed at the SUT."""
    return ApiClient(api_url)


@pytest.fixture(scope="session")
def auth_client(api) -> AuthClient:
    """AuthClient wrapping api, for /auth/* operations."""
    return AuthClient(api)


@pytest.fixture(scope="session")
def seed_manifest(api) -> dict:
    """The seeded accounts and their real password, from the SUT itself."""
    response = api.get("/test/seed-manifest")
    assert (
        response.status_code == 200
    ), f"Could not read the seed manifest: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture(scope="session")
def customer(seed_manifest) -> dict:
    """The seeded CUSTOMER account (email, role, ...)."""
    return seeded_account(seed_manifest, "CUSTOMER")


@pytest.fixture(scope="session")
def admin_session(api_url, auth_client, seed_manifest) -> ApiClient:
    """An ApiClient authenticated as the seeded ADMIN, shared by domain clients."""
    admin = seeded_account(seed_manifest, "ADMIN")
    response = auth_client.login(admin["email"], seed_manifest["password"])
    assert (
        response.status_code == 200
    ), f"Could not authenticate as admin: {response.status_code} {response.text}"
    return ApiClient(api_url, response.json()["access_token"])


@pytest.fixture(scope="session")
def admin_client(admin_session) -> AdminClient:
    """AdminClient authenticated as the seeded ADMIN account."""
    return AdminClient(admin_session)


@pytest.fixture
def run_id() -> str:
    """A unique tag for one test's disposable entities."""
    return f"pytest-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def factory(api, run_id):
    """Create disposable data via /test/factory/*, cleaned up after each test."""

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
    """A fresh throwaway customer."""
    return factory("customer")


@pytest.fixture
def logged_in_customer(new_customer, auth_client):
    """(customer, token pair) for a fresh, already-logged-in throwaway customer."""
    token_pair = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    ).json()
    return new_customer, token_pair


@pytest.fixture
def customer_client(api_url, logged_in_customer) -> AdminClient:
    """AdminClient as a throwaway customer, for permission-boundary tests."""
    _, token_pair = logged_in_customer
    return AdminClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def customer_products(api_url, logged_in_customer) -> ProductClient:
    """ProductClient as a throwaway customer, for permission-boundary tests."""
    _, token_pair = logged_in_customer
    return ProductClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture(scope="session")
def product_client(admin_session) -> ProductClient:
    """ProductClient as the seeded ADMIN, who holds products:manage."""
    return ProductClient(admin_session)


@pytest.fixture(scope="session")
def public_products(api) -> ProductClient:
    """ProductClient with no authentication, for the public side of a check."""
    return ProductClient(api)


@pytest.fixture
def new_product(factory):
    """A fresh throwaway product."""
    return factory("product")


@pytest.fixture(scope="session")
def inventory_client(admin_session) -> InventoryClient:
    """InventoryClient as the seeded ADMIN, who holds inventory:manage."""
    return InventoryClient(admin_session)


@pytest.fixture
def customer_inventory(api_url, logged_in_customer) -> InventoryClient:
    """InventoryClient as a throwaway customer, for permission-boundary tests."""
    _, token_pair = logged_in_customer
    return InventoryClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def inventory_for(inventory_client):
    """Resolve a product's inventory record by its SKU - there is no factory for one."""

    def _resolve(sku: str) -> dict:
        items = inventory_client.list_inventory(search=sku).json()["items"]
        record = next((i for i in items if i["product_sku"] == sku), None)
        assert record is not None, f"No inventory record found for SKU {sku}"
        return record

    return _resolve


@pytest.fixture
def new_inventory(factory, inventory_for):
    """A fresh throwaway product's inventory record."""
    product = factory("product")
    return inventory_for(product["attributes"]["sku"])


@pytest.fixture(scope="session")
def order_client(admin_session) -> OrderClient:
    """OrderClient as the seeded ADMIN, for staff-only order actions."""
    return OrderClient(admin_session)


@pytest.fixture
def customer_orders(api_url, logged_in_customer) -> OrderClient:
    """OrderClient for the shared throwaway customer most order scenarios act as."""
    _, token_pair = logged_in_customer
    return OrderClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def customer_cart(api_url, logged_in_customer) -> CartClient:
    """CartClient for that same throwaway customer."""
    _, token_pair = logged_in_customer
    return CartClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def new_customer_orders(factory, auth_client, api_url):
    """An independent (customer, OrderClient), for scenarios needing a second one."""

    def _create():
        new_customer = factory("customer")
        token_pair = auth_client.login(
            new_customer["attributes"]["email"], new_customer["attributes"]["password"]
        ).json()
        return new_customer, OrderClient(ApiClient(api_url, token_pair["access_token"]))

    return _create


@pytest.fixture
def new_order(new_product, customer_orders) -> dict:
    """A fresh throwaway order (1x a throwaway product) for customer_orders."""
    response = customer_orders.create_order(
        items=[{"product_id": new_product["entity_id"], "quantity": 1}]
    )
    assert (
        response.status_code == 201
    ), f"Could not create a throwaway order: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture
def idempotency_key() -> str:
    """A fresh, unique Idempotency-Key value."""
    return f"idem-{uuid.uuid4().hex[:12]}"
