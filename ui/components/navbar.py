"""The storefront's top bar, shown on every storefront screen."""

from playwright.sync_api import Page


class Navbar:
    def __init__(self, page: Page):
        self.page = page
        bar = page.get_by_role("banner")
        self.login_link = bar.get_by_role("link", name="Log in")
        self.account_menu_button = bar.get_by_role("button", name="Open account menu")
        account_menu = page.get_by_role("menu")
        self.order_history_item = account_menu.get_by_role(
            "menuitem", name="Order history"
        )
        self.log_out_item = account_menu.get_by_role("menuitem", name="Log out")

    def open_order_history(self):
        self.account_menu_button.click()
        self.order_history_item.click()

    def log_out(self):
        self.account_menu_button.click()
        self.log_out_item.click()
