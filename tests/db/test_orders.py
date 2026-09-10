"""DB rules on the orders and order_items tables (tests/db/scenarios/orders.md)."""

from decimal import Decimal

import allure
from sqlalchemy import delete, select, text, update

from db.models import Order, OrderItem
from utils.helpers import assert_rejected, step

pytestmark = allure.feature("DB: Orders")


@allure.title("orders.total follows its formula")
@allure.tag("DB-ORD-01")
@allure.severity(allure.severity_level.CRITICAL)
def test_order_total_matches_the_formula(db_session):
    with step("Read every order"):
        rows = db_session.execute(select(Order)).scalars().all()

    with step("Each total is subtotal - discount + tax + shipping"):
        assert rows
        for row in rows:
            assert row.total == (
                row.subtotal - row.discount_total + row.tax_total + row.shipping_total
            )


@allure.title("order_items.line_total follows its formula")
@allure.tag("DB-ORD-02")
@allure.severity(allure.severity_level.CRITICAL)
def test_line_total_matches_the_formula(db_session):
    with step("Read every order line"):
        rows = db_session.execute(select(OrderItem)).scalars().all()

    with step("Each line total is unit price times quantity"):
        assert rows
        for row in rows:
            assert row.line_total == row.unit_price * row.quantity


@allure.title("a discount cannot drive the order total negative")
@allure.tag("DB-ORD-03")
@allure.severity(allure.severity_level.NORMAL)
def test_discount_cannot_make_total_negative(db_session):
    with step("Given any order"):
        row = db_session.execute(select(Order).limit(1)).scalar_one()

    with step("A discount larger than the order is refused"):
        assert_rejected(
            db_session,
            update(Order)
            .where(Order.id == row.id)
            .values(discount_total=Decimal("999999.99")),
            constraint="ck_orders_total_non_negative",
        )


@allure.title("an order line's quantity must be positive")
@allure.tag("DB-ORD-04")
@allure.severity(allure.severity_level.NORMAL)
def test_order_item_quantity_must_be_positive(db_session):
    with step("Given any order line"):
        row = db_session.execute(select(OrderItem).limit(1)).scalar_one()

    with step("Setting its quantity to zero is refused"):
        assert_rejected(
            db_session,
            update(OrderItem).where(OrderItem.id == row.id).values(quantity=0),
            constraint="ck_order_items_quantity_positive",
        )


@allure.title("deleting an order removes its line items")
@allure.tag("DB-ORD-05")
@allure.severity(allure.severity_level.NORMAL)
def test_deleting_an_order_cascades_to_line_items(db_session, count_rows):
    with step("Given an order that has line items"):
        order_id = db_session.execute(select(OrderItem.order_id).limit(1)).scalar_one()
        assert count_rows(OrderItem.order_id == order_id) > 0

    with step("Delete the order"):
        db_session.execute(delete(Order).where(Order.id == order_id))

    with step("Its line items go with it"):
        assert count_rows(OrderItem.order_id == order_id) == 0


@allure.title("a customer with orders cannot be deleted")
@allure.tag("DB-ORD-06")
@allure.severity(allure.severity_level.NORMAL)
def test_a_customer_with_orders_cannot_be_deleted(db_session):
    with step("Given a customer who has placed an order"):
        customer_id = db_session.execute(
            select(Order.customer_id).limit(1)
        ).scalar_one()

    with step("Deleting them is refused"):
        assert_rejected(
            db_session,
            text("DELETE FROM customers WHERE id = :id").bindparams(id=customer_id),
            sqlstate="23503",
        )


@allure.title("order_number is unique")
@allure.tag("DB-ORD-07")
@allure.severity(allure.severity_level.MINOR)
def test_order_number_is_unique(db_session):
    with step("Given two orders"):
        first, second = db_session.execute(select(Order).limit(2)).scalars().all()

    with step("Giving one the other's order number is refused"):
        assert_rejected(
            db_session,
            update(Order)
            .where(Order.id == first.id)
            .values(order_number=second.order_number),
            sqlstate="23505",
        )
