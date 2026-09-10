"""Test cases for /products/*.

Implements PROD-001 through PROD-040 from tests/api/scenarios/products.md.
"""

import uuid

import allure
import pytest
from faker import Faker

from api.clients.product_client import ProductClient
from api.models.product import BulkOperationResponse, ProductResponse
from db.models import Product
from utils.helpers import assert_error, assert_status_code

pytestmark = allure.feature("Products")

fake = Faker()


# ---------------------------------------------------------------------------
# Permission boundary
# ---------------------------------------------------------------------------

PRODUCT_ENDPOINTS = [
    ("create_product", lambda c: c.create_product(sku="X", name="X", price="1.00")),
    ("update_product", lambda c: c.update_product(uuid.uuid4(), name="X")),
    ("delete_product", lambda c: c.delete_product(uuid.uuid4())),
    ("restore_product", lambda c: c.restore_product(uuid.uuid4())),
    ("bulk_products", lambda c: c.bulk_products([uuid.uuid4()], action="deactivate")),
]


@allure.title("Every products:manage-only endpoint requires authentication - {name}")
@allure.tag("PROD-001")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize(
    "name,call", PRODUCT_ENDPOINTS, ids=[e[0] for e in PRODUCT_ENDPOINTS]
)
def test_product_endpoints_require_authentication(api, name, call):
    response = call(ProductClient(api))

    assert_error(response, 401, "TOKEN_MISSING")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


@allure.title("Product response matches the ProductResponse schema")
@allure.tag("PROD-002")
@allure.severity(allure.severity_level.NORMAL)
def test_product_response_matches_schema(product_client, factory, new_product):
    category_id = factory("category")["entity_id"]
    response = product_client.update_product(
        new_product["entity_id"], category_ids=[category_id]
    )

    assert_status_code(response, 200)
    body = ProductResponse.model_validate(response.json())
    assert body.categories


@allure.title("Bulk operation response matches the BulkOperationResponse schema")
@allure.tag("PROD-003")
@allure.severity(allure.severity_level.NORMAL)
def test_bulk_response_matches_schema(product_client, new_product):
    response = product_client.bulk_products(
        [new_product["entity_id"]], action="deactivate"
    )

    assert_status_code(response, 200)
    BulkOperationResponse.model_validate(response.json())


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@allure.title("Listing products returns paginated results")
@allure.tag("PROD-004")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_listing_products_returns_paginated_results(product_client):
    response = product_client.list_products()

    assert_status_code(response, 200)
    body = response.json()
    assert "items" in body
    assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}


@allure.title("Default listing includes inactive products")
@allure.tag("PROD-005")
@allure.severity(allure.severity_level.NORMAL)
def test_default_listing_includes_inactive_products(product_client, factory):
    name = fake.unique.company()
    factory("product", name=name, is_active=False)

    response = product_client.list_products(search=name)

    assert_status_code(response, 200)
    names = [item["name"] for item in response.json()["items"]]
    assert name in names


@allure.title("Filtering by status=active excludes inactive products")
@allure.tag("PROD-006")
@allure.severity(allure.severity_level.NORMAL)
def test_filtering_by_status_active_excludes_inactive_products(product_client, factory):
    name = fake.unique.company()
    factory("product", name=name, is_active=False)

    response = product_client.list_products(search=name, status="active")

    assert_status_code(response, 200)
    assert response.json()["items"] == []


@allure.title("An invalid sort_by returns 422 with the allowed values in the message")
@allure.tag("PROD-007")
@allure.severity(allure.severity_level.MINOR)
def test_invalid_sort_by_returns_422(product_client):
    response = product_client.list_products(sort_by="not_a_real_column")

    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert "price" in error["message"]


@allure.title("Searching by name or description returns matching products")
@allure.tag("PROD-008")
@allure.severity(allure.severity_level.NORMAL)
def test_searching_returns_matching_products(product_client, factory):
    name = fake.unique.company()
    factory("product", name=name)

    response = product_client.list_products(search=name)

    assert_status_code(response, 200)
    names = [item["name"] for item in response.json()["items"]]
    assert name in names


@allure.title("Combining price filters narrows the result")
@allure.tag("PROD-009")
@allure.severity(allure.severity_level.NORMAL)
def test_combining_price_filters_narrows_the_result(product_client):
    response = product_client.list_products(min_price="20.00", max_price="50.00")

    assert_status_code(response, 200)
    items = response.json()["items"]
    assert items
    assert all(20.00 <= float(item["price"]) <= 50.00 for item in items)


@allure.title("Include_deleted is ignored for non-manager callers")
@allure.tag("PROD-010")
@allure.severity(allure.severity_level.NORMAL)
def test_include_deleted_is_ignored_for_non_manager(
    public_products, product_client, factory
):
    name = fake.unique.company()
    new_product = factory("product", name=name)
    product_client.delete_product(new_product["entity_id"])

    response = public_products.list_products(search=name, include_deleted=True)

    assert_status_code(response, 200)
    assert response.json()["items"] == []


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


@allure.title("Getting a known product by ID succeeds")
@allure.tag("PROD-011")
@allure.severity(allure.severity_level.CRITICAL)
def test_getting_a_known_product_by_id_succeeds(product_client, new_product):
    product_id = new_product["entity_id"]

    response = product_client.get_product(product_id)

    assert_status_code(response, 200)
    body = response.json()
    assert body["id"] == product_id
    assert body["sku"] == new_product["attributes"]["sku"]


@allure.title("Getting an unknown product ID returns 404")
@allure.tag("PROD-012")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_product_id_returns_404(product_client):
    response = product_client.get_product(uuid.uuid4())

    assert_error(response, 404, "PRODUCT_NOT_FOUND")


@allure.title(
    "A soft-deleted product is hidden from the public but visible to managers"
)
@allure.tag("PROD-013")
@allure.severity(allure.severity_level.NORMAL)
def test_soft_deleted_product_hidden_from_public_visible_to_managers(
    public_products, product_client, new_product
):
    product_id = new_product["entity_id"]
    product_client.delete_product(product_id)

    public_response = public_products.get_product(product_id)
    assert_error(public_response, 404, "PRODUCT_NOT_FOUND")

    manager_response = product_client.get_product(product_id)
    assert_status_code(manager_response, 200)
    assert manager_response.json()["deleted_at"] is not None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@allure.title("Creating a product with valid data succeeds")
@allure.tag("PROD-014")
@allure.severity(allure.severity_level.BLOCKER)
def test_creating_a_product_succeeds(product_client):
    sku = f"TAF-{uuid.uuid4().hex[:12]}"

    response = product_client.create_product(
        sku=sku, name=fake.unique.company(), price="19.99"
    )

    assert_status_code(response, 201)
    body = response.json()
    assert body["sku"] == sku
    assert body["available_stock"] == 0


@allure.title("Creating a product without products:manage returns 403")
@allure.tag("PROD-015")
@allure.severity(allure.severity_level.CRITICAL)
def test_creating_a_product_without_permission_returns_403(customer_products):
    response = customer_products.create_product(
        sku=f"TAF-{uuid.uuid4().hex[:12]}", name=fake.unique.company(), price="19.99"
    )

    assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("Creating a product with a duplicate SKU returns 409")
@allure.tag("PROD-016")
@allure.severity(allure.severity_level.NORMAL)
def test_creating_a_product_with_duplicate_sku_returns_409(product_client, new_product):
    existing_sku = new_product["attributes"]["sku"]

    response = product_client.create_product(
        sku=existing_sku, name=fake.unique.company(), price="19.99"
    )

    assert_error(response, 409, "SKU_ALREADY_EXISTS")


@allure.title("A discount_price at or above price is rejected")
@allure.tag("PROD-017")
@allure.severity(allure.severity_level.NORMAL)
def test_discount_price_at_or_above_price_is_rejected(product_client):
    response = product_client.create_product(
        sku=f"TAF-{uuid.uuid4().hex[:12]}",
        name=fake.unique.company(),
        price="10.00",
        discount_price="10.00",
    )

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("An unknown category_id is rejected")
@allure.tag("PROD-018")
@allure.severity(allure.severity_level.MINOR)
def test_creating_with_an_unknown_category_id_is_rejected(product_client):
    response = product_client.create_product(
        sku=f"TAF-{uuid.uuid4().hex[:12]}",
        name=fake.unique.company(),
        price="19.99",
        category_ids=[str(uuid.uuid4())],
    )

    assert_error(response, 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@allure.title("A partial update only changes the fields sent")
@allure.tag("PROD-019")
@allure.severity(allure.severity_level.CRITICAL)
def test_partial_update_only_changes_the_fields_sent(product_client, new_product):
    product_id = new_product["entity_id"]
    before = product_client.get_product(product_id).json()

    response = product_client.update_product(product_id, price="77.77")

    assert_status_code(response, 200)
    after = response.json()
    assert after["price"] == "77.77"

    # effective_price mirrors price when no discount is set; version/updated_at
    # change on every update regardless of which field triggered it.
    side_effects = {"price", "effective_price", "version", "updated_at"}
    for field in set(before) - side_effects:
        assert after[field] == before[field], f"{field} changed unexpectedly"


@allure.title("Updating an unknown product ID returns 404")
@allure.tag("PROD-020")
@allure.severity(allure.severity_level.NORMAL)
def test_updating_an_unknown_product_id_returns_404(product_client):
    response = product_client.update_product(uuid.uuid4(), name=fake.unique.company())

    assert_error(response, 404, "PRODUCT_NOT_FOUND")


@allure.title("Replacing category_ids replaces the previous set, not adds to it")
@allure.tag("PROD-021")
@allure.severity(allure.severity_level.NORMAL)
def test_replacing_category_ids_replaces_the_previous_set(
    product_client, factory, new_product
):
    product_id = new_product["entity_id"]
    first_category = factory("category")["entity_id"]
    second_category = factory("category")["entity_id"]
    first_update = product_client.update_product(
        product_id, category_ids=[first_category]
    )
    assert_status_code(first_update, 200)

    response = product_client.update_product(product_id, category_ids=[second_category])

    assert_status_code(response, 200)
    category_ids = [c["id"] for c in response.json()["categories"]]
    assert category_ids == [second_category]


# ---------------------------------------------------------------------------
# Delete & Restore
# ---------------------------------------------------------------------------


@allure.title("Soft-deleting a product removes it from the default listing and get")
@allure.tag("PROD-022")
@allure.severity(allure.severity_level.BLOCKER)
def test_soft_deleting_removes_from_listing_and_get(
    public_products, product_client, new_product, db_session
):
    product_id = new_product["entity_id"]
    name = new_product["attributes"]["name"]

    response = product_client.delete_product(product_id)

    assert_status_code(response, 204)
    assert_error(public_products.get_product(product_id), 404, "PRODUCT_NOT_FOUND")
    assert public_products.list_products(search=name).json()["items"] == []

    row = db_session.get(Product, uuid.UUID(product_id))
    assert row is not None, "The product row was deleted outright, not soft-deleted"
    assert row.deleted_at is not None


@allure.title("Restoring a soft-deleted product succeeds and stays inactive")
@allure.tag("PROD-023")
@allure.severity(allure.severity_level.NORMAL)
def test_restoring_a_soft_deleted_product_succeeds(product_client, new_product):
    product_id = new_product["entity_id"]
    product_client.delete_product(product_id)

    response = product_client.restore_product(product_id)

    assert_status_code(response, 200)
    body = response.json()
    assert body["deleted_at"] is None
    assert body["is_active"] is False


@allure.title("Restoring a product that is not deleted returns 404")
@allure.tag("PROD-024")
@allure.severity(allure.severity_level.MINOR)
def test_restoring_a_non_deleted_product_returns_404(product_client, new_product):
    response = product_client.restore_product(new_product["entity_id"])

    assert_error(response, 404, "PRODUCT_NOT_FOUND")


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


@allure.title("Best_effort with every id valid succeeds")
@allure.tag("PROD-025")
@allure.severity(allure.severity_level.CRITICAL)
def test_best_effort_with_every_id_valid_succeeds(product_client, factory):
    first = factory("product")["entity_id"]
    second = factory("product")["entity_id"]

    response = product_client.bulk_products([first, second], action="deactivate")

    assert_status_code(response, 200)
    body = response.json()
    assert body["applied"] is True
    assert body["summary"] == {"total": 2, "succeeded": 2, "failed": 0}
    assert product_client.get_product(first).json()["is_active"] is False
    assert product_client.get_product(second).json()["is_active"] is False


@allure.title("Best_effort with a mix of valid and invalid ids partially succeeds")
@allure.tag("PROD-026")
@allure.severity(allure.severity_level.CRITICAL)
def test_best_effort_with_mixed_ids_partially_succeeds(product_client, new_product):
    real_id = new_product["entity_id"]
    unknown_id = str(uuid.uuid4())

    response = product_client.bulk_products([real_id, unknown_id], action="deactivate")

    assert_status_code(response, 207)
    body = response.json()
    assert body["applied"] is True
    results = {r["id"]: r for r in body["results"]}
    assert results[real_id]["success"] is True
    assert results[unknown_id]["success"] is False
    assert results[unknown_id]["code"] == "PRODUCT_NOT_FOUND"
    assert product_client.get_product(real_id).json()["is_active"] is False


@allure.title("Atomic with every id valid succeeds")
@allure.tag("PROD-027")
@allure.severity(allure.severity_level.NORMAL)
def test_atomic_with_every_id_valid_succeeds(product_client, factory):
    first = factory("product")["entity_id"]
    second = factory("product")["entity_id"]

    response = product_client.bulk_products(
        [first, second], action="deactivate", mode="atomic"
    )

    assert_status_code(response, 200)
    assert response.json()["applied"] is True
    assert product_client.get_product(first).json()["is_active"] is False
    assert product_client.get_product(second).json()["is_active"] is False


@allure.title("Atomic with any invalid id rolls back everything")
@allure.tag("PROD-028")
@allure.severity(allure.severity_level.CRITICAL)
def test_atomic_with_any_invalid_id_rolls_back_everything(
    product_client, new_product, db_session
):
    real_id = new_product["entity_id"]
    unknown_id = str(uuid.uuid4())

    response = product_client.bulk_products(
        [real_id, unknown_id], action="deactivate", mode="atomic"
    )

    error = assert_error(response, 409, "BULK_ROLLED_BACK")
    assert error["details"]["applied"] is False
    assert product_client.get_product(real_id).json()["is_active"] is True

    assert db_session.get(Product, uuid.UUID(real_id)).is_active is True


@allure.title("An empty ids list is rejected")
@allure.tag("PROD-029")
@allure.severity(allure.severity_level.NORMAL)
def test_empty_ids_list_is_rejected(product_client):
    response = product_client.bulk_products([], action="deactivate")

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("More than the maximum ids is rejected")
@allure.tag("PROD-030")
@allure.severity(allure.severity_level.MINOR)
def test_more_than_the_maximum_ids_is_rejected(product_client):
    ids = [str(uuid.uuid4()) for _ in range(101)]

    response = product_client.bulk_products(ids, action="deactivate")

    error = assert_error(response, 422, "VALIDATION_ERROR")
    ctx = error["details"]["errors"][0]["ctx"]
    assert ctx["max_length"] == 100
    assert ctx["actual_length"] == 101


@allure.title("Duplicate ids are collapsed, not rejected")
@allure.tag("PROD-031")
@allure.severity(allure.severity_level.MINOR)
def test_duplicate_ids_are_collapsed_not_rejected(product_client, new_product):
    product_id = new_product["entity_id"]

    response = product_client.bulk_products(
        [product_id, product_id], action="deactivate"
    )

    assert_status_code(response, 200)
    body = response.json()
    assert body["summary"]["total"] == 1
    assert len(body["results"]) == 1


@allure.title("Bulk without products:manage returns 403")
@allure.tag("PROD-032")
@allure.severity(allure.severity_level.CRITICAL)
def test_bulk_without_permission_returns_403(customer_products):
    response = customer_products.bulk_products([str(uuid.uuid4())], action="deactivate")

    assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("Activating a soft-deleted product fails per-item, not the whole batch")
@allure.tag("PROD-033")
@allure.severity(allure.severity_level.NORMAL)
def test_activating_a_soft_deleted_product_fails_per_item(product_client, new_product):
    product_id = new_product["entity_id"]
    product_client.delete_product(product_id)

    response = product_client.bulk_products([product_id], action="activate")

    assert_status_code(response, 207)
    body = response.json()
    assert body["summary"]["failed"] == 1
    result = body["results"][0]
    assert result["success"] is False
    assert result["code"] == "PRODUCT_DELETED"


@allure.title("Bulk requires no If-Match precondition")
@allure.tag("PROD-034")
@allure.severity(allure.severity_level.MINOR)
def test_bulk_requires_no_if_match_precondition(product_client, new_product):
    response = product_client.bulk_products(
        [new_product["entity_id"]], action="deactivate"
    )

    assert_status_code(response, 200)


# ---------------------------------------------------------------------------
# Concurrency (ETag / If-Match)
# ---------------------------------------------------------------------------


@allure.title("GET returns an ETag header matching the body's version")
@allure.tag("PROD-035")
@allure.severity(allure.severity_level.NORMAL)
def test_get_returns_etag_header_matching_the_bodys_version(
    product_client, new_product
):
    response = product_client.get_product(new_product["entity_id"])

    version = response.json()["version"]
    assert response.headers["ETag"] == f'"{version}"'


@allure.title("Updating without If-Match returns 428")
@allure.tag("PROD-036")
@allure.severity(allure.severity_level.CRITICAL)
def test_updating_without_if_match_returns_428(product_client, new_product):
    response = product_client.update_product(
        new_product["entity_id"], if_match=None, name=fake.unique.company()
    )

    error = assert_error(response, 428, "PRECONDITION_REQUIRED")
    assert "current_etag" in error["details"]


@allure.title("Deleting without If-Match returns 428")
@allure.tag("PROD-037")
@allure.severity(allure.severity_level.NORMAL)
def test_deleting_without_if_match_returns_428(product_client, new_product):
    response = product_client.delete_product(new_product["entity_id"], if_match=None)

    assert_error(response, 428, "PRECONDITION_REQUIRED")


@allure.title("Updating with a stale If-Match returns 412")
@allure.tag("PROD-038")
@allure.severity(allure.severity_level.CRITICAL)
def test_updating_with_a_stale_if_match_returns_412(product_client, new_product):
    product_id = new_product["entity_id"]
    original_version = product_client.get_product(product_id).json()["version"]
    product_client.update_product(product_id, name=fake.unique.company())
    before = product_client.get_product(product_id).json()

    response = product_client.update_product(
        product_id, if_match=f'"{original_version}"', name=fake.unique.company()
    )

    error = assert_error(response, 412, "PRECONDITION_FAILED")
    assert error["details"]["current_etag"] == f'"{before["version"]}"'
    assert error["details"]["provided"] == [str(original_version)]
    assert product_client.get_product(product_id).json() == before


@allure.title("Deleting with a stale If-Match returns 412")
@allure.tag("PROD-039")
@allure.severity(allure.severity_level.NORMAL)
def test_deleting_with_a_stale_if_match_returns_412(product_client, new_product):
    product_id = new_product["entity_id"]
    original_version = product_client.get_product(product_id).json()["version"]
    product_client.update_product(product_id, name=fake.unique.company())

    response = product_client.delete_product(
        product_id, if_match=f'"{original_version}"'
    )

    assert_error(response, 412, "PRECONDITION_FAILED")
    assert product_client.get_product(product_id).json()["deleted_at"] is None


@allure.title("If-Match: * always succeeds regardless of actual version")
@allure.tag("PROD-040")
@allure.severity(allure.severity_level.NORMAL)
def test_if_match_star_always_succeeds(product_client, new_product):
    response = product_client.update_product(
        new_product["entity_id"], if_match="*", name=fake.unique.company()
    )

    assert_status_code(response, 200)
