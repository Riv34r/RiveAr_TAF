"""Fixtures shared by more than one suite."""

import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.clients.auth_client import AuthClient
from core.api.api_client import ApiClient
from core.db.session import build_dsn
from db.models import Order
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
    """The seeded CUSTOMER account (email, role, password, ...)."""
    return seeded_account(seed_manifest, "CUSTOMER")


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
