"""Test cases for /inventory/*.

Implements INV-001 through INV-018 from tests/scenarios/api/inventory.md.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

import allure
import pytest
from faker import Faker

from core.inventory_client import InventoryClient
from utils.helpers import assert_error, assert_status_code

pytestmark = allure.feature("Inventory")

fake = Faker()


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@allure.title("Listing inventory returns paginated results")
@allure.tag("INV-001")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_inventory_returns_paginated_results(inventory_client):
    response = inventory_client.list_inventory()

    assert_status_code(response, 200)
    body = response.json()
    assert "items" in body
    assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}


@allure.title("Filtering by status returns only matching records")
@allure.tag("INV-002")
@allure.severity(allure.severity_level.NORMAL)
def test_filtering_by_status_returns_only_matching_records(
    inventory_client, new_inventory
):
    sku = new_inventory["product_sku"]

    response = inventory_client.list_inventory(
        search=sku, status=new_inventory["status"]
    )

    assert_status_code(response, 200)
    items = response.json()["items"]
    assert [item["id"] for item in items] == [new_inventory["id"]]


@allure.title("Searching by product name or SKU returns the matching record")
@allure.tag("INV-003")
@allure.severity(allure.severity_level.NORMAL)
def test_searching_by_name_or_sku_returns_the_matching_record(
    inventory_client, factory
):
    name = fake.unique.company()
    product = factory("product", name=name)
    sku = product["attributes"]["sku"]

    by_name = inventory_client.list_inventory(search=name).json()["items"]
    by_sku = inventory_client.list_inventory(search=sku).json()["items"]

    assert any(item["product_sku"] == sku for item in by_name)
    assert any(item["product_sku"] == sku for item in by_sku)


@allure.title("An invalid sort_by returns 422 with the allowed values in the message")
@allure.tag("INV-004")
@allure.severity(allure.severity_level.MINOR)
def test_invalid_sort_by_returns_422(inventory_client):
    response = inventory_client.list_inventory(sort_by="not_a_real_column")

    error = assert_error(response, 422, "VALIDATION_ERROR")
    allowed = error["message"].split("Allowed values:")[1].strip(" .").split(", ")
    assert set(allowed) == {"available_stock", "created_at", "stock"}


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


@allure.title("Getting a known inventory record by ID succeeds")
@allure.tag("INV-005")
@allure.severity(allure.severity_level.CRITICAL)
def test_getting_a_known_inventory_record_by_id_succeeds(
    inventory_client, new_inventory
):
    response = inventory_client.get_inventory(new_inventory["id"])

    assert_status_code(response, 200)
    # Both endpoints build their response via the same to_response() -
    # identical for the same record, so this catches every field, not just
    # a hand-picked few.
    assert response.json() == new_inventory


@allure.title("Getting an unknown inventory ID returns 404")
@allure.tag("INV-006")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_inventory_id_returns_404(inventory_client):
    response = inventory_client.get_inventory(uuid.uuid4())

    assert_error(response, 404, "INVENTORY_NOT_FOUND")


# ---------------------------------------------------------------------------
# Adjust stock
# ---------------------------------------------------------------------------


@allure.title("A positive stock_delta increases stock")
@allure.tag("INV-007")
@allure.severity(allure.severity_level.CRITICAL)
def test_a_positive_stock_delta_increases_stock(inventory_client, new_inventory):
    response = inventory_client.adjust_stock(new_inventory["id"], stock_delta=5)

    assert_status_code(response, 200)
    body = response.json()
    assert body["stock"] == new_inventory["stock"] + 5
    assert body["available_stock"] == new_inventory["stock"] + 5


@allure.title("A negative stock_delta decreases stock")
@allure.tag("INV-008")
@allure.severity(allure.severity_level.NORMAL)
def test_a_negative_stock_delta_decreases_stock(inventory_client, new_inventory):
    response = inventory_client.adjust_stock(new_inventory["id"], stock_delta=-20)

    assert_status_code(response, 200)
    assert response.json()["stock"] == new_inventory["stock"] - 20


@allure.title("An adjustment that would take stock negative is rejected")
@allure.tag("INV-009")
@allure.severity(allure.severity_level.CRITICAL)
def test_adjustment_taking_stock_negative_is_rejected(inventory_client, new_inventory):
    response = inventory_client.adjust_stock(
        new_inventory["id"], stock_delta=-(new_inventory["stock"] + 1)
    )

    assert_error(response, 409, "INSUFFICIENT_STOCK")
    after = inventory_client.get_inventory(new_inventory["id"]).json()
    assert after["stock"] == new_inventory["stock"]


@pytest.mark.skip(
    reason="No API-only way to raise reserved_stock above 0 - see the "
    "Blocker note on INV-010 in tests/scenarios/api/inventory.md"
)
@allure.title("An adjustment that would leave stock below reserved_stock is rejected")
@allure.tag("INV-010")
@allure.severity(allure.severity_level.NORMAL)
def test_adjustment_below_reserved_stock_is_rejected():
    pass


@allure.title("Adjusting stock records a transaction with the given reason")
@allure.tag("INV-011")
@allure.severity(allure.severity_level.CRITICAL)
def test_adjusting_stock_records_a_transaction(inventory_client, new_inventory):
    response = inventory_client.adjust_stock(
        new_inventory["id"], stock_delta=7, reason="Restock"
    )

    assert_status_code(response, 200)
    new_stock = response.json()["stock"]

    transactions = inventory_client.list_transactions(new_inventory["id"]).json()[
        "items"
    ]
    entry = next((t for t in transactions if t["quantity_change"] == 7), None)
    assert entry is not None, "No transaction found for the adjustment just made"
    assert entry["stock_after"] == new_stock
    assert entry["note"] == "Restock"


@allure.title(
    "Stock crossing the reorder threshold recomputes status through all three states"
)
@allure.tag("INV-012")
@allure.severity(allure.severity_level.CRITICAL)
def test_status_recomputed_across_the_reorder_threshold(
    factory, inventory_for, inventory_client
):
    product = factory("product", stock=0)
    record = inventory_for(product["attributes"]["sku"])
    assert record["status"] == "OUT_OF_STOCK"

    low = inventory_client.adjust_stock(record["id"], stock_delta=15)
    assert_status_code(low, 200)
    assert low.json()["status"] == "LOW_STOCK"

    in_stock = inventory_client.adjust_stock(record["id"], stock_delta=1)
    assert_status_code(in_stock, 200)
    assert in_stock.json()["status"] == "IN_STOCK"


@allure.title("Adjusting an unknown inventory ID returns 404")
@allure.tag("INV-013")
@allure.severity(allure.severity_level.NORMAL)
def test_adjusting_an_unknown_inventory_id_returns_404(inventory_client):
    response = inventory_client.adjust_stock(uuid.uuid4(), stock_delta=1)

    assert_error(response, 404, "INVENTORY_NOT_FOUND")


@pytest.mark.xfail(
    reason="BUG-003: adjust_stock has no row lock - see BUGS.md", strict=True
)
@allure.title("Concurrent stock adjustments can lose writes")
@allure.tag("INV-014")
@allure.severity(allure.severity_level.CRITICAL)
def test_concurrent_stock_adjustments_can_lose_writes(inventory_client, new_inventory):
    concurrency = 20

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        responses = list(
            pool.map(
                lambda _: inventory_client.adjust_stock(
                    new_inventory["id"], stock_delta=1
                ),
                range(concurrency),
            )
        )

    assert all(r.status_code == 200 for r in responses)
    final_stock = inventory_client.get_inventory(new_inventory["id"]).json()["stock"]
    assert final_stock == new_inventory["stock"] + concurrency


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------


@allure.title("Transaction history lists entries in reverse-chronological order")
@allure.tag("INV-015")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_lists_entries_reverse_chronologically(
    inventory_client, new_inventory
):
    inventory_client.adjust_stock(new_inventory["id"], stock_delta=5)
    inventory_client.adjust_stock(new_inventory["id"], stock_delta=-3)

    response = inventory_client.list_transactions(new_inventory["id"])

    assert_status_code(response, 200)
    body = response.json()
    assert "pagination" in body
    changes = [t["quantity_change"] for t in body["items"][:2]]
    assert changes == [-3, 5]


@allure.title("Transaction history for an unknown inventory ID returns 404")
@allure.tag("INV-016")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_for_an_unknown_inventory_id_returns_404(inventory_client):
    response = inventory_client.list_transactions(uuid.uuid4())

    assert_error(response, 404, "INVENTORY_NOT_FOUND")


@allure.title("Transaction history is scoped to its own inventory record")
@allure.tag("INV-017")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_is_scoped_to_its_own_record(
    factory, inventory_for, inventory_client
):
    first_product = factory("product")
    second_product = factory("product")
    first = inventory_for(first_product["attributes"]["sku"])
    second = inventory_for(second_product["attributes"]["sku"])

    inventory_client.adjust_stock(first["id"], stock_delta=11)
    inventory_client.adjust_stock(second["id"], stock_delta=22)

    response = inventory_client.list_transactions(first["id"])

    assert_status_code(response, 200)
    changes = [t["quantity_change"] for t in response.json()["items"]]
    assert 11 in changes
    assert 22 not in changes


# ---------------------------------------------------------------------------
# Permission boundary
# ---------------------------------------------------------------------------


@allure.title("Inventory endpoints require inventory:manage")
@allure.tag("INV-018")
@allure.severity(allure.severity_level.CRITICAL)
def test_inventory_endpoints_require_inventory_manage(api, customer_inventory):
    no_token = InventoryClient(api).list_inventory()
    assert_error(no_token, 401, "TOKEN_MISSING")

    wrong_permission = customer_inventory.list_inventory()
    assert_error(wrong_permission, 403, "INSUFFICIENT_PERMISSIONS")
