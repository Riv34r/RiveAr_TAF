"""Test cases for /inventory/*.

Implements INV-001 through INV-021 from tests/api/scenarios/inventory.md.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

import allure
import pytest
from faker import Faker

from api.clients.inventory_client import InventoryClient
from api.models.inventory import InventoryResponse, InventoryTransactionResponse
from utils.helpers import assert_error, assert_status_code, step

pytestmark = allure.feature("Inventory")

fake = Faker()


# ---------------------------------------------------------------------------
# Permission boundary
# ---------------------------------------------------------------------------


@allure.title("Inventory endpoints require inventory:manage")
@allure.tag("INV-001")
@allure.severity(allure.severity_level.CRITICAL)
def test_inventory_endpoints_require_inventory_manage(api, customer_inventory):
    with step("Without a token the request is turned away"):
        no_token = InventoryClient(api).list_inventory()
        assert_error(no_token, 401, "TOKEN_MISSING")

    with step("With a token but no inventory:manage it is forbidden"):
        wrong_permission = customer_inventory.list_inventory()
        assert_error(wrong_permission, 403, "INSUFFICIENT_PERMISSIONS")


INVENTORY_ENDPOINTS = [
    ("list_inventory", lambda c: c.list_inventory()),
    ("get_inventory", lambda c: c.get_inventory(uuid.uuid4())),
    ("adjust_stock", lambda c: c.adjust_stock(uuid.uuid4(), stock_delta=1)),
    ("list_transactions", lambda c: c.list_transactions(uuid.uuid4())),
]


@allure.title("Every inventory endpoint requires authentication - {name}")
@allure.tag("INV-002")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize(
    "name,call", INVENTORY_ENDPOINTS, ids=[e[0] for e in INVENTORY_ENDPOINTS]
)
def test_inventory_endpoints_require_authentication(api, name, call):
    with step(f"Call {name} without a token"):
        response = call(InventoryClient(api))

    with step("The request is turned away"):
        assert_error(response, 401, "TOKEN_MISSING")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


@allure.title("Inventory response matches the InventoryResponse schema")
@allure.tag("INV-003")
@allure.severity(allure.severity_level.NORMAL)
def test_inventory_response_matches_schema(new_inventory):
    with step("The record validates against InventoryResponse"):
        InventoryResponse.model_validate(new_inventory)


@allure.title(
    "Inventory transaction response matches the InventoryTransactionResponse schema"
)
@allure.tag("INV-004")
@allure.severity(allure.severity_level.NORMAL)
def test_inventory_transaction_response_matches_schema(inventory_client, new_inventory):
    with step("Adjust the stock, producing a transaction"):
        inventory_client.adjust_stock(
            new_inventory["id"], stock_delta=1, reason="Restock"
        )

    with step("Read the transaction history"):
        response = inventory_client.list_transactions(new_inventory["id"])

    with step("Every entry validates against InventoryTransactionResponse"):
        assert_status_code(response, 200)
        items = response.json()["items"]
        assert items
        for item in items:
            InventoryTransactionResponse.model_validate(item)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@allure.title("Listing inventory returns paginated results")
@allure.tag("INV-005")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_inventory_returns_paginated_results(inventory_client):
    with step("List inventory"):
        response = inventory_client.list_inventory()

    with step("The response is a paginated envelope"):
        assert_status_code(response, 200)
        body = response.json()
        assert "items" in body
        assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}


@allure.title("Filtering by status returns only matching records")
@allure.tag("INV-006")
@allure.severity(allure.severity_level.NORMAL)
def test_filtering_by_status_returns_only_matching_records(
    inventory_client, new_inventory
):
    sku = new_inventory["product_sku"]
    actual_status = new_inventory["status"]
    other_status = next(
        s for s in ("IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK") if s != actual_status
    )

    with step(f"Filtering by its real status ({actual_status}) finds the record"):
        matching = inventory_client.list_inventory(search=sku, status=actual_status)
        assert_status_code(matching, 200)
        assert [item["id"] for item in matching.json()["items"]] == [
            new_inventory["id"]
        ]

    # search=sku alone would already narrow to this one record, so a wrong
    # status has to come back empty - otherwise the filter would be a no-op.
    with step(f"Filtering by any other status ({other_status}) finds nothing"):
        non_matching = inventory_client.list_inventory(search=sku, status=other_status)
        assert non_matching.json()["items"] == []


@allure.title("Searching by product name or SKU returns the matching record")
@allure.tag("INV-007")
@allure.severity(allure.severity_level.NORMAL)
def test_searching_by_name_or_sku_returns_the_matching_record(
    inventory_client, factory
):
    with step("Given a product with a distinctive name"):
        name = fake.unique.company()
        product = factory("product", name=name)
        sku = product["attributes"]["sku"]

    with step("Search by name and by SKU"):
        by_name = inventory_client.list_inventory(search=name).json()["items"]
        by_sku = inventory_client.list_inventory(search=sku).json()["items"]

    with step("Both searches find its inventory record"):
        assert any(item["product_sku"] == sku for item in by_name)
        assert any(item["product_sku"] == sku for item in by_sku)


@allure.title("An invalid sort_by returns 422 with the allowed values in the message")
@allure.tag("INV-008")
@allure.severity(allure.severity_level.MINOR)
def test_invalid_sort_by_returns_422(inventory_client):
    with step("Sort by a column that does not exist"):
        response = inventory_client.list_inventory(sort_by="not_a_real_column")

    with step("The error names every column that would have worked"):
        error = assert_error(response, 422, "VALIDATION_ERROR")
        allowed = error["message"].split("Allowed values:")[1].strip(" .").split(", ")
        assert set(allowed) == {"available_stock", "created_at", "stock"}


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


@allure.title("Getting a known inventory record by ID succeeds")
@allure.tag("INV-009")
@allure.severity(allure.severity_level.CRITICAL)
def test_getting_a_known_inventory_record_by_id_succeeds(
    inventory_client, new_inventory
):
    with step("Fetch the record by ID"):
        response = inventory_client.get_inventory(new_inventory["id"])

    # Both endpoints build their response via the same to_response() -
    # identical for the same record, so this catches every field, not just
    # a hand-picked few.
    with step("It matches the record the listing gave, field for field"):
        assert_status_code(response, 200)
        assert response.json() == new_inventory


@allure.title("Getting an unknown inventory ID returns 404")
@allure.tag("INV-010")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_inventory_id_returns_404(inventory_client):
    with step("Fetch an inventory ID that does not exist"):
        response = inventory_client.get_inventory(uuid.uuid4())

    with step("The record is not found"):
        assert_error(response, 404, "INVENTORY_NOT_FOUND")


# ---------------------------------------------------------------------------
# Adjust stock
# ---------------------------------------------------------------------------


@allure.title("A positive stock_delta increases stock")
@allure.tag("INV-011")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_a_positive_stock_delta_increases_stock(inventory_client, new_inventory):
    with step("Add 5 to the stock"):
        response = inventory_client.adjust_stock(new_inventory["id"], stock_delta=5)

    with step("Stock and available_stock both rise by 5"):
        assert_status_code(response, 200)
        body = response.json()
        assert body["stock"] == new_inventory["stock"] + 5
        assert body["available_stock"] == new_inventory["stock"] + 5


@allure.title("A negative stock_delta decreases stock")
@allure.tag("INV-012")
@allure.severity(allure.severity_level.NORMAL)
def test_a_negative_stock_delta_decreases_stock(inventory_client, new_inventory):
    with step("Take 20 off the stock"):
        response = inventory_client.adjust_stock(new_inventory["id"], stock_delta=-20)

    with step("Stock falls by 20"):
        assert_status_code(response, 200)
        assert response.json()["stock"] == new_inventory["stock"] - 20


@allure.title("An adjustment that would take stock negative is rejected")
@allure.tag("INV-013")
@allure.severity(allure.severity_level.CRITICAL)
def test_adjustment_taking_stock_negative_is_rejected(inventory_client, new_inventory):
    with step("Take off one more than the record holds"):
        response = inventory_client.adjust_stock(
            new_inventory["id"], stock_delta=-(new_inventory["stock"] + 1)
        )

    with step("The adjustment is refused"):
        assert_error(response, 409, "INSUFFICIENT_STOCK")

    with step("The stock is left where it was"):
        after = inventory_client.get_inventory(new_inventory["id"]).json()
        assert after["stock"] == new_inventory["stock"]


@pytest.mark.skip(
    reason="No API-only way to raise reserved_stock above 0 - see the "
    "Blocker note on INV-014 in tests/api/scenarios/inventory.md"
)
@allure.title("An adjustment that would leave stock below reserved_stock is rejected")
@allure.tag("INV-014")
@allure.severity(allure.severity_level.NORMAL)
def test_adjustment_below_reserved_stock_is_rejected():
    pass


@allure.title("Adjusting stock records a transaction with the given reason")
@allure.tag("INV-015")
@allure.severity(allure.severity_level.CRITICAL)
def test_adjusting_stock_records_a_transaction(inventory_client, new_inventory):
    with step("Add 7 to the stock, giving a reason"):
        response = inventory_client.adjust_stock(
            new_inventory["id"], stock_delta=7, reason="Restock"
        )
        assert_status_code(response, 200)
        new_stock = response.json()["stock"]

    with step("The history carries that adjustment, its result and its reason"):
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
@allure.tag("INV-016")
@allure.severity(allure.severity_level.CRITICAL)
def test_status_recomputed_across_the_reorder_threshold(
    factory, inventory_for, inventory_client
):
    with step("Given a product with no stock at all"):
        product = factory("product", stock=0)
        record = inventory_for(product["attributes"]["sku"])
        assert record["status"] == "OUT_OF_STOCK"

    with step("Stocking up to below the reorder point makes it LOW_STOCK"):
        low = inventory_client.adjust_stock(record["id"], stock_delta=15)
        assert_status_code(low, 200)
        assert low.json()["status"] == "LOW_STOCK"

    with step("One more unit takes it over the threshold, to IN_STOCK"):
        in_stock = inventory_client.adjust_stock(record["id"], stock_delta=1)
        assert_status_code(in_stock, 200)
        assert in_stock.json()["status"] == "IN_STOCK"


@allure.title("Adjusting an unknown inventory ID returns 404")
@allure.tag("INV-017")
@allure.severity(allure.severity_level.NORMAL)
def test_adjusting_an_unknown_inventory_id_returns_404(inventory_client):
    with step("Adjust an inventory ID that does not exist"):
        response = inventory_client.adjust_stock(uuid.uuid4(), stock_delta=1)

    with step("The record is not found"):
        assert_error(response, 404, "INVENTORY_NOT_FOUND")


# strict=True is deliberate: a real fix should surface as a hard failure
# (unremoved marker), not a silent XFAIL. Trade-off: a lucky interleaving
# could occasionally XPASS - accepted given how reliably this reproduced.
@pytest.mark.xfail(
    reason="BUG-003: adjust_stock has no row lock - see BUGS.md", strict=True
)
@allure.title("Concurrent stock adjustments can lose writes")
@allure.tag("INV-018")
@allure.severity(allure.severity_level.CRITICAL)
def test_concurrent_stock_adjustments_can_lose_writes(inventory_client, new_inventory):
    concurrency = 20

    with step(f"Add a unit {concurrency} times at once"):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            responses = list(
                pool.map(
                    lambda _: inventory_client.adjust_stock(
                        new_inventory["id"], stock_delta=1
                    ),
                    range(concurrency),
                )
            )

    with step("Every call succeeded and every unit landed"):
        assert all(r.status_code == 200 for r in responses)
        final = inventory_client.get_inventory(new_inventory["id"]).json()["stock"]
        assert final == new_inventory["stock"] + concurrency


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------


@allure.title("Transaction history lists entries in reverse-chronological order")
@allure.tag("INV-019")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_lists_entries_reverse_chronologically(
    inventory_client, new_inventory
):
    with step("Make two adjustments, one after the other"):
        inventory_client.adjust_stock(new_inventory["id"], stock_delta=5)
        inventory_client.adjust_stock(new_inventory["id"], stock_delta=-3)

    with step("Read the transaction history"):
        response = inventory_client.list_transactions(new_inventory["id"])

    with step("The most recent adjustment comes first"):
        assert_status_code(response, 200)
        body = response.json()
        assert "pagination" in body
        changes = [t["quantity_change"] for t in body["items"][:2]]
        assert changes == [-3, 5]


@allure.title("Transaction history for an unknown inventory ID returns 404")
@allure.tag("INV-020")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_for_an_unknown_inventory_id_returns_404(inventory_client):
    with step("Read the history of an inventory ID that does not exist"):
        response = inventory_client.list_transactions(uuid.uuid4())

    with step("The record is not found"):
        assert_error(response, 404, "INVENTORY_NOT_FOUND")


@allure.title("Transaction history is scoped to its own inventory record")
@allure.tag("INV-021")
@allure.severity(allure.severity_level.NORMAL)
def test_transaction_history_is_scoped_to_its_own_record(
    factory, inventory_for, inventory_client
):
    with step("Given two products, each with its own inventory record"):
        first_product = factory("product")
        second_product = factory("product")
        first = inventory_for(first_product["attributes"]["sku"])
        second = inventory_for(second_product["attributes"]["sku"])

    with step("Adjust each by a different amount"):
        inventory_client.adjust_stock(first["id"], stock_delta=11)
        inventory_client.adjust_stock(second["id"], stock_delta=22)

    with step("Read the first record's history"):
        response = inventory_client.list_transactions(first["id"])

    with step("It holds its own adjustment and not the other record's"):
        assert_status_code(response, 200)
        changes = [t["quantity_change"] for t in response.json()["items"]]
        assert 11 in changes
        assert 22 not in changes
