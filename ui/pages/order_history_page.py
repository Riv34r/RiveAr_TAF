"""The customer's order history, /orders."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.components.navbar import Navbar


class OrderHistoryPage(BasePage):
    path = "/orders"

    def __init__(self, page: Page):
        super().__init__(page)
        self.navbar = Navbar(page)
        self.orders = page.get_by_test_id("order-history-list").get_by_role("link")
