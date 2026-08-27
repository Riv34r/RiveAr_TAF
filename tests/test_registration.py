"""Test cases for customer registration (POST /api/v1/auth/register)."""

import allure
import pytest
from faker import Faker

from models.auth import TokenResponse

pytestmark = allure.feature("Registration")

fake = Faker()


@allure.title("Registering with valid details creates a customer and returns tokens")
@allure.tag("REG-01")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_register_creates_customer_and_returns_tokens(auth_client):
    email = fake.unique.email()
    response = auth_client.register(email, "StrongPass1", fake.name())

    assert response.status_code == 201
    tokens = TokenResponse.model_validate(response.json())
    assert tokens.token_type == "bearer"
    assert tokens.expires_in > 0

    # The account is immediately usable with the returned access token.
    me = auth_client.get_current_user(tokens.access_token).json()
    assert me["email"] == email
    assert me["roles"] == ["CUSTOMER"]
    assert me["is_active"] is True


@allure.title("Registering with an already-registered email returns 409")
@allure.tag("REG-02")
@allure.severity(allure.severity_level.CRITICAL)
def test_register_with_duplicate_email_returns_409(auth_client):
    """Relies on 'customer@rivear.local' existing in seed data."""
    response = auth_client.register("customer@rivear.local", "StrongPass1", "Duplicate")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@allure.title("Registering with a malformed email returns 422")
@allure.tag("REG-03")
@allure.severity(allure.severity_level.NORMAL)
def test_register_with_malformed_email_returns_422(auth_client):
    response = auth_client.register("not-an-email", "StrongPass1", "X")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@allure.title("Registering with a password that fails strength rules returns 422")
@allure.tag("REG-04")
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

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@allure.title("Registering with a missing required field returns 422")
@allure.tag("REG-05")
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

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
