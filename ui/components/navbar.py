"""The storefront's top bar, shown on every storefront screen."""

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.ui.base_page import BasePage


class Navbar:
    def __init__(self, page: Page):
        self.page = page
        # The footer has its own "Log in" link, so look only inside the top bar.
        bar = page.get_by_role("banner")
        self.login_link = bar.get_by_role("link", name="Log in")
        self.account_menu_button = bar.get_by_role("button", name="Open account menu")
        self.logout_item = page.get_by_role("menuitem", name="Log out")

    def logout(self, lands_on: type[BasePage]):
        """Log out from the account menu; returns the page it lands on."""
        try:
            self.account_menu_button.click()
        except PlaywrightTimeoutError:
            raise RuntimeError(
                "Can't log out: no one is signed in - the navbar has no account menu"
            ) from None
        self.logout_item.click()
        return lands_on(self.page)
