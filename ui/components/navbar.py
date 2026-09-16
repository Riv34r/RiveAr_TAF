"""The storefront's top bar, shown on every storefront screen."""

from playwright.sync_api import Page


class Navbar:
    def __init__(self, page: Page):
        self.page = page
        # The footer has its own "Log in" link, so look only inside the top bar.
        bar = page.get_by_role("banner")
        self.login_link = bar.get_by_role("link", name="Log in")
        self.cart_link = bar.get_by_role("link", name="View cart")
        self.account_menu_button = bar.get_by_role("button", name="Open account menu")
        self.order_history_item = page.get_by_role("menuitem", name="Order history")
        self.logout_item = page.get_by_role("menuitem", name="Log out")

    def open_account_menu(self):
        """Open the account menu, which only a signed-in user has."""
        self.account_menu_button.click()

    def open_login(self):
        """Go to the login screen from the navbar."""
        from ui.pages.login_page import LoginPage

        self.login_link.click()
        return LoginPage(self.page)

    def open_cart(self):
        """Go to the cart from the navbar."""
        from ui.pages.cart_page import CartPage

        self.cart_link.click()
        return CartPage(self.page)

    def open_order_history(self):
        """Go to the order history from the account menu."""
        from ui.pages.order_history_page import OrderHistoryPage

        self.open_account_menu()
        self.order_history_item.click()
        return OrderHistoryPage(self.page)

    def logout(self):
        """Log out from the account menu; it lands on the storefront home."""
        from ui.pages.home_page import HomePage

        self.open_account_menu()
        self.logout_item.click()
        return HomePage(self.page)
