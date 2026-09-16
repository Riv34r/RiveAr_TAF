"""Checkout, /checkout."""

from playwright.sync_api import Locator, Page

from core.ui.base_page import BasePage
from ui.pages.cart_page import CartLine, parse_money


class SummaryItem:
    """One product in checkout's order summary."""

    def __init__(self, row: Locator):
        self.name = row.get_by_role("paragraph").filter(has_not_text="$")
        self.quantity = row.get_by_text("Qty")
        self.line_total = row.get_by_text("$")

    def line(self) -> CartLine:
        return CartLine(
            name=self.name.inner_text(),
            quantity=int(self.quantity.inner_text().removeprefix("Qty ")),
            line_total=parse_money(self.line_total.inner_text()),
        )


class CheckoutPage(BasePage):
    path = "/checkout"

    def __init__(self, page: Page):
        super().__init__(page)
        self.summary_items = page.get_by_test_id("checkout-summary-item")

    def lines(self) -> list[CartLine]:
        """The order summary right now - wait for it to load before reading."""
        return [SummaryItem(row).line() for row in self.summary_items.all()]
