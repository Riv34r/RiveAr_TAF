"""The cart, /cart."""

from dataclasses import dataclass
from decimal import Decimal

from playwright.sync_api import Page

from core.ui.base_page import BasePage


@dataclass
class CartLine:
    name: str
    quantity: int
    line_total: Decimal


class CartPage(BasePage):
    path = "/cart"

    def __init__(self, page: Page):
        super().__init__(page)
        self.items = page.get_by_test_id("cart-row")

    def lines(self) -> list[CartLine]:
        """What the cart shows right now - wait for it to load before reading."""
        return [
            CartLine(
                name=row.get_by_role("link").inner_text(),
                quantity=int(row.get_by_role("textbox").input_value()),
                # The Total column - its cell has no name of its own.
                line_total=Decimal(
                    row.get_by_role("cell").nth(3).inner_text().lstrip("$")
                ),
            )
            for row in self.items.all()
        ]
