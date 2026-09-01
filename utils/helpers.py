"""Shared helper functions."""

from models.auth import TokenResponse


def seeded_account(manifest: dict, role: str) -> dict:
    """The first seeded account holding `role` (e.g. "ADMIN", "CUSTOMER")."""
    return next(a for a in manifest["accounts"] if a["role"] == role)


def logged_in_customer(factory, auth_client):
    """Create a throwaway customer and log in as them.

    Returns (factory response, token pair). email/password/user_id are in
    the factory response's `attributes`.
    """
    new_customer = factory("customer")
    token_pair = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    ).json()
    return new_customer, token_pair


def assert_status_code(response, expected: int) -> None:
    assert response.status_code == expected, (
        f"Expected status {expected}, got {response.status_code}. "
        f"Response body: {response.text}"
    )


def assert_valid_token_pair(tokens: TokenResponse) -> None:
    assert tokens.token_type == "bearer"
    assert tokens.expires_in > 0


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
