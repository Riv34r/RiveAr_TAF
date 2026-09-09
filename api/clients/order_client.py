"""
Domain client for order endpoints (/orders/*).

    orders = OrderClient(api)
    orders.create_order(items=[{"product_id": pid, "quantity": 1}])
    orders.update_status(order_id, status="CANCELLED")
"""

import requests

from core.api.api_client import ApiClient


class OrderClient:
    """Wraps an ApiClient to expose /orders/* operations without inline payloads."""

    def __init__(self, api: ApiClient):
        self.api = api

    def list_orders(self, **params) -> requests.Response:
        return self.api.get("/orders", params=params)

    def create_order(self, idempotency_key: str = None, **payload) -> requests.Response:
        headers = (
            {"Idempotency-Key": idempotency_key} if idempotency_key is not None else {}
        )
        return self.api.post("/orders", json=payload, headers=headers)

    def checkout(self, idempotency_key: str = None, **payload) -> requests.Response:
        headers = (
            {"Idempotency-Key": idempotency_key} if idempotency_key is not None else {}
        )
        return self.api.post("/orders/checkout", json=payload, headers=headers)

    def get_order(self, order_id) -> requests.Response:
        return self.api.get(f"/orders/{order_id}")

    def update_status(
        self, order_id, status: str, note: str = None
    ) -> requests.Response:
        payload = {"status": status}
        if note is not None:
            payload["note"] = note
        return self.api.patch(f"/orders/{order_id}/status", json=payload)

    def list_status_history(self, order_id) -> requests.Response:
        return self.api.get(f"/orders/{order_id}/status-history")

    def process_payment(
        self, order_id, outcome: str = "success", method: str = None
    ) -> requests.Response:
        payload = {"outcome": outcome}
        if method is not None:
            payload["method"] = method
        return self.api.post(f"/orders/{order_id}/payment/process", json=payload)
