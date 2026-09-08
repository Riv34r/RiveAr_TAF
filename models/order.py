"""Pydantic models for order responses.

Mirrors ``app.schemas.order.OrderResponse`` and its nested shapes
(``OrderItemResponse``, ``PaymentResponse``, ``AddressResponse``,
``OrderStatusHistoryResponse``) in the SUT.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from models.common import StrictModel


class AddressResponse(StrictModel):
    id: uuid.UUID
    type: str
    recipient_name: str
    line1: str
    line2: str | None
    city: str
    state: str | None
    postal_code: str
    country: str
    phone: str | None
    is_default: bool
    created_at: datetime


class OrderItemResponse(StrictModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name_snapshot: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class PaymentResponse(StrictModel):
    id: uuid.UUID
    status: str
    method: str
    amount: Decimal
    transaction_reference: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderResponse(StrictModel):
    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    status: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    total: Decimal
    promotion_id: uuid.UUID | None
    shipping_address_id: uuid.UUID | None
    billing_address_id: uuid.UUID | None
    shipping_address: AddressResponse | None
    billing_address: AddressResponse | None
    items: list[OrderItemResponse]
    payment: PaymentResponse | None
    created_at: datetime
    updated_at: datetime


class OrderStatusHistoryResponse(StrictModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    changed_by: uuid.UUID | None
    note: str | None
    created_at: datetime
