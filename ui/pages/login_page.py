"""The login screen, /login."""

from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self.form = page.get_by_test_id("login-form")
        self.email = self.form.get_by_role("textbox", name="Email")
        self.password = self.form.get_by_role("textbox", name="Password")
        self.login_button = self.form.get_by_role("button", name="Log in")
        self.error = self.form.get_by_role("alert")

    def open(self):
        self.page.goto("/login")

    def login(self, email: str, password: str):
        self.email.fill(email)
        self.password.fill(password)
        self.login_button.click()
