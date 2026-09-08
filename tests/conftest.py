"""
Shared pytest fixtures.

    api_url         -> base URL + version prefix, read from the environment
    api             -> an unauthenticated ApiClient pointed at it
    auth_client     -> AuthClient wrapping api, for /auth/* operations
    seed_manifest   -> seeded accounts and their real password, from the SUT
    customer        -> the seeded CUSTOMER account (email, role, ...)
    admin_session   -> an authenticated ApiClient for the seeded ADMIN
                       account, shared by every domain client that needs
                       a privileged identity
    admin_client    -> AdminClient authenticated as the seeded ADMIN account
    factory         -> creates disposable test data via /test/factory/*,
                       cleaned up automatically after each test
    new_customer    -> a fresh throwaway customer via factory("customer")
    logged_in_customer -> (new_customer, token pair) for a fresh,
                       already-logged-in throwaway customer
    customer_client -> AdminClient authenticated as a throwaway customer,
                       for permission-boundary negative tests
    customer_products -> ProductClient authenticated as a throwaway
                       customer, for permission-boundary negative tests
    product_client  -> ProductClient authenticated as the seeded ADMIN
                       account (holds products:manage)
    public_products -> ProductClient with no authentication, for the
                       public/permission-boundary side of a check
    new_product     -> a fresh throwaway product via factory("product")
    inventory_client -> InventoryClient authenticated as the seeded ADMIN
                       account (holds inventory:manage)
    customer_inventory -> InventoryClient authenticated as a throwaway
                       customer, for permission-boundary negative tests
    inventory_for   -> resolves a product's inventory record by its SKU
    new_inventory   -> a fresh throwaway product's inventory record
    order_client    -> OrderClient authenticated as the seeded ADMIN
                       account, for staff-only order actions
    customer_orders -> OrderClient for the shared throwaway customer
                       (logged_in_customer) - most order scenarios act as
                       this one customer
    customer_cart   -> CartClient for that same throwaway customer
    new_customer_orders -> creates an independent throwaway customer and
                       returns (customer, OrderClient), for scenarios that
                       need more than one distinct customer
    new_order       -> a fresh throwaway order (1x a throwaway product) for
                       the shared customer_orders customer - for scenarios
                       that just need *an* order to act on, not a specific
                       product/price/quantity
    idempotency_key -> a fresh, unique Idempotency-Key value
"""

import os
import uuid

import pytest
from dotenv import load_dotenv

from core.admin_client import AdminClient
from core.api_client import ApiClient
from core.auth_client import AuthClient
from core.cart_client import CartClient
from core.inventory_client import InventoryClient
from core.order_client import OrderClient
from core.product_client import ProductClient
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
def admin_session(api_url, auth_client, seed_manifest) -> ApiClient:
    admin = seeded_account(seed_manifest, "ADMIN")
    response = auth_client.login(admin["email"], seed_manifest["password"])
    assert (
        response.status_code == 200
    ), f"Could not authenticate as admin: {response.status_code} {response.text}"
    return ApiClient(api_url, response.json()["access_token"])


@pytest.fixture(scope="session")
def admin_client(admin_session) -> AdminClient:
    return AdminClient(admin_session)


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


@pytest.fixture
def customer_products(api_url, logged_in_customer) -> ProductClient:
    _, token_pair = logged_in_customer
    return ProductClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture(scope="session")
def product_client(admin_session) -> ProductClient:
    return ProductClient(admin_session)


@pytest.fixture(scope="session")
def public_products(api) -> ProductClient:
    return ProductClient(api)


@pytest.fixture
def new_product(factory):
    return factory("product")


@pytest.fixture(scope="session")
def inventory_client(admin_session) -> InventoryClient:
    return InventoryClient(admin_session)


@pytest.fixture
def customer_inventory(api_url, logged_in_customer) -> InventoryClient:
    _, token_pair = logged_in_customer
    return InventoryClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def inventory_for(inventory_client):
    """Resolve a product's inventory record by its SKU.

    There is no standalone inventory factory - a record's lifetime matches
    its product's - so tests needing a specific stock create a product via
    factory("product", stock=...) and resolve the resulting record here.
    """

    def _resolve(sku: str) -> dict:
        items = inventory_client.list_inventory(search=sku).json()["items"]
        record = next((i for i in items if i["product_sku"] == sku), None)
        assert record is not None, f"No inventory record found for SKU {sku}"
        return record

    return _resolve


@pytest.fixture
def new_inventory(factory, inventory_for):
    product = factory("product")
    return inventory_for(product["attributes"]["sku"])


@pytest.fixture(scope="session")
def order_client(admin_session) -> OrderClient:
    return OrderClient(admin_session)


@pytest.fixture
def customer_orders(api_url, logged_in_customer) -> OrderClient:
    _, token_pair = logged_in_customer
    return OrderClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def customer_cart(api_url, logged_in_customer) -> CartClient:
    _, token_pair = logged_in_customer
    return CartClient(ApiClient(api_url, token_pair["access_token"]))


@pytest.fixture
def new_customer_orders(factory, auth_client, api_url):
    """Mint an independent throwaway customer + OrderClient on demand.

    logged_in_customer/customer_orders share one customer per test; scenarios
    that need two or more distinct customers (isolation checks) call this
    instead.
    """

    def _create():
        new_customer = factory("customer")
        token_pair = auth_client.login(
            new_customer["attributes"]["email"], new_customer["attributes"]["password"]
        ).json()
        return new_customer, OrderClient(ApiClient(api_url, token_pair["access_token"]))

    return _create


@pytest.fixture
def new_order(new_product, customer_orders) -> dict:
    response = customer_orders.create_order(
        items=[{"product_id": new_product["entity_id"], "quantity": 1}]
    )
    assert (
        response.status_code == 201
    ), f"Could not create a throwaway order: {response.status_code} {response.text}"
    return response.json()


@pytest.fixture
def idempotency_key() -> str:
    return f"idem-{uuid.uuid4().hex[:12]}"
