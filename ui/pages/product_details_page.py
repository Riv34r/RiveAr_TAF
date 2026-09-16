"""A product's page, /products/<id>."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.components.navbar import Navbar


class ProductDetailsPage(BasePage):
    path = "/products/{id}"

    def __init__(self, page: Page):
        super().__init__(page)
        self.navbar = Navbar(page)
        self.quantity = page.get_by_test_id("product-detail-quantity").get_by_role(
            "textbox"
        )
        self.add_to_cart_button = page.get_by_role("button", name="Add to cart")

    def add_to_cart(self, quantity: int):
        """Add the given quantity of the product to the cart."""
        self.quantity.fill(str(quantity))
        self.add_to_cart_button.click()
