"""Fixtures shared by more than one suite."""

import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from core.db.session import build_dsn

load_dotenv(override=False)


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
