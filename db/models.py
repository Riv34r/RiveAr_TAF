"""
TAF's own ORM models for the tables its tests read.

These mirror the shape of RiveAr App's real schema (see
../RiveAr App/backend/app/models/*.py) closely enough to query and to
exercise its constraints.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Computed, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    stock: Mapped[int]
    reserved_stock: Mapped[int]
    available_stock: Mapped[int] = mapped_column(Computed("stock - reserved_stock"))


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # VARCHAR + CHECK in the SUT (native_enum=False), so a plain str maps it.
    type: Mapped[str]
    quantity_change: Mapped[int]


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    is_active: Mapped[bool]
    deleted_at: Mapped[datetime | None]


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str]
    usage_count: Mapped[int]


class PromotionUsage(Base):
    __tablename__ = "promotion_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    promotion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_number: Mapped[str]
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        Computed("subtotal - discount_total + tax_total + shipping_total"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int]
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), Computed("unit_price * quantity")
    )
