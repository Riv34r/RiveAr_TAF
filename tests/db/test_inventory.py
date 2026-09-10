"""DB rules on the inventory table (tests/db/scenarios/inventory.md)."""

import uuid

import allure
from sqlalchemy import delete, select, update

from db.models import Inventory, InventoryTransaction
from utils.helpers import assert_rejected, step

pytestmark = allure.feature("DB: Inventory")


@allure.title("available_stock is always stock minus reserved_stock")
@allure.tag("DB-INV-01")
@allure.severity(allure.severity_level.CRITICAL)
def test_available_stock_matches_the_formula(db_session):
    with step("Read every inventory row"):
        rows = db_session.execute(select(Inventory)).scalars().all()

    with step("Each one's available_stock is the difference of the other two"):
        assert rows
        for row in rows:
            assert row.available_stock == row.stock - row.reserved_stock


@allure.title("reserved_stock cannot exceed stock")
@allure.tag("DB-INV-02")
@allure.severity(allure.severity_level.NORMAL)
def test_reserved_stock_cannot_exceed_stock(db_session):
    with step("Given an inventory row holding stock"):
        row = db_session.execute(
            select(Inventory).where(Inventory.stock > 0).limit(1)
        ).scalar_one()

    with step("Reserving one more than it holds is refused"):
        assert_rejected(
            db_session,
            update(Inventory)
            .where(Inventory.id == row.id)
            .values(reserved_stock=row.stock + 1),
            constraint="ck_inventory_reserved_not_exceeding_stock",
        )


@allure.title("reserved_stock cannot be negative")
@allure.tag("DB-INV-03")
@allure.severity(allure.severity_level.MINOR)
def test_reserved_stock_cannot_be_negative(db_session):
    with step("Given an inventory row holding stock"):
        row = db_session.execute(
            select(Inventory).where(Inventory.stock > 0).limit(1)
        ).scalar_one()

    with step("Reserving a negative amount is refused"):
        assert_rejected(
            db_session,
            update(Inventory).where(Inventory.id == row.id).values(reserved_stock=-1),
            constraint="ck_inventory_reserved_stock_non_negative",
        )


@allure.title("product_id must reference a real product")
@allure.tag("DB-INV-04")
@allure.severity(allure.severity_level.NORMAL)
def test_product_id_must_reference_a_real_product(db_session):
    with step("Given any inventory row"):
        row = db_session.execute(select(Inventory).limit(1)).scalar_one()

    with step("Pointing it at a product that does not exist is refused"):
        assert_rejected(
            db_session,
            update(Inventory)
            .where(Inventory.id == row.id)
            .values(product_id=uuid.uuid4()),
            sqlstate="23503",
        )


@allure.title("deleting an inventory record removes its transactions")
@allure.tag("DB-INV-05")
@allure.severity(allure.severity_level.NORMAL)
def test_deleting_inventory_cascades_to_transactions(db_session, count_rows):
    with step("Given an inventory record that has transactions"):
        inventory_id = db_session.execute(
            select(InventoryTransaction.inventory_id).limit(1)
        ).scalar_one()
        assert count_rows(InventoryTransaction.inventory_id == inventory_id) > 0

    with step("Delete the record"):
        db_session.execute(delete(Inventory).where(Inventory.id == inventory_id))

    with step("Its transactions go with it"):
        assert count_rows(InventoryTransaction.inventory_id == inventory_id) == 0
