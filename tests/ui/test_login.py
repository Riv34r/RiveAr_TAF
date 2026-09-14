"""Test cases for logging in and the browser's session.

Implements scenarios from tests/ui/scenarios/login.md.
"""

import allure
from playwright.sync_api import expect

from utils.helpers import step

pytestmark = allure.feature("UI: Login")


def expect_signed_in(navbar):
    """The navbar shows the account menu in place of the Log in link."""
    expect(navbar.account_menu_button).to_be_visible()
    expect(navbar.login_link).to_be_hidden()


@allure.title(
    "Valid credentials sign the customer in and the session survives a reload"
)
@allure.tag("UI-LOGIN-01")
@allure.severity(allure.severity_level.BLOCKER)
def test_valid_credentials_sign_the_customer_in(login_page, customer):
    with step("Log in as the seeded customer"):
        login_page.open()
        home_page = login_page.login(customer)

    with step("The storefront home opens with the customer signed in"):
        expect(home_page.page).to_have_url(home_page.path)
        expect_signed_in(home_page.navbar)

    with step("The customer stays signed in after a reload"):
        home_page.page.reload()
        expect_signed_in(home_page.navbar)
