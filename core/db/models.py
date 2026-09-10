"""
TAF's own ORM models for the tables the DB suite touches.

These mirror the shape of RiveAr App's real schema (see
../RiveAr App/backend/app/models/*.py) closely enough to query and to
exercise its constraints.
"""

import uuid
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
