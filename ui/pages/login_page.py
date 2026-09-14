"""The login screen, /login."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.pages.home_page import HomePage


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page: Page):
        super().__init__(page)
        form = page.get_by_test_id("login-form")
        self.email = form.get_by_role("textbox", name="Email")
        self.password = form.get_by_role("textbox", name="Password")
        self.login_button = form.get_by_role("button", name="Log in")

    def login(self, account: dict, expected_errors: bool = False) -> HomePage | None:
        """Log in with the account; returns the home unless errors are expected."""
        self.email.fill(account["email"])
        self.password.fill(account["password"])
        self.login_button.click()
        if expected_errors:
            return None
        return HomePage(self.page)
