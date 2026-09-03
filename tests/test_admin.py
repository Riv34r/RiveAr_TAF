"""Test cases for /admin/users/* and /admin/audit-logs"""

import uuid

import allure
import pytest

from core.admin_client import AdminClient
from core.api_client import ApiClient
from utils.helpers import assert_error, assert_status_code

pytestmark = allure.feature("Admin")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@allure.title("Listing users returns every account, paginated")
@allure.tag("ADMIN-001")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_users_returns_every_account_paginated(admin_client, seed_manifest):
    response = admin_client.list_users(page_size=100)

    assert_status_code(response, 200)
    body = response.json()
    assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}

    returned_emails = {item["email"] for item in body["items"]}
    seeded_emails = {account["email"] for account in seed_manifest["accounts"]}
    assert seeded_emails <= returned_emails


@allure.title("Listing users without the required permission returns 403")
@allure.tag("ADMIN-002")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_users_without_permission_returns_403(customer_client):
    response = customer_client.list_users()

    error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
    assert "users:manage" in error["details"]["required_any_of"]


@allure.title("Listing users with no token returns 401")
@allure.tag("ADMIN-003")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_users_with_no_token_returns_401(api):
    response = AdminClient(api).list_users()

    assert_error(response, 401, "TOKEN_MISSING")


@allure.title("Getting a known user by ID succeeds")
@allure.tag("ADMIN-004")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_a_known_user_by_id_succeeds(admin_client, customer):
    response = admin_client.get_user(customer["user_id"])

    assert_status_code(response, 200)
    body = response.json()
    assert body["id"] == str(customer["user_id"])
    assert body["email"] == customer["email"]
    assert customer["role"] in body["roles"]


@allure.title("Getting an unknown user ID returns 404")
@allure.tag("ADMIN-005")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_user_id_returns_404(admin_client):
    response = admin_client.get_user(uuid.uuid4())

    assert_error(response, 404, "USER_NOT_FOUND")


@allure.title("Disabling a user's account takes effect immediately")
@allure.tag("ADMIN-006")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
def test_disabling_a_users_account_takes_effect_immediately(
    admin_client, new_customer, auth_client
):
    attrs = new_customer["attributes"]

    response = admin_client.update_user(attrs["user_id"], is_active=False)

    assert_status_code(response, 200)
    assert response.json()["is_active"] is False

    login = auth_client.login(attrs["email"], attrs["password"])
    assert_error(login, 401, "USER_DISABLED")


@allure.title("Reassigning a user's roles replaces the previous set")
@allure.tag("ADMIN-007")
@allure.severity(allure.severity_level.CRITICAL)
def test_reassigning_a_users_roles_replaces_the_previous_set(
    admin_client, new_customer
):
    user_id = new_customer["attributes"]["user_id"]

    response = admin_client.update_user(user_id, roles=["SUPPORT"])

    assert_status_code(response, 200)
    assert response.json()["roles"] == ["SUPPORT"]


@allure.title("Setting an empty roles list is rejected")
@allure.tag("ADMIN-008")
@allure.severity(allure.severity_level.NORMAL)
def test_setting_an_empty_roles_list_is_rejected(admin_client, new_customer):
    user_id = new_customer["attributes"]["user_id"]

    response = admin_client.update_user(user_id, roles=[])

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Updating an unknown user ID returns 404")
@allure.tag("ADMIN-009")
@allure.severity(allure.severity_level.NORMAL)
def test_updating_an_unknown_user_id_returns_404(admin_client):
    response = admin_client.update_user(uuid.uuid4(), is_active=False)

    assert_error(response, 404, "USER_NOT_FOUND")


@allure.title("An admin can disable their own account")
@allure.tag("ADMIN-010")
@allure.severity(allure.severity_level.NORMAL)
def test_an_admin_can_disable_their_own_account(
    admin_client, new_customer, auth_client, api_url
):
    user_id = new_customer["attributes"]["user_id"]

    promote = admin_client.update_user(user_id, roles=["ADMIN"])
    assert_status_code(promote, 200)

    attrs = new_customer["attributes"]
    own_tokens = auth_client.login(attrs["email"], attrs["password"]).json()
    own_admin = AdminClient(ApiClient(api_url, own_tokens["access_token"]))

    response = own_admin.update_user(user_id, is_active=False)

    assert_status_code(response, 200)
    assert response.json()["is_active"] is False


@allure.title("A malformed user_id (not a UUID) returns 422, not 404")
@allure.tag("ADMIN-015")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_user_id_returns_422(admin_client):
    response = admin_client.get_user("not-a-uuid")

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Setting an unrecognised role name is rejected")
@allure.tag("ADMIN-016")
@allure.severity(allure.severity_level.MINOR)
def test_setting_an_unrecognised_role_name_is_rejected(admin_client, new_customer):
    user_id = new_customer["attributes"]["user_id"]

    response = admin_client.update_user(user_id, roles=["NOT_A_ROLE"])

    assert_error(response, 422, "VALIDATION_ERROR")


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


@allure.title("Listing audit logs returns recent entries, paginated")
@allure.tag("ADMIN-011")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_audit_logs_returns_recent_entries_paginated(
    admin_client, new_customer
):
    user_id = new_customer["attributes"]["user_id"]
    admin_client.update_user(user_id, is_active=False)

    response = admin_client.list_audit_logs()

    assert_status_code(response, 200)
    body = response.json()
    assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}
    assert body["items"][0]["entity_id"] == user_id


@allure.title("Listing audit logs without audit_logs:view returns 403")
@allure.tag("ADMIN-012")
@allure.severity(allure.severity_level.MINOR)
def test_listing_audit_logs_without_permission_returns_403(customer_client):
    response = customer_client.list_audit_logs()

    error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
    assert "audit_logs:view" in error["details"]["required_any_of"]


@allure.title("Filtering audit logs by action returns only matching entries")
@allure.tag("ADMIN-013")
@allure.severity(allure.severity_level.NORMAL)
def test_filtering_audit_logs_by_action_returns_only_matching_entries(
    admin_client, new_customer
):
    user_id = new_customer["attributes"]["user_id"]
    admin_client.update_user(user_id, is_active=False)

    response = admin_client.list_audit_logs(action="USER_STATUS_CHANGED")

    assert_status_code(response, 200)
    items = response.json()["items"]
    assert items
    assert all(item["action"] == "USER_STATUS_CHANGED" for item in items)


@allure.title("Granting a permission is itself recorded in the audit log")
@allure.tag("ADMIN-014")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_a_permission_is_recorded_in_the_audit_log(admin_client):
    roles = admin_client.list_roles().json()
    support = next(r for r in roles if r["name"] == "SUPPORT")

    grant_response = admin_client.grant_permission(support["id"], "customers:manage")
    assert_status_code(grant_response, 201)
    permission = next(
        p
        for p in grant_response.json()["permissions"]
        if p["name"] == "customers:manage"
    )

    try:
        response = admin_client.list_audit_logs(action="PERMISSION_GRANTED")
        assert_status_code(response, 200)
        assert any(
            item["entity_type"] == "role"
            and item["new_value"].get("permission") == "customers:manage"
            for item in response.json()["items"]
        )
    finally:
        admin_client.revoke_permission(support["id"], permission["id"])


@allure.title("Combining audit log filters narrows the result, not widens it")
@allure.tag("ADMIN-017")
@allure.severity(allure.severity_level.NORMAL)
def test_combining_audit_log_filters_narrows_the_result(admin_client, factory):
    first_id = factory("customer")["attributes"]["user_id"]
    second_id = factory("customer")["attributes"]["user_id"]
    admin_client.update_user(first_id, is_active=False)
    admin_client.update_user(second_id, is_active=False)

    by_action = admin_client.list_audit_logs(action="USER_STATUS_CHANGED").json()[
        "items"
    ]
    entity_ids = {item["entity_id"] for item in by_action}
    assert {first_id, second_id} <= entity_ids

    combined = admin_client.list_audit_logs(
        action="USER_STATUS_CHANGED", entity_id=first_id
    )

    assert_status_code(combined, 200)
    items = combined.json()["items"]
    assert items
    assert all(item["entity_id"] == first_id for item in items)
