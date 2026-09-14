"""The base every page object builds on."""

from playwright.sync_api import Page


class BasePage:
    path: str

    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto(self.path)
