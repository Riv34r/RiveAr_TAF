"""Test cases for the /auth/* endpoints: register, login, refresh, logout,
profile, and password change.

Implements AUTH-001 through AUTH-030 from tests/scenarios/api/auth.md.
"""

import time

import allure
import pytest
from faker import Faker

from models.auth import TokenResponse
from utils.helpers import (
    assert_error,
    assert_status_code,
    assert_valid_token_pair,
    logged_in_customer,
)

pytestmark = allure.feature("Auth")

fake = Faker()


def disable(admin_client, new_customer):
    response = admin_client.patch(
        f"/admin/users/{new_customer['attributes']['user_id']}",
        json={"is_active": False},
    )
    assert_status_code(response, 200)


def disabled_customer(admin_client, factory):
    """Create a throwaway customer and disable it as an admin.

    Returns the factory response (email/password/user_id in `attributes`).
    """
    new_customer = factory("customer")
    disable(admin_client, new_customer)
    return new_customer


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@allure.title("Registering with valid details creates a customer and returns tokens")
@allure.tag("AUTH-001")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_register_creates_customer_and_returns_tokens(auth_client):
    email = fake.unique.email()
    response = auth_client.register(email, "StrongPass1", fake.name())

    assert_status_code(response, 201)
    token_pair = TokenResponse.model_validate(response.json())
    assert_valid_token_pair(token_pair)

    # The account is immediately usable with the returned access token.
    current_user = auth_client.get_current_user(token_pair.access_token).json()
    assert current_user["email"] == email
    assert current_user["roles"] == ["CUSTOMER"]
    assert current_user["is_active"] is True


@allure.title("Registering with an already-registered email returns 409")
@allure.tag("AUTH-002")
@allure.severity(allure.severity_level.CRITICAL)
def test_register_with_duplicate_email_returns_409(auth_client, customer):
    response = auth_client.register(customer["email"], "StrongPass1", "Duplicate")

    assert_error(response, 409, "EMAIL_ALREADY_REGISTERED")


@allure.title("Registering with a malformed email returns 422")
@allure.tag("AUTH-003")
@allure.severity(allure.severity_level.NORMAL)
def test_register_with_malformed_email_returns_422(auth_client):
    response = auth_client.register("not-an-email", "StrongPass1", "X")

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Registering with a password that fails strength rules returns 422")
@allure.tag("AUTH-004")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize(
    "password",
    ["alllowercase", "12345678", "short1"],
    ids=["no-digit", "no-letter", "below-min-length"],
)
def test_register_with_invalid_password_returns_422(auth_client, password):
    """Covers the letter+digit strength rule and the 8-char floor,
    each enforced independently by RegisterRequest."""
    response = auth_client.register(fake.unique.email(), password, fake.name())

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Registering with a missing required field returns 422")
@allure.tag("AUTH-005")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize("missing_field", ["email", "password", "full_name"])
def test_register_missing_required_field_returns_422(auth_client, missing_field):
    payload = {
        "email": fake.unique.email(),
        "password": "StrongPass1",
        "full_name": fake.name(),
    }
    del payload[missing_field]

    response = auth_client.api.post("/auth/register", json=payload)

    assert_error(response, 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@allure.title("Logging in with valid credentials returns a token pair")
@allure.tag("AUTH-006")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_login_with_valid_credentials_returns_a_token_pair(
    auth_client, admin_client, customer, seed_manifest
):
    # last_login_at is a server timestamp - compare it against its own
    # previous value rather than the test runner's clock.
    before = admin_client.get(f"/admin/users/{customer['user_id']}").json()
    last_login_before = before["last_login_at"]

    response = auth_client.login(customer["email"], seed_manifest["password"])

    assert_status_code(response, 200)
    token_pair = TokenResponse.model_validate(response.json())
    assert_valid_token_pair(token_pair)

    current_user = auth_client.get_current_user(token_pair.access_token).json()
    assert current_user["last_login_at"] != last_login_before


@allure.title("Logging in with a wrong password returns 401")
@allure.tag("AUTH-007")
@allure.severity(allure.severity_level.CRITICAL)
def test_login_with_wrong_password_returns_401(auth_client, customer):
    response = auth_client.login(customer["email"], "WrongPassword123!")

    assert_error(response, 401, "INVALID_CREDENTIALS")


@allure.title("An unknown email is indistinguishable from a wrong password")
@allure.tag("AUTH-008")
@allure.severity(allure.severity_level.CRITICAL)
def test_unknown_email_is_indistinguishable_from_wrong_password(
    auth_client, customer, seed_manifest
):
    unknown_email = auth_client.login(fake.unique.email(), seed_manifest["password"])
    wrong_password = auth_client.login(customer["email"], "WrongPassword123!")

    assert unknown_email.status_code == wrong_password.status_code
    assert (
        unknown_email.json()["error"]["code"] == wrong_password.json()["error"]["code"]
    )


@allure.title("Logging in to a disabled account returns 401")
@allure.tag("AUTH-009")
@allure.severity(allure.severity_level.NORMAL)
def test_login_to_a_disabled_account_returns_401(admin_client, factory, auth_client):
    new_customer = disabled_customer(admin_client, factory)

    response = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    )

    assert_error(response, 401, "USER_DISABLED")


@allure.title("A malformed login request returns 422")
@allure.tag("AUTH-010")
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.parametrize(
    "payload",
    [{"password": "x"}, {"email": "a@b.com"}, {}],
    ids=["missing-email", "missing-password", "empty-body"],
)
def test_malformed_login_request_returns_422(api, payload):
    response = api.post("/auth/login", json=payload)

    assert_error(response, 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


@allure.title("A valid refresh token rotates into a new token pair")
@allure.tag("AUTH-011")
@allure.severity(allure.severity_level.CRITICAL)
def test_refresh_rotates_into_a_new_token_pair(auth_client, customer, seed_manifest):
    token_pair = auth_client.login(customer["email"], seed_manifest["password"]).json()

    response = auth_client.refresh(token_pair["refresh_token"])

    assert_status_code(response, 200)
    rotated = response.json()
    assert rotated["refresh_token"] != token_pair["refresh_token"]
    assert_status_code(auth_client.get_current_user(rotated["access_token"]), 200)


@allure.title("A refresh token cannot be reused after rotation")
@allure.tag("AUTH-012")
@allure.severity(allure.severity_level.CRITICAL)
def test_refresh_token_cannot_be_reused_after_rotation(
    auth_client, customer, seed_manifest
):
    token_pair = auth_client.login(customer["email"], seed_manifest["password"]).json()
    first_refresh = auth_client.refresh(token_pair["refresh_token"])
    assert_status_code(first_refresh, 200)

    reused = auth_client.refresh(token_pair["refresh_token"])

    assert_error(reused, 401, "TOKEN_REVOKED")


@pytest.mark.skip(
    reason="No API-only way to produce an expired refresh token - see the "
    "Blocker note on AUTH-013 in tests/scenarios/api/auth.md"
)
@allure.title("An expired refresh token returns 401")
@allure.tag("AUTH-013")
@allure.severity(allure.severity_level.NORMAL)
def test_expired_refresh_token_returns_401():
    pass


@allure.title("A malformed refresh token returns 401")
@allure.tag("AUTH-014")
@allure.severity(allure.severity_level.NORMAL)
def test_malformed_refresh_token_returns_401(auth_client):
    response = auth_client.refresh("not.a.token")

    assert_error(response, 401, "TOKEN_INVALID")


@allure.title("Refreshing as a since-disabled user returns 401")
@allure.tag("AUTH-015")
@allure.severity(allure.severity_level.MINOR)
def test_refresh_as_a_since_disabled_user_returns_401(
    admin_client, factory, auth_client
):
    new_customer, token_pair = logged_in_customer(factory, auth_client)
    disable(admin_client, new_customer)

    response = auth_client.refresh(token_pair["refresh_token"])

    assert_error(response, 401, "USER_DISABLED")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@allure.title("Logging out revokes the refresh token")
@allure.tag("AUTH-016")
@allure.severity(allure.severity_level.CRITICAL)
def test_logout_revokes_the_refresh_token(auth_client, customer, seed_manifest):
    token_pair = auth_client.login(customer["email"], seed_manifest["password"]).json()

    response = auth_client.logout(token_pair["refresh_token"])

    assert_status_code(response, 204)
    reused = auth_client.refresh(token_pair["refresh_token"])
    assert_error(reused, 401, "TOKEN_REVOKED")


@allure.title("Logging out an already-revoked token is idempotent")
@allure.tag("AUTH-017")
@allure.severity(allure.severity_level.NORMAL)
def test_logout_is_idempotent_for_an_already_revoked_token(
    auth_client, customer, seed_manifest
):
    token_pair = auth_client.login(customer["email"], seed_manifest["password"]).json()
    auth_client.logout(token_pair["refresh_token"])

    response = auth_client.logout(token_pair["refresh_token"])

    assert_status_code(response, 204)


@pytest.mark.skip(
    reason="Same blocker as AUTH-013 - no API-only way to produce an expired "
    "refresh token to prove logout is idempotent for it too."
)
@allure.title("Logging out an already-expired token is idempotent")
@allure.tag("AUTH-017")
@allure.severity(allure.severity_level.NORMAL)
def test_logout_is_idempotent_for_an_expired_token():
    pass


@allure.title("A malformed refresh token on logout returns 401")
@allure.tag("AUTH-018")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_refresh_token_on_logout_returns_401(auth_client):
    response = auth_client.logout("not.a.token")

    assert_error(response, 401, "TOKEN_INVALID")


# ---------------------------------------------------------------------------
# Get current user
# ---------------------------------------------------------------------------


@allure.title("A valid access token returns the caller's identity")
@allure.tag("AUTH-019")
@allure.severity(allure.severity_level.CRITICAL)
def test_valid_access_token_returns_identity(auth_client, customer, seed_manifest):
    token_pair = auth_client.login(customer["email"], seed_manifest["password"]).json()

    response = auth_client.get_current_user(token_pair["access_token"])

    assert_status_code(response, 200)
    current_user = response.json()
    assert current_user["email"] == customer["email"]
    assert "CUSTOMER" in current_user["roles"]


@allure.title("No token returns 401")
@allure.tag("AUTH-020")
@allure.severity(allure.severity_level.CRITICAL)
def test_no_token_returns_401(api):
    response = api.get("/auth/me")

    assert_error(response, 401, "TOKEN_MISSING")


@allure.title("A malformed access token returns 401")
@allure.tag("AUTH-021")
@allure.severity(allure.severity_level.NORMAL)
def test_malformed_access_token_returns_401(auth_client):
    response = auth_client.get_current_user("not.a.token")

    assert_error(response, 401, "TOKEN_INVALID")


@allure.title("An expired access token returns 401")
@allure.tag("AUTH-022")
@allure.severity(allure.severity_level.CRITICAL)
def test_expired_access_token_returns_401(api, auth_client, customer):
    minted = api.post(
        "/test/token", json={"email": customer["email"], "ttl_seconds": 1}
    ).json()
    time.sleep(1.5)

    response = auth_client.get_current_user(minted["access_token"])

    assert_error(response, 401, "TOKEN_EXPIRED")


@allure.title("A token for a since-disabled user returns 401")
@allure.tag("AUTH-023")
@allure.severity(allure.severity_level.MINOR)
def test_token_for_a_since_disabled_user_returns_401(
    admin_client, factory, auth_client
):
    new_customer, token_pair = logged_in_customer(factory, auth_client)
    disable(admin_client, new_customer)

    response = auth_client.get_current_user(token_pair["access_token"])

    assert_error(response, 401, "USER_DISABLED")


# ---------------------------------------------------------------------------
# Update profile
# ---------------------------------------------------------------------------


@allure.title("A valid full_name update succeeds")
@allure.tag("AUTH-024")
@allure.severity(allure.severity_level.NORMAL)
def test_valid_full_name_update_succeeds(factory, auth_client):
    _, token_pair = logged_in_customer(factory, auth_client)

    new_name = fake.name()
    response = auth_client.update_profile(token_pair["access_token"], new_name)

    assert_status_code(response, 200)
    assert response.json()["full_name"] == new_name


@allure.title("Updating the profile without authentication returns 401")
@allure.tag("AUTH-025")
@allure.severity(allure.severity_level.NORMAL)
def test_update_profile_without_authentication_returns_401(api):
    response = api.patch("/auth/me", json={"full_name": "X"})

    assert_error(response, 401, "TOKEN_MISSING")


@allure.title("An invalid full_name returns 422")
@allure.tag("AUTH-026")
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.parametrize("full_name", ["", "x" * 256], ids=["empty", "over-max-length"])
def test_invalid_full_name_returns_422(factory, auth_client, full_name):
    _, token_pair = logged_in_customer(factory, auth_client)

    response = auth_client.update_profile(token_pair["access_token"], full_name)

    assert_error(response, 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@allure.title("Changing the password with the correct current password succeeds")
@allure.tag("AUTH-027")
@allure.severity(allure.severity_level.CRITICAL)
def test_change_password_with_correct_current_password_succeeds(factory, auth_client):
    new_customer, token_pair = logged_in_customer(factory, auth_client)
    current_password = new_customer["attributes"]["password"]

    response = auth_client.change_password(
        token_pair["access_token"], current_password, "NewStrongPass1"
    )

    assert_status_code(response, 204)
    old_login = auth_client.login(new_customer["attributes"]["email"], current_password)
    assert_error(old_login, 401, "INVALID_CREDENTIALS")
    new_login = auth_client.login(new_customer["attributes"]["email"], "NewStrongPass1")
    assert_status_code(new_login, 200)


@allure.title("Changing the password with the wrong current password returns 401")
@allure.tag("AUTH-028")
@allure.severity(allure.severity_level.CRITICAL)
def test_change_password_with_wrong_current_password_returns_401(factory, auth_client):
    new_customer, token_pair = logged_in_customer(factory, auth_client)

    response = auth_client.change_password(
        token_pair["access_token"], "WrongCurrent1", "NewStrongPass1"
    )

    assert_error(response, 401, "INVALID_CREDENTIALS")
    old_login = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    )
    assert_status_code(old_login, 200)


@allure.title("A weak new password returns 422")
@allure.tag("AUTH-029")
@allure.severity(allure.severity_level.NORMAL)
def test_weak_new_password_returns_422(factory, auth_client):
    new_customer, token_pair = logged_in_customer(factory, auth_client)

    response = auth_client.change_password(
        token_pair["access_token"], new_customer["attributes"]["password"], "weak"
    )

    assert_error(response, 422, "VALIDATION_ERROR")
    old_login = auth_client.login(
        new_customer["attributes"]["email"], new_customer["attributes"]["password"]
    )
    assert_status_code(old_login, 200)


@allure.title("Changing the password without authentication returns 401")
@allure.tag("AUTH-030")
@allure.severity(allure.severity_level.NORMAL)
def test_change_password_without_authentication_returns_401(api):
    response = api.post(
        "/auth/change-password",
        json={"current_password": "x", "new_password": "NewStrongPass1"},
    )

    assert_error(response, 401, "TOKEN_MISSING")
