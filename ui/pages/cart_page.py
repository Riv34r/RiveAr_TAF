"""The cart, /cart."""

from dataclasses import dataclass
from decimal import Decimal

from playwright.sync_api import Locator, Page

from core.ui.base_page import BasePage


@dataclass
class CartLine:
    name: str
    quantity: int
    line_total: Decimal


def parse_money(text: str) -> Decimal:
    """'$1,234.50' as it's displayed -> Decimal('1234.50')."""
    return Decimal(text.lstrip("$").replace(",", ""))


class CartRow:
    """One product in the cart's table."""

    def __init__(self, row: Locator, total_column: int):
        self.name = row.get_by_role("link")
        self.quantity = row.get_by_role("textbox")
        self.line_total = row.get_by_role("cell").nth(total_column)

    def line(self) -> CartLine:
        return CartLine(
            name=self.name.inner_text(),
            quantity=int(self.quantity.input_value()),
            line_total=parse_money(self.line_total.inner_text()),
        )


class CartPage(BasePage):
    path = "/cart"

    def __init__(self, page: Page):
        super().__init__(page)
        self.items = page.get_by_test_id("cart-row")
        self.column_headers = page.get_by_role("columnheader")
        self.checkout_button = page.get_by_role("button", name="Proceed to checkout")

    def proceed_to_checkout(self, lands_on: type[BasePage]):
        """Proceed to checkout; returns where it lands - login, for a guest."""
        self.checkout_button.click()
        return lands_on(self.page)

    def lines(self) -> list[CartLine]:
        """What the cart shows right now - wait for it to load before reading."""
        # The Total cell has no name of its own, so find its column by the header.
        total_column = self.column_headers.all_inner_texts().index("Total")
        return [CartRow(row, total_column).line() for row in self.items.all()]
