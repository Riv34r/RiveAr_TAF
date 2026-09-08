"""Pydantic models for product responses.

Mirrors ``app.schemas.product.ProductResponse``/``CategorySummary`` and
``app.schemas.bulk.BulkOperationResponse`` in the SUT.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from models.common import StrictModel


class CategorySummary(StrictModel):
    """The minimal category shape embedded in ProductResponse.categories -
    not the full CategoryResponse."""

    id: uuid.UUID
    name: str
    slug: str


class ProductResponse(StrictModel):
    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    image_url: str | None
    price: Decimal
    discount_price: Decimal | None
    effective_price: Decimal
    average_rating: Decimal
    rating_count: int
    is_active: bool
    deleted_at: datetime | None
    version: int
    categories: list[CategorySummary]
    available_stock: int | None
    inventory_status: str | None
    created_at: datetime
    updated_at: datetime


class BulkItemResult(StrictModel):
    id: uuid.UUID
    success: bool
    code: str | None = None
    message: str | None = None


class BulkSummary(StrictModel):
    total: int
    succeeded: int
    failed: int


class BulkOperationResponse(StrictModel):
    mode: str
    applied: bool
    summary: BulkSummary
    results: list[BulkItemResult]
