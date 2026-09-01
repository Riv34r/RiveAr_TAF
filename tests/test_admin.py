"""Test cases for /admin/users/* and /admin/audit-logs.

Implements ADMIN-001 through ADMIN-014 from tests/scenarios/api/admin.md.
"""

import uuid

import allure

from core.api_client import ApiClient
from utils.helpers import assert_error, assert_status_code, logged_in_customer

pytestmark = allure.feature("Admin")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@allure.title("Listing users returns every account, paginated")
@allure.tag("ADMIN-001")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_users_returns_every_account_paginated(admin_client):
    response = admin_client.get("/admin/users")

    assert_status_code(response, 200)
    body = response.json()
    assert "items" in body
    assert set(body["pagination"]) >= {"page", "page_size", "total", "total_pages"}


@allure.title("Listing users without the required permission returns 403")
@allure.tag("ADMIN-002")
@allure.severity(allure.severity_level.CRITICAL)
def test_listing_users_without_permission_returns_403(api, factory, auth_client):
    _, token_pair = logged_in_customer(factory, auth_client)

    response = api.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )

    error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
    assert "users:manage" in error["details"]["required_any_of"]


@allure.title("Listing users with no token returns 401")
@allure.tag("ADMIN-003")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_users_with_no_token_returns_401(api):
    response = api.get("/admin/users")

    assert_error(response, 401, "TOKEN_MISSING")


@allure.title("Getting a known user by ID succeeds")
@allure.tag("ADMIN-004")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_a_known_user_by_id_succeeds(admin_client, customer):
    response = admin_client.get(f"/admin/users/{customer['user_id']}")

    assert_status_code(response, 200)
    body = response.json()
    assert body["id"] == str(customer["user_id"])
    assert body["email"] == customer["email"]
    assert customer["role"] in body["roles"]


@allure.title("Getting an unknown user ID returns 404")
@allure.tag("ADMIN-005")
@allure.severity(allure.severity_level.NORMAL)
def test_getting_an_unknown_user_id_returns_404(admin_client):
    response = admin_client.get(f"/admin/users/{uuid.uuid4()}")

    assert_error(response, 404, "USER_NOT_FOUND")


@allure.title("Disabling a user's account takes effect immediately")
@allure.tag("ADMIN-006")
@allure.severity(allure.severity_level.BLOCKER)
def test_disabling_a_users_account_takes_effect_immediately(
    admin_client, factory, auth_client
):
    new_customer = factory("customer")
    attrs = new_customer["attributes"]

    response = admin_client.patch(
        f"/admin/users/{attrs['user_id']}", json={"is_active": False}
    )

    assert_status_code(response, 200)
    assert response.json()["is_active"] is False

    login = auth_client.login(attrs["email"], attrs["password"])
    assert_error(login, 401, "USER_DISABLED")


@allure.title("Reassigning a user's roles replaces the previous set")
@allure.tag("ADMIN-007")
@allure.severity(allure.severity_level.CRITICAL)
def test_reassigning_a_users_roles_replaces_the_previous_set(admin_client, factory):
    new_customer = factory("customer")
    user_id = new_customer["attributes"]["user_id"]

    response = admin_client.patch(
        f"/admin/users/{user_id}", json={"roles": ["SUPPORT"]}
    )

    assert_status_code(response, 200)
    assert response.json()["roles"] == ["SUPPORT"]


@allure.title("Setting an empty roles list is rejected")
@allure.tag("ADMIN-008")
@allure.severity(allure.severity_level.NORMAL)
def test_setting_an_empty_roles_list_is_rejected(admin_client, factory):
    new_customer = factory("customer")
    user_id = new_customer["attributes"]["user_id"]

    response = admin_client.patch(f"/admin/users/{user_id}", json={"roles": []})

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("Updating an unknown user ID returns 404")
@allure.tag("ADMIN-009")
@allure.severity(allure.severity_level.NORMAL)
def test_updating_an_unknown_user_id_returns_404(admin_client):
    response = admin_client.patch(
        f"/admin/users/{uuid.uuid4()}", json={"is_active": False}
    )

    assert_error(response, 404, "USER_NOT_FOUND")


@allure.title("An admin can disable their own account")
@allure.tag("ADMIN-010")
@allure.severity(allure.severity_level.NORMAL)
def test_an_admin_can_disable_their_own_account(
    admin_client, factory, auth_client, api_url
):
    new_customer = factory("customer")
    attrs = new_customer["attributes"]
    user_id = attrs["user_id"]

    promote = admin_client.patch(f"/admin/users/{user_id}", json={"roles": ["ADMIN"]})
    assert_status_code(promote, 200)

    own_tokens = auth_client.login(attrs["email"], attrs["password"]).json()
    own_client = ApiClient(api_url, own_tokens["access_token"])

    response = own_client.patch(f"/admin/users/{user_id}", json={"is_active": False})

    assert_status_code(response, 200)
    assert response.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


@allure.title("Listing audit logs returns recent entries, paginated")
@allure.tag("ADMIN-011")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_audit_logs_returns_recent_entries_paginated(admin_client):
    response = admin_client.get("/admin/audit-logs")

    assert_status_code(response, 200)
    body = response.json()
    assert "items" in body and "pagination" in body


@allure.title("Listing audit logs without audit_logs:view returns 403")
@allure.tag("ADMIN-012")
@allure.severity(allure.severity_level.MINOR)
def test_listing_audit_logs_without_permission_returns_403(api, factory, auth_client):
    _, token_pair = logged_in_customer(factory, auth_client)

    response = api.get(
        "/admin/audit-logs",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )

    error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
    assert "audit_logs:view" in error["details"]["required_any_of"]


@allure.title("Filtering audit logs by action returns only matching entries")
@allure.tag("ADMIN-013")
@allure.severity(allure.severity_level.NORMAL)
def test_filtering_audit_logs_by_action_returns_only_matching_entries(
    admin_client, factory
):
    user_id = factory("customer")["attributes"]["user_id"]
    admin_client.patch(f"/admin/users/{user_id}", json={"is_active": False})

    response = admin_client.get(
        "/admin/audit-logs", params={"action": "USER_STATUS_CHANGED"}
    )

    assert_status_code(response, 200)
    items = response.json()["items"]
    assert items
    assert all(item["action"] == "USER_STATUS_CHANGED" for item in items)


@allure.title("Granting a permission is itself recorded in the audit log")
@allure.tag("ADMIN-014")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_a_permission_is_recorded_in_the_audit_log(admin_client):
    roles = admin_client.get("/admin/roles").json()
    support = next(r for r in roles if r["name"] == "SUPPORT")

    grant_response = admin_client.post(
        f"/admin/roles/{support['id']}/permissions", json={"name": "customers:manage"}
    )
    assert_status_code(grant_response, 201)
    permission = next(
        p
        for p in grant_response.json()["permissions"]
        if p["name"] == "customers:manage"
    )

    try:
        response = admin_client.get(
            "/admin/audit-logs", params={"action": "PERMISSION_GRANTED"}
        )
        assert_status_code(response, 200)
        assert any(
            item["entity_type"] == "role"
            and item["new_value"].get("permission") == "customers:manage"
            for item in response.json()["items"]
        )
    finally:
        admin_client.delete(
            f"/admin/roles/{support['id']}/permissions/{permission['id']}"
        )
