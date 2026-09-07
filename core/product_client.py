"""
Domain client for product catalog endpoints (/products/*).

    products = ProductClient(api)
    products.list_products(search="lamp")
    products.update_product(product_id, price="19.99")

PUT/DELETE require an If-Match precondition; it defaults to "*" ("any
current version"). Pass if_match=None to omit the header entirely.
"""

import requests

from core.api_client import ApiClient


class ProductClient:
    """Wraps an ApiClient to expose /products/* operations without inline payloads."""

    def __init__(self, api: ApiClient):
        self.api = api

    def list_products(self, **params) -> requests.Response:
        return self.api.get("/products", params=params)

    def get_product(self, product_id) -> requests.Response:
        return self.api.get(f"/products/{product_id}")

    def create_product(self, **payload) -> requests.Response:
        return self.api.post("/products", json=payload)

    def update_product(
        self, product_id, if_match: str = "*", **payload
    ) -> requests.Response:
        headers = {"If-Match": if_match} if if_match is not None else {}
        return self.api.put(f"/products/{product_id}", json=payload, headers=headers)

    def delete_product(self, product_id, if_match: str = "*") -> requests.Response:
        headers = {"If-Match": if_match} if if_match is not None else {}
        return self.api.delete(f"/products/{product_id}", headers=headers)

    def restore_product(self, product_id) -> requests.Response:
        return self.api.post(f"/products/{product_id}/restore")

    def bulk_products(self, ids, action: str, mode: str = None) -> requests.Response:
        payload = {"ids": [str(i) for i in ids], "action": action}
        if mode is not None:
            payload["mode"] = mode
        return self.api.post("/products/bulk", json=payload)
