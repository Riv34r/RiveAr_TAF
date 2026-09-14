"""The storefront's top bar, shown on every storefront screen."""

from playwright.sync_api import Page


class Navbar:
    def __init__(self, page: Page):
        # The footer has its own "Log in" link, so look only inside the top bar.
        bar = page.get_by_role("banner")
        self.login_link = bar.get_by_role("link", name="Log in")
        self.account_menu_button = bar.get_by_role("button", name="Open account menu")
