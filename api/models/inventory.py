"""Pydantic models for inventory responses.

Mirrors ``app.schemas.inventory.InventoryResponse``/
``InventoryTransactionResponse`` in the SUT.
"""

import uuid
from datetime import datetime

from api.models.common import StrictModel


class InventoryResponse(StrictModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_sku: str
    warehouse: str
    stock: int
    reserved_stock: int
    available_stock: int
    reorder_threshold: int
    status: str
    created_at: datetime
    updated_at: datetime


class InventoryTransactionResponse(StrictModel):
    id: uuid.UUID
    type: str
    quantity_change: int
    stock_after: int | None
    order_id: uuid.UUID | None
    note: str | None
    created_by: uuid.UUID | None
    created_at: datetime
