"""A customer's order, /orders/<id>."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage


class OrderDetailsPage(BasePage):
    path = "/orders/{id}"

    def __init__(self, page: Page):
        super().__init__(page)
        self.order_number = page.get_by_role("heading", level=5)
