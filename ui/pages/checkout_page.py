"""Checkout, /checkout."""

from decimal import Decimal

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.pages.cart_page import CartLine


class CheckoutPage(BasePage):
    path = "/checkout"

    def __init__(self, page: Page):
        super().__init__(page)
        self.summary_items = page.get_by_test_id("checkout-summary-item")

    def lines(self) -> list[CartLine]:
        """The order summary right now - wait for it to load before reading."""
        lines = []
        for row in self.summary_items.all():
            text = row.inner_text().splitlines()
            name, quantity, line_total = [line for line in text if line]
            lines.append(
                CartLine(
                    name=name,
                    quantity=int(quantity.removeprefix("Qty ")),
                    line_total=Decimal(line_total.lstrip("$")),
                )
            )
        return lines
