"""The login screen, /login."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.pages.home_page import HomePage


class LoginForm:
    def __init__(self, page: Page):
        form = page.get_by_test_id("login-form")
        self.email = form.get_by_role("textbox", name="Email")
        self.password = form.get_by_role("textbox", name="Password")
        self.login_button = form.get_by_role("button", name="Log in")
        self.errors = form.get_by_role("alert").or_(
            form.locator("[id$='-helper-text']")
        )


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page: Page):
        super().__init__(page)
        self.form = LoginForm(page)

    def login(self, account: dict, lands_on: type[BasePage] = HomePage):
        """Log in; returns the page a successful login lands on, the home by default."""
        self.form.email.fill(account["email"])
        self.form.password.fill(account["password"])
        self.form.login_button.click()
        return lands_on(self.page)
