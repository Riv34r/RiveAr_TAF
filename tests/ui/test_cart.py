"""Test cases for the cart in the browser.

Implements scenarios from tests/ui/scenarios/cart.md.
"""

import allure
from playwright.sync_api import expect

from utils.helpers import step

pytestmark = allure.feature("UI: Cart")


@allure.title("A product a guest adds is in the cart once and survives a reload")
@allure.tag("UI-CART-01")
@allure.severity(allure.severity_level.CRITICAL)
def test_product_a_guest_adds_is_in_the_cart_once_after_a_reload(
    product_details_page, new_product_line
):
    with step("Add one of the product from its page"):
        product_details_page.add_to_cart(quantity=1)

    with step("Add two more of the same product"):
        product_details_page.add_to_cart(quantity=2)

    with step("The navbar's cart count shows 3"):
        expect(product_details_page.navbar.cart_link).to_have_text("3")

    with step("Open the cart from the navbar"):
        cart_page = product_details_page.navbar.open_cart()

    with step("The cart lists the product once, with quantity 3"):
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=3)]

    with step("After a reload, the cart still lists it"):
        cart_page.page.reload()
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=3)]
