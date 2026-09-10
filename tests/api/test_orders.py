"""Test cases for /orders/*.

Implements ORD-001 through ORD-040 from tests/api/scenarios/orders.md.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import allure
import pytest
from sqlalchemy import select

from api.clients.address_client import AddressClient
from api.clients.order_client import OrderClient
from api.models.order import OrderResponse, OrderStatusHistoryResponse
from db.models import InventoryTransaction, Promotion, PromotionUsage
from utils.helpers import assert_error, assert_paginated_response, assert_status_code

pytestmark = allure.feature("Orders")


# ---------------------------------------------------------------------------
# Permission boundary
# ---------------------------------------------------------------------------


@allure.title("Orders endpoints require authentication")
@allure.tag("ORD-001")
@allure.severity(allure.severity_level.CRITICAL)
def test_orders_endpoints_require_authentication(api):
    response = OrderClient(api).list_orders()

    assert_error(response, 401, "TOKEN_MISSING")


ORDER_ENDPOINTS = [
    ("list_orders", lambda c: c.list_orders()),
    ("create_order", lambda c: c.create_order(items=[])),
    ("checkout", lambda c: c.checkout()),
    ("get_order", lambda c: c.get_order(uuid.uuid4())),
    ("update_status", lambda c: c.update_status(uuid.uuid4(), status="CANCELLED")),
    ("list_status_history", lambda c: c.list_status_history(uuid.uuid4())),
    ("process_payment", lambda c: c.process_payment(uuid.uuid4())),
]


@allure.title("Every order endpoint requires authentication - {name}")
@allure.tag("ORD-002")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize(
    "name,call", ORDER_ENDPOINTS, ids=[e[0] for e in ORDER_ENDPOINTS]
)
def test_order_endpoints_require_authentication(api, name, call):
    response = call(OrderClient(api))

    assert_error(response, 401, "TOKEN_MISSING")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


@allure.title("Order response matches the OrderResponse schema")
@allure.tag("ORD-003")
@allure.severity(allure.severity_level.NORMAL)
def test_order_response_matches_schema(customer_orders, new_product):
    address = AddressClient(customer_orders.api).create_address(
        recipient_name="Test",
        line1="1 Test St",
        city="Testville",
        postal_code="00000",
        country="US",
    )
    created = customer_orders.create_order(
        items=[{"product_id": new_product["entity_id"], "quantity": 1}],
        shipping_address_id=address.json()["id"],
    )
    assert_status_code(created, 201)
    order_id = created.json()["id"]

    response = customer_orders.process_payment(order_id, outcome="success")

    assert_status_code(response, 200)
    body = OrderResponse.model_validate(response.json())
    assert body.items
    assert body.payment is not None
    assert body.shipping_address is not None


@allure.title("Status history response matches the OrderStatusHistoryResponse schema")
@allure.tag("ORD-004")
@allure.severity(allure.severity_level.NORMAL)
def test_status_history_response_matches_schema(customer_orders, new_order):
    order_id = new_order["id"]
    customer_orders.update_status(order_id, status="CANCELLED", note="Changed my mind")

    response = customer_orders.list_status_history(order_id)

    assert_status_code(response, 200)
    items = response.json()
    assert items
    for item in items:
        OrderStatusHistoryResponse.model_validate(item)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@allure.title("Listing orders returns paginated results")
@allure.tag("ORD-005")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_orders_returns_paginated_results(customer_orders):
    response = customer_orders.list_orders()

    assert_paginated_response(response)


@allure.title("A customer's order list is scoped to their own orders")
@allure.tag("ORD-006")
@allure.severity(allure.severity_level.CRITICAL)
def test_customer_order_list_is_scoped_to_their_own(
    customer_orders, new_customer_orders, new_order, factory
):
    _, other_orders = new_customer_orders()
    other_product = factory("product", stock=10)
    other = other_orders.create_order(
        items=[{"product_id": other_product["entity_id"], "quantity": 1}]
    )
    other_id = other.json()["id"]

    response = customer_orders.list_orders(page_size=100)

    ids = [o["id"] for o in response.json()["items"]]
    assert new_order["id"] in ids
    assert other_id not in ids


@allure.title("Staff can list all orders and filter by customer_id")
@allure.tag("ORD-007")
@allure.severity(allure.severity_level.NORMAL)
def test_staff_can_filter_orders_by_customer_id(order_client, new_order):
    order_id = new_order["id"]

    response = order_client.list_orders(customer_id=new_order["customer_id"])

    body = assert_paginated_response(response)
    assert [o["id"] for o in body["items"]] == [order_id]


@allure.title("An invalid sort_by returns 422 with the allowed values in the message")
@allure.tag("ORD-008")
@allure.severity(allure.severity_level.MINOR)
def test_invalid_sort_by_returns_422(customer_orders):
    response = customer_orders.list_orders(sort_by="not_a_real_column")

    error = assert_error(response, 422, "VALIDATION_ERROR")
    allowed = error["message"].split("Allowed values:")[1].strip(" .").split(", ")
    assert set(allowed) == {"created_at", "order_number", "total"}


# ---------------------------------------------------------------------------
# Create order
# ---------------------------------------------------------------------------


@allure.title("Creating an order with valid items succeeds")
@allure.tag("ORD-009")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_creating_an_order_with_valid_items_succeeds(
    customer_orders, factory, inventory_for
):
    product = factory("product", price="20.00")
    before = inventory_for(product["attributes"]["sku"])

    response = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 2}]
    )

    assert_status_code(response, 201)
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["subtotal"] == "40.00"
    assert body["tax_total"] == "3.20"
    assert body["shipping_total"] == "9.99"
    assert body["total"] == "53.19"
    item = body["items"][0]
    assert item["product_id"] == product["entity_id"]
    assert item["unit_price"] == "20.00"
    assert item["quantity"] == 2
    assert body["payment"]["status"] == "PENDING"
    assert body["payment"]["amount"] == body["total"]

    after = inventory_for(product["attributes"]["sku"])
    assert after["reserved_stock"] == before["reserved_stock"] + 2


@allure.title("Free shipping applies at/above the threshold, a flat cost below it")
@allure.tag("ORD-010")
@allure.severity(allure.severity_level.NORMAL)
def test_free_shipping_applies_at_the_threshold(customer_orders, factory):
    low = factory("product", price="20.00")
    low_order = customer_orders.create_order(
        items=[{"product_id": low["entity_id"], "quantity": 1}]
    )
    assert low_order.json()["shipping_total"] == "9.99"

    high = factory("product", price="80.00")
    high_order = customer_orders.create_order(
        items=[{"product_id": high["entity_id"], "quantity": 1}]
    )
    assert high_order.json()["shipping_total"] == "0.00"


@allure.title("Creating an order without a customer profile returns 403")
@allure.tag("ORD-011")
@allure.severity(allure.severity_level.CRITICAL)
def test_creating_an_order_without_a_customer_profile_returns_403(
    order_client, factory
):
    product = factory("product", stock=10)

    response = order_client.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 1}]
    )

    assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("An empty items list is rejected")
@allure.tag("ORD-012")
@allure.severity(allure.severity_level.MINOR)
def test_empty_items_list_is_rejected(customer_orders):
    response = customer_orders.create_order(items=[])

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Ordering a nonexistent product returns 404")
@allure.tag("ORD-013")
@allure.severity(allure.severity_level.NORMAL)
def test_ordering_a_nonexistent_product_returns_404(customer_orders):
    response = customer_orders.create_order(
        items=[{"product_id": str(uuid.uuid4()), "quantity": 1}]
    )

    assert_error(response, 404, "PRODUCT_NOT_FOUND")


@allure.title("Ordering an inactive product returns 409")
@allure.tag("ORD-014")
@allure.severity(allure.severity_level.NORMAL)
def test_ordering_an_inactive_product_returns_409(customer_orders, factory):
    product = factory("product", is_active=False)

    response = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 1}]
    )

    assert_error(response, 409, "PRODUCT_INACTIVE")


@allure.title("Ordering more than available stock returns 409 with the shortfall")
@allure.tag("ORD-015")
@allure.severity(allure.severity_level.CRITICAL)
def test_ordering_more_than_available_stock_returns_409(customer_orders, factory):
    product = factory("product", stock=5)

    response = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 6}]
    )

    error = assert_error(response, 409, "INSUFFICIENT_STOCK")
    assert error["details"]["available"] == 5
    assert error["details"]["requested"] == 6


@allure.title("An address not belonging to the customer is rejected")
@allure.tag("ORD-016")
@allure.severity(allure.severity_level.NORMAL)
def test_address_not_belonging_to_customer_is_rejected(
    customer_orders, new_customer_orders, factory
):
    product = factory("product")
    address = AddressClient(customer_orders.api).create_address(
        recipient_name="Test",
        line1="1 Test St",
        city="Testville",
        postal_code="00000",
        country="US",
    )
    address_id = address.json()["id"]

    _, other_orders = new_customer_orders()
    response = other_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 1}],
        shipping_address_id=address_id,
    )

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("A valid promotion code applies a discount")
@allure.tag("ORD-017")
@allure.severity(allure.severity_level.NORMAL)
def test_valid_promotion_code_applies_a_discount(
    customer_orders, factory, seed_manifest, db_session
):
    promo = next(
        (f for f in seed_manifest["fixtures"] if f["key"] == "valid_promotion"), None
    )
    assert promo is not None, "Seed manifest has no valid_promotion fixture"
    product = factory("product", price="20.00", stock=10)
    promotion_id = uuid.UUID(promo["entity_id"])
    used_before = db_session.get(Promotion, promotion_id).usage_count

    response = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 1}],
        promotion_code=promo["label"],
    )

    assert_status_code(response, 201)
    body = response.json()
    assert float(body["discount_total"]) > 0
    assert body["promotion_id"] == str(promo["entity_id"])

    db_session.expire_all()
    usage = db_session.execute(
        select(PromotionUsage).where(PromotionUsage.order_id == uuid.UUID(body["id"]))
    ).scalar_one()
    assert usage.promotion_id == promotion_id
    assert usage.discount_amount == Decimal(body["discount_total"])
    assert db_session.get(Promotion, promotion_id).usage_count == used_before + 1


@allure.title(
    "Retrying a create request with the same Idempotency-Key replays the original order"
)
@allure.tag("ORD-018")
@allure.severity(allure.severity_level.CRITICAL)
def test_retrying_with_the_same_idempotency_key_replays_the_original_order(
    customer_orders, new_product, idempotency_key, db_session, count_rows
):
    key = idempotency_key
    items = [{"product_id": new_product["entity_id"], "quantity": 1}]

    first = customer_orders.create_order(idempotency_key=key, items=items)
    assert_status_code(first, 201)
    order_number = first.json()["order_number"]

    second = customer_orders.create_order(idempotency_key=key, items=items)
    assert_status_code(second, 201)
    assert second.json()["order_number"] == order_number
    assert second.headers.get("Idempotent-Replay") == "true"

    listing = customer_orders.list_orders(search=order_number)
    assert listing.json()["pagination"]["total"] == 1

    order_id = uuid.UUID(first.json()["id"])
    assert count_rows(InventoryTransaction.order_id == order_id) == 1


@allure.title("Reusing an Idempotency-Key with a different request body is rejected")
@allure.tag("ORD-019")
@allure.severity(allure.severity_level.NORMAL)
def test_reusing_idempotency_key_with_a_different_body_is_rejected(
    customer_orders, new_product, idempotency_key
):
    first = customer_orders.create_order(
        idempotency_key=idempotency_key,
        items=[{"product_id": new_product["entity_id"], "quantity": 1}],
    )
    assert_status_code(first, 201)

    second = customer_orders.create_order(
        idempotency_key=idempotency_key,
        items=[{"product_id": new_product["entity_id"], "quantity": 2}],
    )

    error = assert_error(second, 422, "IDEMPOTENCY_KEY_REUSED")
    assert error["details"]["key"] == idempotency_key


@pytest.mark.xfail(
    reason="BUG-004: order creation loses stock reservations under concurrency, "
    "despite a row lock - see BUGS.md",
    strict=True,
)
@allure.title("Concurrent order creation for the same product loses stock reservations")
@allure.tag("ORD-020")
@allure.severity(allure.severity_level.CRITICAL)
def test_concurrent_order_creation_loses_stock_reservations(
    customer_orders, new_product, inventory_for
):
    before = inventory_for(new_product["attributes"]["sku"])
    concurrency = 10

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        responses = list(
            pool.map(
                lambda _: customer_orders.create_order(
                    items=[{"product_id": new_product["entity_id"], "quantity": 1}]
                ),
                range(concurrency),
            )
        )

    assert all(r.status_code == 201 for r in responses)
    after = inventory_for(new_product["attributes"]["sku"])
    assert after["reserved_stock"] == before["reserved_stock"] + concurrency


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


@allure.title("Checking out a non-empty cart creates an order and clears the cart")
@allure.tag("ORD-021")
@allure.severity(allure.severity_level.CRITICAL)
def test_checking_out_a_non_empty_cart_creates_an_order_and_clears_it(
    customer_orders, customer_cart, factory
):
    product = factory("product", price="20.00", stock=10)
    assert_status_code(customer_cart.add_item(product["entity_id"], quantity=2), 200)

    response = customer_orders.checkout()

    assert_status_code(response, 201)
    item = response.json()["items"][0]
    assert item["product_id"] == product["entity_id"]
    assert item["quantity"] == 2
    assert customer_cart.get_cart().json()["items"] == []


@allure.title("Checking out an empty cart returns 409")
@allure.tag("ORD-022")
@allure.severity(allure.severity_level.NORMAL)
def test_checking_out_an_empty_cart_returns_409(customer_orders):
    response = customer_orders.checkout()

    assert_error(response, 409, "CART_EMPTY")


@allure.title("A failed checkout leaves the cart untouched")
@allure.tag("ORD-023")
@allure.severity(allure.severity_level.CRITICAL)
def test_a_failed_checkout_leaves_the_cart_untouched(
    customer_orders, customer_cart, factory, inventory_for, inventory_client
):
    product = factory("product", stock=3)
    assert_status_code(customer_cart.add_item(product["entity_id"], quantity=3), 200)

    record = inventory_for(product["attributes"]["sku"])
    inventory_client.adjust_stock(record["id"], stock_delta=-3)

    response = customer_orders.checkout()

    assert_error(response, 409, "INSUFFICIENT_STOCK")
    assert len(customer_cart.get_cart().json()["items"]) == 1


# ---------------------------------------------------------------------------
# Get order
# ---------------------------------------------------------------------------


@allure.title("Getting your own order succeeds")
@allure.tag("ORD-024")
@allure.severity(allure.severity_level.CRITICAL)
def test_getting_your_own_order_succeeds(customer_orders, new_order):
    order_id = new_order["id"]

    response = customer_orders.get_order(order_id)

    assert_status_code(response, 200)
    assert response.json()["id"] == order_id


@allure.title("Getting another customer's order returns 404, not 403")
@allure.tag("ORD-025")
@allure.severity(allure.severity_level.CRITICAL)
def test_getting_another_customers_order_returns_404(new_order, new_customer_orders):
    _, other_orders = new_customer_orders()
    response = other_orders.get_order(new_order["id"])

    assert_error(response, 404, "ORDER_NOT_FOUND")


@allure.title("Staff can get any order")
@allure.tag("ORD-026")
@allure.severity(allure.severity_level.NORMAL)
def test_staff_can_get_any_order(order_client, new_order):
    order_id = new_order["id"]

    response = order_client.get_order(order_id)

    assert_status_code(response, 200)
    assert response.json()["id"] == order_id


@allure.title("Getting an unknown order ID returns 404")
@allure.tag("ORD-027")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_order_id_returns_404(customer_orders):
    response = customer_orders.get_order(uuid.uuid4())

    assert_error(response, 404, "ORDER_NOT_FOUND")


# ---------------------------------------------------------------------------
# Order status
# ---------------------------------------------------------------------------


@allure.title("Staff can walk an order through the full happy-path state machine")
@allure.tag("ORD-028")
@allure.severity(allure.severity_level.BLOCKER)
def test_staff_can_walk_an_order_through_the_full_happy_path(order_client, new_order):
    order_id = new_order["id"]

    for status in ("CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
        response = order_client.update_status(order_id, status=status)
        assert_status_code(response, 200)
        assert response.json()["status"] == status


@allure.title("An invalid transition is rejected with machine-readable details")
@allure.tag("ORD-029")
@allure.severity(allure.severity_level.CRITICAL)
def test_invalid_transition_is_rejected_with_machine_readable_details(
    order_client, new_order
):
    response = order_client.update_status(new_order["id"], status="SHIPPED")

    error = assert_error(response, 409, "INVALID_STATUS_TRANSITION")
    assert error["details"]["from"] == "PENDING"
    assert error["details"]["to"] == "SHIPPED"
    assert set(error["details"]["allowed"]) == {"CONFIRMED", "CANCELLED"}


@allure.title("A customer can cancel their own PENDING order")
@allure.tag("ORD-030")
@allure.severity(allure.severity_level.CRITICAL)
def test_customer_can_cancel_their_own_pending_order(customer_orders, new_order):
    response = customer_orders.update_status(new_order["id"], status="CANCELLED")

    assert_status_code(response, 200)
    assert response.json()["status"] == "CANCELLED"


@allure.title("A customer cannot cancel an order that has progressed past CONFIRMED")
@allure.tag("ORD-031")
@allure.severity(allure.severity_level.NORMAL)
def test_customer_cannot_cancel_an_order_past_confirmed(
    order_client, customer_orders, new_order
):
    order_id = new_order["id"]
    order_client.update_status(order_id, status="CONFIRMED")
    order_client.update_status(order_id, status="PROCESSING")

    response = customer_orders.update_status(order_id, status="CANCELLED")

    assert_error(response, 409, "INVALID_STATUS_TRANSITION")


@allure.title("A customer attempting any non-cancel transition gets 403")
@allure.tag("ORD-032")
@allure.severity(allure.severity_level.CRITICAL)
def test_customer_attempting_a_non_cancel_transition_gets_403(
    customer_orders, new_order
):
    response = customer_orders.update_status(new_order["id"], status="CONFIRMED")

    assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("Cancelling releases the reserved stock")
@allure.tag("ORD-033")
@allure.severity(allure.severity_level.CRITICAL)
def test_cancelling_releases_the_reserved_stock(
    customer_orders, factory, inventory_for, db_session
):
    product = factory("product")
    before = inventory_for(product["attributes"]["sku"])
    created = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 3}]
    )
    order_id = created.json()["id"]

    reserved = inventory_for(product["attributes"]["sku"])
    assert reserved["reserved_stock"] == before["reserved_stock"] + 3

    customer_orders.update_status(order_id, status="CANCELLED")

    after = inventory_for(product["attributes"]["sku"])
    assert after["reserved_stock"] == before["reserved_stock"]

    types = (
        db_session.execute(
            select(InventoryTransaction.type).where(
                InventoryTransaction.order_id == uuid.UUID(order_id)
            )
        )
        .scalars()
        .all()
    )
    assert sorted(types) == ["RELEASE", "RESERVATION"]


@allure.title(
    "Shipping converts the reservation into a sale without changing available_stock"
)
@allure.tag("ORD-034")
@allure.severity(allure.severity_level.CRITICAL)
def test_shipping_converts_the_reservation_into_a_sale(
    order_client, customer_orders, factory, inventory_for, db_session
):
    product = factory("product")
    created = customer_orders.create_order(
        items=[{"product_id": product["entity_id"], "quantity": 1}]
    )
    order_id = created.json()["id"]
    before = inventory_for(product["attributes"]["sku"])

    order_client.update_status(order_id, status="CONFIRMED")
    order_client.update_status(order_id, status="PROCESSING")
    order_client.update_status(order_id, status="SHIPPED")

    after = inventory_for(product["attributes"]["sku"])
    assert after["stock"] == before["stock"] - 1
    assert after["reserved_stock"] == before["reserved_stock"] - 1
    assert after["available_stock"] == before["available_stock"]

    types = (
        db_session.execute(
            select(InventoryTransaction.type).where(
                InventoryTransaction.order_id == uuid.UUID(order_id)
            )
        )
        .scalars()
        .all()
    )
    assert sorted(types) == ["RESERVATION", "SALE"]


@allure.title("Cancelling a paid order refunds the payment")
@allure.tag("ORD-035")
@allure.severity(allure.severity_level.CRITICAL)
def test_cancelling_a_paid_order_refunds_the_payment(customer_orders, new_order):
    order_id = new_order["id"]
    customer_orders.process_payment(order_id, outcome="success")

    response = customer_orders.update_status(order_id, status="CANCELLED")

    assert_status_code(response, 200)
    assert response.json()["payment"]["status"] == "REFUNDED"


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------


@allure.title(
    "Status history lists entries chronologically, including the initial PENDING entry"
)
@allure.tag("ORD-036")
@allure.severity(allure.severity_level.NORMAL)
def test_status_history_lists_entries_chronologically(customer_orders, new_order):
    order_id = new_order["id"]
    customer_orders.update_status(order_id, status="CANCELLED")

    response = customer_orders.list_status_history(order_id)

    assert_status_code(response, 200)
    history = response.json()
    assert history[0]["from_status"] is None
    assert history[0]["to_status"] == "PENDING"
    assert history[-1]["to_status"] == "CANCELLED"
    timestamps = [h["created_at"] for h in history]
    assert timestamps == sorted(timestamps)


@allure.title("Status history for an unknown order ID returns 404")
@allure.tag("ORD-037")
@allure.severity(allure.severity_level.MINOR)
def test_status_history_for_an_unknown_order_id_returns_404(customer_orders):
    response = customer_orders.list_status_history(uuid.uuid4())

    assert_error(response, 404, "ORDER_NOT_FOUND")


# ---------------------------------------------------------------------------
# Payment processing
# ---------------------------------------------------------------------------


@allure.title("outcome=success marks the payment PAID")
@allure.tag("ORD-038")
@allure.severity(allure.severity_level.CRITICAL)
def test_payment_outcome_success_marks_it_paid(customer_orders, new_order):
    response = customer_orders.process_payment(new_order["id"], outcome="success")

    assert_status_code(response, 200)
    payment = response.json()["payment"]
    assert payment["status"] == "PAID"
    assert payment["paid_at"] is not None
    assert payment["transaction_reference"] is not None


@allure.title("outcome=failure marks the payment FAILED and can be retried afterward")
@allure.tag("ORD-039")
@allure.severity(allure.severity_level.NORMAL)
def test_payment_outcome_failure_can_be_retried(customer_orders, new_order):
    order_id = new_order["id"]

    first = customer_orders.process_payment(order_id, outcome="failure")
    assert_status_code(first, 200)
    assert first.json()["payment"]["status"] == "FAILED"

    second = customer_orders.process_payment(order_id, outcome="success")
    assert_status_code(second, 200)
    assert second.json()["payment"]["status"] == "PAID"


@allure.title("Processing an already-processed payment returns 409")
@allure.tag("ORD-040")
@allure.severity(allure.severity_level.NORMAL)
def test_processing_an_already_processed_payment_returns_409(
    customer_orders, new_order
):
    order_id = new_order["id"]
    customer_orders.process_payment(order_id, outcome="success")

    response = customer_orders.process_payment(order_id, outcome="success")

    assert_error(response, 409, "PAYMENT_ALREADY_PROCESSED")
