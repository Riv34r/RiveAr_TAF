"""Test cases for logging in and the browser's session.

Implements scenarios from tests/ui/scenarios/login.md.
"""

import allure
import pytest
from playwright.sync_api import expect

from ui.pages.order_details_page import OrderDetailsPage
from utils.helpers import step

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


@allure.title(
    "Valid credentials sign the customer in and the session survives a reload"
)
@allure.tag("UI-LOGIN-01")
@allure.severity(allure.severity_level.BLOCKER)
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
