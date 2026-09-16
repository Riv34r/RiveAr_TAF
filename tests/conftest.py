"""Fixtures shared by more than one suite."""

import os
import time
import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.clients.auth_client import AuthClient
from core.api.api_client import ApiClient
from core.db.session import build_dsn
from db.models import Order
from utils.helpers import assert_status_code, seeded_account

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
    """The seeded CUSTOMER account (email, role, password, ...)."""
    return seeded_account(seed_manifest, "CUSTOMER")


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


@pytest.fixture(scope="session")
def out_of_stock_product(seed_manifest) -> dict:
    """The seeded product with no stock, as the seed manifest lists it."""
    return next(
        fixture
        for fixture in seed_manifest["fixtures"]
        if fixture["key"] == "out_of_stock_product"
    )


@pytest.fixture
def new_customer(factory):
    """A fresh throwaway customer, with an empty cart."""
    return factory("customer")


@pytest.fixture
def new_product(factory):
    """A fresh throwaway product - active, 100 in stock, no category."""
    return factory("product")


@pytest.fixture(scope="session")
def expired_access_token(api, customer) -> str:
    """An access token for the seeded CUSTOMER that has already expired."""
    response = api.post(
        "/test/token", json={"email": customer["email"], "ttl_seconds": 1}
    )
    assert_status_code(response, 200)
    time.sleep(1.5)
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def db_engine():
    """A SQLAlchemy engine bound to the SUT's Postgres, from the environment."""
    dsn = build_dsn(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        name=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    engine = create_engine(dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A Session that always rolls back - nothing a test writes outlives it."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def count_rows(db_session):
    """count_rows(OrderItem.order_id == some_id) -> how many rows match."""

    def _count(condition):
        return db_session.scalar(select(func.count()).where(condition))

    return _count


@pytest.fixture
def customer_order(db_session, customer) -> Order:
    """One of the seeded CUSTOMER's orders, from the database."""
    order = db_session.scalars(
        select(Order).where(Order.customer_id == customer["customer_id"])
    ).first()
    assert order is not None, "The seeded CUSTOMER has no orders to test against"
    return order
