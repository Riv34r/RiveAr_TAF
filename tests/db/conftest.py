"""
Shared pytest fixtures for the DB suite.

    db_engine  -> a SQLAlchemy engine bound to the SUT's Postgres, from env
    db_session -> a Session, function-scoped and always rolled back after
                  the test - nothing a test writes outlives it, pass or fail
    count_rows -> count_rows(<condition>) - how many rows match

A test sends a statement with session.execute(update(...)/delete(...)/
text(...)) (which hits the DB, and raises on a constraint violation, right
there) or with session.add(obj) + session.flush(). Either way it stays
inside the fixture's transaction and never commits.
"""

import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from core.db.session import build_dsn

load_dotenv(override=False)


@pytest.fixture(scope="session")
def db_engine():
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
