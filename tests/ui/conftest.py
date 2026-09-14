"""Fixtures for the UI suite."""

import os

import pytest

from ui.pages.login_page import LoginPage


@pytest.fixture(scope="session")
def base_url() -> str:
    """The front end's own URL - what pytest-playwright resolves page.goto() against."""
    return os.environ["UI_BASE_URL"].rstrip("/")


@pytest.fixture
def login_page(page) -> LoginPage:
    """The login screen, bound to this test's page."""
    return LoginPage(page)
