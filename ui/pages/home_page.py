"""The storefront home, /."""

from urllib.parse import urlparse

from playwright.sync_api import Page

from ui.components.navbar import Navbar


class HomePage:
    def __init__(self, page: Page):
        self.page = page
        self.navbar = Navbar(page)

    def open_signed_in(self):
        """Open the home page as a signed-in customer and wait until it has settled.

        The customer's cart is the last request the page sends on its own, and
        it goes out after the navbar already shows the account menu - so a test
        that changes the stored session mid-visit has to wait for it.
        """
        with self.page.expect_response(
            lambda response: urlparse(response.url).path.endswith("/cart")
        ):
            self.page.goto("/")
