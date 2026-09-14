"""A single order of the customer's, /orders/:orderId."""

from playwright.sync_api import Locator, Page


class OrderDetailPage:
    def __init__(self, page: Page):
        self.page = page

    def open(self, order_id: str):
        self.page.goto(f"/orders/{order_id}")

    def heading(self, order_number: str) -> Locator:
        return self.page.get_by_role("heading", name=order_number, exact=True)
