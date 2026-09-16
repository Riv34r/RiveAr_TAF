"""The base every page object builds on."""

from playwright.sync_api import Page


class BasePage:
    path: str

    def __init__(self, page: Page):
        self.page = page

    def open(self, **params):
        self.page.goto(self.path.format(**params))
        return self
