"""The storefront home, /."""

from playwright.sync_api import Page

from core.ui.base_page import BasePage
from ui.components.navbar import Navbar


class HomePage(BasePage):
    path = "/"

    def __init__(self, page: Page):
        super().__init__(page)
        self.navbar = Navbar(page)
