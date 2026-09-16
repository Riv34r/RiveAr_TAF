"""Test cases for the cart in the browser.

Implements scenarios from tests/ui/scenarios/cart.md.
"""

import allure
from playwright.sync_api import expect

from ui.pages.cart_page import CartPage
from ui.pages.checkout_page import CheckoutPage
from ui.pages.login_page import LoginPage
from utils.helpers import step

pytestmark = allure.feature("UI: Cart")


def wait_for_empty_guest_cart(page):
    """Wait until the browser holds no guest cart - a login's merge is done."""
    page.wait_for_function("() => localStorage.getItem('rivear_guest_cart') === null")


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


@allure.title("Logging in carries the guest cart into the customer's cart exactly once")
@allure.tag("UI-CART-02")
@allure.severity(allure.severity_level.CRITICAL)
def test_logging_in_carries_the_guest_cart_over_exactly_once(
    product_details_page, new_customer, new_product_line
):
    with step("The guest cart holds two of the product"):
        product_details_page.add_to_cart(quantity=2)

    with step("Log in as a fresh customer"):
        login_page = product_details_page.navbar.open_login()
        home_page = login_page.login(new_customer["attributes"])

    with step("The guest cart the browser held is emptied"):
        wait_for_empty_guest_cart(home_page.page)

    with step("The cart lists the product with quantity 2"):
        cart_page = home_page.navbar.open_cart()
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=2)]

    with step("After a reload, the cart still lists it with quantity 2"):
        cart_page.page.reload()
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=2)]


@allure.title(
    "A guest line the server refuses is dropped on login and the customer is told"
)
@allure.tag("UI-CART-03")
@allure.severity(allure.severity_level.NORMAL)
def test_guest_line_the_server_refuses_is_dropped_on_login(
    login_page, refused_guest_cart, new_customer, new_product_line
):
    with step("Log in as a fresh customer"):
        home_page = login_page.login(new_customer["attributes"])

    with step("The customer is warned that one item couldn't be added"):
        expect(home_page.toast).to_have_text(
            "One item from your cart couldn't be added"
            " — it may be out of stock or no longer available."
        )

    with step("The guest cart the browser held is emptied"):
        wait_for_empty_guest_cart(home_page.page)

    with step("The cart lists only the product that was in stock"):
        cart_page = home_page.navbar.open_cart()
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=1)]


@allure.title(
    "A guest proceeding to checkout logs in and comes back to checkout with the cart"
)
@allure.tag("UI-CART-04")
@allure.severity(allure.severity_level.CRITICAL)
def test_guest_proceeding_to_checkout_comes_back_to_it_with_the_cart(
    product_details_page, new_customer, new_product_line
):
    with step("The guest cart holds two of the product"):
        product_details_page.add_to_cart(quantity=2)

    with step("Proceed to checkout from the cart"):
        cart_page = product_details_page.navbar.open_cart()
        login_page = cart_page.proceed_to_checkout(lands_on=LoginPage)

    with step("The guest is sent to log in"):
        expect(login_page.page).to_have_url(login_page.path)

    with step("Log in as a fresh customer"):
        checkout_page = login_page.login(
            new_customer["attributes"], lands_on=CheckoutPage
        )

    with step("The browser lands back on checkout"):
        expect(checkout_page.page).to_have_url(checkout_page.path)

    with step("The order summary lists the product with quantity 2"):
        expect(checkout_page.summary_items).to_have_count(1)
        assert checkout_page.lines() == [new_product_line(quantity=2)]


@allure.title("Reloading checkout sends a customer with a full cart back to the cart")
@allure.tag("UI-CART-05")
@allure.severity(allure.severity_level.NORMAL)
def test_reloading_checkout_sends_a_customer_with_a_full_cart_to_the_cart(
    login_page, new_customer_cart, new_customer, new_product_line
):
    """Pins BUG-006 as it is - flips to staying on checkout once it is fixed."""
    # TODO: flip to "checkout stays open with the cart" once BUG-006 is fixed
    with step("Log in and proceed to checkout from the cart"):
        home_page = login_page.login(new_customer["attributes"])
        cart_page = home_page.navbar.open_cart()
        checkout_page = cart_page.proceed_to_checkout(lands_on=CheckoutPage)

    with step("Checkout shows the order summary"):
        expect(checkout_page.summary_items).to_have_count(1)

    with step("After a reload, the browser lands on the cart"):
        checkout_page.page.reload()
        expect(checkout_page.page).to_have_url(CartPage.path)

    with step("The cart still lists the product with quantity 2"):
        expect(cart_page.items).to_have_count(1)
        assert cart_page.lines() == [new_product_line(quantity=2)]
