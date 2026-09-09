"""
Domain client for inventory endpoints (/inventory/*).

    inventory = InventoryClient(api)
    inventory.list_inventory(status="LOW_STOCK")
    inventory.adjust_stock(inventory_id, stock_delta=-5, reason="Damaged in transit")
"""

import requests

from core.api.api_client import ApiClient


class InventoryClient:
    """Wraps an ApiClient to expose /inventory/* operations without inline payloads."""

    def __init__(self, api: ApiClient):
        self.api = api

    def list_inventory(self, **params) -> requests.Response:
        return self.api.get("/inventory", params=params)

    def get_inventory(self, inventory_id) -> requests.Response:
        return self.api.get(f"/inventory/{inventory_id}")

    def adjust_stock(
        self, inventory_id, stock_delta: int, reason: str = None
    ) -> requests.Response:
        payload = {"stock_delta": stock_delta}
        if reason is not None:
            payload["reason"] = reason
        return self.api.patch(f"/inventory/{inventory_id}", json=payload)

    def list_transactions(self, inventory_id, **params) -> requests.Response:
        return self.api.get(f"/inventory/{inventory_id}/transactions", params=params)
