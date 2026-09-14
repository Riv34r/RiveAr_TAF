"""The customer's order history, /orders."""

from playwright.sync_api import Locator, Page

from ui.components.navbar import Navbar


class OrderHistoryPage:
    def __init__(self, page: Page):
        self.page = page
        self.navbar = Navbar(page)

    def open(self):
        self.page.goto("/orders")

    def order(self, order_number: str) -> Locator:
        """An order's entry in the list - a link to that order."""
        return self.page.get_by_role("link", name=order_number)
