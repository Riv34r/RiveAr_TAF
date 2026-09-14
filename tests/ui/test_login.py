"""Test cases for logging in and the browser's session.

Implements UI-LOGIN-01 through UI-LOGIN-10 from tests/ui/scenarios/login.md.
"""

import allure
import pytest
from playwright.sync_api import expect

from utils.helpers import step

pytestmark = allure.feature("UI: Login")


# ---------------------------------------------------------------------------
# Login form
# ---------------------------------------------------------------------------


@allure.title(
    "Valid credentials sign the customer in and the session survives a reload"
)
@allure.tag("UI-LOGIN-01")
@allure.severity(allure.severity_level.BLOCKER)
def test_valid_credentials_sign_the_customer_in(
    page, login_page, home_page, base_url, customer
):
    with step("Log in as the seeded customer"):
        login_page.open()
        login_page.login(customer["email"], customer["password"])

    with step("The storefront home opens with the customer signed in"):
        expect(page).to_have_url(f"{base_url}/")
        expect(home_page.navbar.account_menu_button).to_be_visible()
        expect(home_page.navbar.login_link).to_be_hidden()

    with step("Reload the page"):
        page.reload()

    with step("The customer is still signed in"):
        expect(home_page.navbar.account_menu_button).to_be_visible()


@allure.title("A rejected login is reported on the form and the customer can try again")
@allure.tag("UI-LOGIN-02")
@allure.severity(allure.severity_level.CRITICAL)
def test_rejected_login_is_reported_on_the_form(page, login_page, base_url, customer):
    with step("Log in with the wrong password"):
        login_page.open()
        login_page.login(customer["email"], "WrongPassword123!")

    with step("The API's message is shown and the form is ready for another try"):
        expect(login_page.error).to_have_text("Incorrect email or password.")
        expect(page).to_have_url(f"{base_url}/login")
        expect(login_page.email).to_have_value(customer["email"])
        expect(login_page.login_button).to_be_enabled()


INVALID_INPUT = [
    pytest.param(
        "",
        "",
        "Email is required.",
        "Password is required.",
        id="both-empty",
    ),
    pytest.param(
        "not-an-email",
        "Password123!",
        "Enter a valid email address.",
        "",
        id="malformed-email",
    ),
]


@allure.title("The form rejects empty and malformed input before sending anything")
@allure.tag("UI-LOGIN-03")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize("email,password,email_message,password_message", INVALID_INPUT)
def test_form_rejects_invalid_input_before_sending(
    page,
    login_page,
    base_url,
    requests_to,
    email,
    password,
    email_message,
    password_message,
):
    with step(f"Log in with the email {email!r} and the password {password!r}"):
        login_page.open()
        login_page.login(email, password)

    with step("Each field reports its own problem"):
        expect(login_page.email).to_have_accessible_description(email_message)
        expect(login_page.password).to_have_accessible_description(password_message)

    with step("Nothing was sent and the customer stays on the form"):
        assert requests_to("/auth/login") == []
        expect(page).to_have_url(f"{base_url}/login")


# ---------------------------------------------------------------------------
# Protected routes
# ---------------------------------------------------------------------------


@allure.title(
    "An anonymous visitor is sent to log in and brought back to the page they asked for"
)
@allure.tag("UI-LOGIN-04")
@allure.severity(allure.severity_level.CRITICAL)
def test_anonymous_visitor_is_brought_back_after_logging_in(
    page,
    order_detail_page,
    login_page,
    base_url,
    customer,
    customer_order,
):
    order_heading = order_detail_page.heading(customer_order["order_number"])

    with step("Open one of the customer's orders without a session"):
        order_detail_page.open(customer_order["id"])

    with step("The login form is shown instead of the order"):
        expect(page).to_have_url(f"{base_url}/login")
        expect(login_page.form).to_be_visible()
        expect(order_heading).to_have_count(0)

    with step("Log in as the seeded customer"):
        login_page.login(customer["email"], customer["password"])

    with step("The order that was asked for opens"):
        expect(page).to_have_url(f"{base_url}/orders/{customer_order['id']}")
        expect(order_heading).to_be_visible()


@allure.title("A session handed to the browser opens a protected route directly")
@allure.tag("UI-LOGIN-05")
@allure.severity(allure.severity_level.CRITICAL)
def test_session_handed_to_the_browser_opens_a_protected_route(
    customer_page, order_history_page, base_url, customer_order
):
    with step("Open the order history with the customer's session in storage"):
        order_history_page.open()

    with step("The order history is listed, with the customer signed in"):
        expect(order_history_page.order(customer_order["order_number"])).to_be_visible()
        expect(customer_page).to_have_url(f"{base_url}/orders")
        expect(order_history_page.navbar.account_menu_button).to_be_visible()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


@allure.title("Logging out ends the session in the browser")
@allure.tag("UI-LOGIN-06")
@allure.severity(allure.severity_level.CRITICAL)
def test_logging_out_ends_the_session(
    customer_page, order_history_page, home_page, base_url, customer_order
):
    with step("The customer is on their order history"):
        order_history_page.open()
        expect(order_history_page.order(customer_order["order_number"])).to_be_visible()

    with step("Log out from the account menu"):
        order_history_page.navbar.log_out()

    with step("The storefront home opens with the customer signed out"):
        expect(customer_page).to_have_url(f"{base_url}/")
        expect(home_page.navbar.login_link).to_be_visible()
        expect(home_page.navbar.account_menu_button).to_be_hidden()

    with step("Open the order history again"):
        order_history_page.open()

    with step("The customer is sent to log in"):
        expect(customer_page).to_have_url(f"{base_url}/login")


@allure.title("A stored session the API rejects is treated as signed out")
@allure.tag("UI-LOGIN-07")
@allure.severity(allure.severity_level.CRITICAL)
def test_stored_session_the_api_rejects_is_treated_as_signed_out(
    rejected_session_page, order_history_page, login_page, base_url, stored_tokens
):
    with step("Open the order history with tokens that no longer work"):
        order_history_page.open()

    with step("The login form is shown"):
        expect(rejected_session_page).to_have_url(f"{base_url}/login")
        expect(login_page.form).to_be_visible()

    with step("Neither token is left in storage"):
        assert stored_tokens() == {"access_token": None, "refresh_token": None}


@allure.title(
    "An access token that lapses mid-visit is renewed without interrupting the customer"
)
@allure.tag("UI-LOGIN-08")
@allure.severity(allure.severity_level.CRITICAL)
def test_access_token_lapsing_mid_visit_is_renewed(
    customer_page,
    home_page,
    order_history_page,
    base_url,
    customer_tokens,
    customer_order,
    expired_access_token,
    replace_access_token,
    stored_tokens,
):
    with step("The customer is on the storefront home"):
        home_page.open_signed_in()
        expect(home_page.navbar.account_menu_button).to_be_visible()

    with step("The access token lapses mid-visit"):
        replace_access_token(expired_access_token)

    with step("Go to the order history from the account menu"):
        home_page.navbar.open_order_history()

    with step("The order history is listed, with no detour to log in"):
        expect(order_history_page.order(customer_order["order_number"])).to_be_visible()
        expect(customer_page).to_have_url(f"{base_url}/orders")

    with step("The session was renewed"):
        refresh_token = stored_tokens()["refresh_token"]
        assert refresh_token is not None
        assert refresh_token != customer_tokens["refresh_token"]


@allure.title("A session that cannot be renewed mid-visit sends the customer to log in")
@allure.tag("UI-LOGIN-09")
@allure.severity(allure.severity_level.NORMAL)
def test_session_that_cannot_be_renewed_sends_the_customer_to_log_in(
    unrenewable_session_page,
    home_page,
    base_url,
    expired_access_token,
    replace_access_token,
    stored_tokens,
):
    with step("The customer is on the storefront home"):
        home_page.open_signed_in()
        expect(home_page.navbar.account_menu_button).to_be_visible()

    with step("The access token lapses mid-visit"):
        replace_access_token(expired_access_token)

    with step("Go to the order history from the account menu"):
        home_page.navbar.open_order_history()

    with step("The customer is sent to log in, with no tokens left"):
        expect(unrenewable_session_page).to_have_url(f"{base_url}/login")
        assert stored_tokens() == {"access_token": None, "refresh_token": None}


@allure.title(
    "A reload after the access token lapses signs the customer out, "
    "even with a renewable session"
)
@allure.tag("UI-LOGIN-10")
@allure.severity(allure.severity_level.NORMAL)
def test_reload_after_access_token_lapses_signs_the_customer_out(
    lapsed_session_page, order_history_page, base_url, requests_to, stored_tokens
):
    with step("Open the order history with a lapsed access token in storage"):
        order_history_page.open()

    with step("The customer is sent to log in without a renewal being tried"):
        expect(lapsed_session_page).to_have_url(f"{base_url}/login")
        assert requests_to("/auth/refresh") == []
        assert stored_tokens() == {"access_token": None, "refresh_token": None}
