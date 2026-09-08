"""
Shared response models used across every paginated endpoint.

Every list endpoint in RiveAr (products, inventory, orders, admin users,
audit logs, ...) wraps its items in the same {"items", "pagination"} shape -
one generic model validates all of them.

    from models.common import PaginatedResponse
    from models.product import ProductResponse

    body = PaginatedResponse[ProductResponse].model_validate(response.json())
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class StrictModel(BaseModel):
    """Base for every response model in this package.

    extra="forbid" so an undocumented field the SUT starts returning fails
    validation too, not just a missing/retyped one.
    """

    model_config = ConfigDict(extra="forbid")


class PaginationMeta(StrictModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(StrictModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta
