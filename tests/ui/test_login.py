"""Test cases for logging in and the browser's session.

Implements scenarios from tests/ui/scenarios/login.md.
"""

import allure
import pytest
from playwright.sync_api import expect

from ui.pages.login_page import LoginPage
from ui.pages.order_details_page import OrderDetailsPage
from utils.helpers import assert_status_code, step

pytestmark = allure.feature("UI: Login")


def expect_signed_in(navbar):
    """The navbar shows the account menu in place of the Log in link."""
    expect(navbar.account_menu_button).to_be_visible()
    expect(navbar.login_link).to_be_hidden()


def watch_requests(page, path: str) -> list[str]:
    """A list that fills with the URLs of requests the page sends to `path`."""
    sent = []

    def record(request):
        if request.url.endswith(path):
            sent.append(request.url)

    page.on("request", record)
    return sent


def stored_tokens(page) -> list:
    """The access and refresh tokens the front end holds now, None where gone."""
    return page.evaluate(
        "['rivear_access_token', 'rivear_refresh_token']"
        ".map(key => localStorage.getItem(key))"
    )


def replace_access_token(page, token: str):
    """Swap the access token the front end holds, as a lapsed one would leave it."""
    page.evaluate("token => localStorage.setItem('rivear_access_token', token)", token)


@allure.title(
    "Valid credentials sign the customer in and the session survives a reload"
)
@allure.tag("UI-LOGIN-01")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_valid_credentials_sign_the_customer_in(login_page, customer):
    with step("Log in as the seeded customer"):
        home_page = login_page.login(customer)

    with step("The storefront home opens with the customer signed in"):
        expect(home_page.page).to_have_url(home_page.path)
        expect_signed_in(home_page.navbar)

    with step("The customer stays signed in after a reload"):
        home_page.page.reload()
        expect_signed_in(home_page.navbar)


@allure.title("A rejected login is reported on the form and the customer can try again")
@allure.tag("UI-LOGIN-02")
@allure.severity(allure.severity_level.CRITICAL)
def test_rejected_login_is_reported_on_the_form(login_page, customer):
    with step("Log in with the wrong password"):
        login_page.login({**customer, "password": "WrongPassword123!"})

    with step("The form reports it and is ready for another try"):
        expect(login_page.form.errors).to_have_text(["Incorrect email or password."])
        expect(login_page.page).to_have_url(login_page.path)
        expect(login_page.form.email).to_have_value(customer["email"])
        expect(login_page.form.login_button).to_be_enabled()


INVALID_INPUT = [
    pytest.param(
        "", "", ["Email is required.", "Password is required."], id="both-empty"
    ),
    pytest.param(
        "not-an-email",
        "Password123!",
        ["Enter a valid email address."],
        id="malformed-email",
    ),
]


@allure.title("The form rejects empty and malformed input before sending anything")
@allure.tag("UI-LOGIN-03")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize("email,password,messages", INVALID_INPUT)
def test_form_rejects_invalid_input_before_sending(
    login_page, email, password, messages
):
    login_requests = watch_requests(login_page.page, "/auth/login")

    with step(f"Log in with the email {email!r} and the password {password!r}"):
        login_page.login({"email": email, "password": password})

    with step("The form shows exactly these errors"):
        expect(login_page.form.errors).to_have_text(messages)

    with step("Nothing was sent, and the customer stays on the form"):
        assert login_requests == []
        expect(login_page.page).to_have_url(login_page.path)


@allure.title(
    "An anonymous visitor is sent to log in "
    "and brought back to the page they asked for"
)
@allure.tag("UI-LOGIN-04")
@allure.severity(allure.severity_level.CRITICAL)
def test_anonymous_visitor_is_brought_back_after_logging_in(
    login_page, customer, customer_order
):
    order_path = OrderDetailsPage.path.format(id=customer_order.id)

    with step("Open one of the customer's orders without a session"):
        login_page.page.goto(order_path)

    with step("The visitor is sent to log in"):
        expect(login_page.page).to_have_url(login_page.path)

    with step("Log in as the seeded customer"):
        order_details_page = login_page.login(customer, lands_on=OrderDetailsPage)

    with step("The order that was asked for opens"):
        expect(order_details_page.page).to_have_url(order_path)
        expect(order_details_page.order_number).to_have_text(
            customer_order.order_number
        )


@allure.title("A session handed to the browser opens a protected route directly")
@allure.tag("UI-LOGIN-05")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_session_handed_to_the_browser_opens_a_protected_route(
    customer_page, order_history_page
):
    with step("The customer's order history is listed, with the customer signed in"):
        expect(order_history_page.orders.first).to_be_visible()
        expect_signed_in(order_history_page.navbar)

    with step("The customer was not sent to log in"):
        expect(order_history_page.page).to_have_url(order_history_page.path)


@allure.title("Logging out ends the session in the browser")
@allure.tag("UI-LOGIN-06")
@allure.severity(allure.severity_level.CRITICAL)
def test_logging_out_ends_the_session_in_the_browser(customer_page, order_history_page):
    with step("Log out from the account menu"):
        home_page = order_history_page.navbar.logout()

    with step("The storefront home opens with the customer signed out"):
        expect(home_page.page).to_have_url(home_page.path)
        expect(home_page.navbar.login_link).to_be_visible()
        expect(home_page.navbar.account_menu_button).to_be_hidden()

    with step("Opening the order history again asks to log in"):
        order_history_page.open()
        expect(order_history_page.page).to_have_url(LoginPage.path)


@allure.title("A stored session the API rejects is treated as signed out")
@allure.tag("UI-LOGIN-07")
@allure.severity(allure.severity_level.CRITICAL)
def test_rejected_stored_session_is_treated_as_signed_out(
    rejected_session_page, order_history_page
):
    with step("The order history sends the customer to log in"):
        expect(order_history_page.page).to_have_url(LoginPage.path)

    with step("Neither token is left in the browser"):
        assert stored_tokens(order_history_page.page) == [None, None]


@allure.title(
    "An access token that lapses mid-visit is renewed "
    "without interrupting the customer"
)
@allure.tag("UI-LOGIN-08")
@allure.severity(allure.severity_level.CRITICAL)
def test_access_token_lapsing_mid_visit_is_renewed(
    customer_page, home_page, customer_tokens, expired_access_token
):
    with step("The customer is signed in on the storefront home"):
        expect_signed_in(home_page.navbar)

    with step("The access token lapses mid-visit"):
        replace_access_token(home_page.page, expired_access_token)

    with step("Go to the order history from the account menu"):
        order_history_page = home_page.navbar.open_order_history()

    with step("The order history is listed, without being sent to log in"):
        expect(order_history_page.orders.first).to_be_visible()
        expect(order_history_page.page).to_have_url(order_history_page.path)

    with step("The session was renewed with a new refresh token"):
        _, refresh_token = stored_tokens(order_history_page.page)
        assert refresh_token not in (None, customer_tokens["refresh_token"])


@allure.title("A session that cannot be renewed mid-visit sends the customer to log in")
@allure.tag("UI-LOGIN-09")
@allure.severity(allure.severity_level.NORMAL)
def test_session_that_cannot_be_renewed_mid_visit_sends_to_log_in(
    unrenewable_session_page, home_page, expired_access_token
):
    with step("The customer is signed in on the storefront home"):
        expect_signed_in(home_page.navbar)

    with step("The access token lapses mid-visit"):
        replace_access_token(home_page.page, expired_access_token)

    with step("Go to the order history from the account menu"):
        home_page.navbar.open_order_history()

    with step("The customer is sent to log in"):
        expect(home_page.page).to_have_url(LoginPage.path)

    with step("Neither token is left in the browser"):
        assert stored_tokens(home_page.page) == [None, None]


@allure.title(
    "A reload after the access token lapses signs the customer out, "
    "even with a renewable session"
)
@allure.tag("UI-LOGIN-10")
@allure.severity(allure.severity_level.NORMAL)
def test_lapsed_access_token_signs_the_customer_out_on_load(
    lapsed_session_page, order_history_page, auth_client, customer_tokens
):
    # TODO: flip to "stays signed in" once BUG-005 is fixed
    with step("The order history sends the customer to log in"):
        expect(order_history_page.page).to_have_url(LoginPage.path)

    with step("Neither token is left in the browser"):
        assert stored_tokens(order_history_page.page) == [None, None]

    with step("The refresh token was never tried - the API still honours it"):
        assert_status_code(auth_client.refresh(customer_tokens["refresh_token"]), 200)
