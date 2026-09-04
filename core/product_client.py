"""
Domain client for product catalog endpoints (/products/*).

    products = ProductClient(api)
    products.list_products(search="lamp")
    products.update_product(product_id, price="19.99")

PUT/DELETE require an If-Match precondition; it defaults to "*" ("any
current version") since optimistic-concurrency behaviour itself is a
separate scenario set - see tests/scenarios/api/products.md.
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
        return self.api.put(
            f"/products/{product_id}", json=payload, headers={"If-Match": if_match}
        )

    def delete_product(self, product_id, if_match: str = "*") -> requests.Response:
        return self.api.delete(
            f"/products/{product_id}", headers={"If-Match": if_match}
        )

    def restore_product(self, product_id) -> requests.Response:
        return self.api.post(f"/products/{product_id}/restore")
