"""
Domain client for the current customer's saved addresses (/me/addresses).

Minimal by design: only what the orders scenarios need as a precondition
(creating an address to test cross-customer ownership). Not a full
addresses domain client - that belongs to its own scenario set if/when
one exists.

    addresses = AddressClient(api)
    addresses.create_address(
        recipient_name="Jane Doe", line1="1 Test St", city="Testville",
        postal_code="00000", country="US",
    )
"""

import requests

from core.api_client import ApiClient


class AddressClient:
    """Wraps an ApiClient to expose the /me/addresses operations used as order
    test setup."""

    def __init__(self, api: ApiClient):
        self.api = api

    def create_address(self, **payload) -> requests.Response:
        return self.api.post("/me/addresses", json=payload)
