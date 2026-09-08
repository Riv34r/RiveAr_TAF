"""
Domain client for cart endpoints (/cart/*).

Minimal by design: only what the orders checkout scenarios need as
preconditions (adding an item, reading the cart back). Not a full cart
domain client - that belongs to its own scenario set if/when one exists.

    cart = CartClient(api)
    cart.add_item(product_id, quantity=1)
"""

import requests

from core.api_client import ApiClient


class CartClient:
    """Wraps an ApiClient to expose the /cart/* operations used as order test setup."""

    def __init__(self, api: ApiClient):
        self.api = api

    def add_item(self, product_id, quantity: int) -> requests.Response:
        return self.api.post(
            "/cart/items", json={"product_id": str(product_id), "quantity": quantity}
        )

    def get_cart(self) -> requests.Response:
        return self.api.get("/cart")
