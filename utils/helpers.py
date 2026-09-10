"""Shared helper functions."""

from sqlalchemy.exc import IntegrityError

from api.models.auth import TokenResponse


def seeded_account(manifest: dict, role: str) -> dict:
    """The first seeded account holding `role` (e.g. "ADMIN", "CUSTOMER")."""
    return next(a for a in manifest["accounts"] if a["role"] == role)


def assert_status_code(response, expected: int) -> None:
    assert response.status_code == expected, (
        f"Expected status {expected}, got {response.status_code}. "
        f"Response body: {response.text}"
    )


def assert_valid_token_pair(tokens: TokenResponse) -> None:
    assert tokens.token_type == "bearer"
    assert tokens.expires_in > 0


def assert_paginated_response(response, expected_status: int = 200) -> dict:
    """Assert a paginated list envelope ({"items", "pagination"}); return the body."""
    assert_status_code(response, expected_status)

    body = response.json()
    assert "items" in body, f"Response has no 'items': {body}"
    assert set(body["pagination"]) >= {
        "page",
        "page_size",
        "total",
        "total_pages",
    }, f"Response 'pagination' missing expected keys: {body.get('pagination')}"

    return body


def assert_rejected(
    session, statement, *, constraint: str = None, sqlstate: str = None
):
    """Run `statement`, expecting the database to refuse it.

    Executes within the caller's transaction (nothing commits). On the
    expected IntegrityError checks psycopg's `sqlstate` ("23514" CHECK,
    "23503" foreign key, "23505" unique) and/or the `constraint` name
    Postgres reported (e.g. "ck_orders_total_non_negative"). Fails if the
    write unexpectedly succeeds.
    """
    try:
        session.execute(statement)
    except IntegrityError as exc:
        orig = exc.orig
        if sqlstate is not None:
            assert (
                orig.sqlstate == sqlstate
            ), f"Expected SQLSTATE {sqlstate}, got {orig.sqlstate}: {orig}"
        if constraint is not None:
            actual = orig.diag.constraint_name
            assert (
                actual == constraint
            ), f"Expected constraint {constraint!r}, got {actual!r}: {orig}"
        return
    raise AssertionError("Expected the database to reject this write, but it succeeded")


def assert_error(response, expected_status: int, expected_code: str) -> dict:
    """Assert the response is RiveAr's structured error envelope, and return it.

    Every error RiveAr returns - validation, auth, business rule - is
    {"error": {"code", "message", "details", "request_id"}}. Returns the
    inner `error` object so a test can go on to assert on `details` without
    re-parsing the body.
    """
    assert_status_code(response, expected_status)

    body = response.json()
    assert "error" in body, f"Response is not in the error envelope: {body}"

    error = body["error"]
    assert (
        error["code"] == expected_code
    ), f"Expected error code {expected_code!r}, got: {error!r}"
    assert error["message"], f"Error {expected_code} carries no message: {error}"

    return error
