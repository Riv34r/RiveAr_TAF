"""Test cases for /admin/roles/*.

Implements ROLE-001 through ROLE-015 from tests/scenarios/api/admin-roles.md.
"""

import uuid

import allure

from utils.helpers import assert_error, assert_status_code

pytestmark = allure.feature("Admin roles")


def role_named(admin_client, name):
    roles = admin_client.list_roles().json()
    return next(r for r in roles if r["name"] == name)


def grant(admin_client, role_id, permission_name):
    response = admin_client.grant_permission(role_id, permission_name)
    assert_status_code(response, 201)
    return next(
        p for p in response.json()["permissions"] if p["name"] == permission_name
    )


@allure.title("Listing roles returns each with its permissions")
@allure.tag("ROLE-001")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_roles_returns_each_with_its_permissions(admin_client):
    response = admin_client.list_roles()

    assert_status_code(response, 200)
    roles = response.json()
    assert roles
    for role in roles:
        assert set(role) >= {"id", "name", "permissions"}


@allure.title("Listing roles without roles:manage returns 403")
@allure.tag("ROLE-002")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_roles_without_permission_returns_403(customer_client):
    response = customer_client.list_roles()

    error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
    assert "roles:manage" in error["details"]["required_any_of"]


@allure.title("The permission catalogue lists every grantable permission")
@allure.tag("ROLE-003")
@allure.severity(allure.severity_level.NORMAL)
def test_permission_catalogue_lists_every_grantable_permission(admin_client):
    response = admin_client.permission_catalogue()

    assert_status_code(response, 200)
    catalogue = response.json()
    assert catalogue
    assert all(isinstance(v, str) for v in catalogue.values())


@allure.title("The permission catalogue requires roles:manage")
@allure.tag("ROLE-004")
@allure.severity(allure.severity_level.MINOR)
def test_permission_catalogue_requires_permission(customer_client):
    response = customer_client.permission_catalogue()

    assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("Granting a permission a role does not yet have succeeds")
@allure.tag("ROLE-005")
@allure.severity(allure.severity_level.CRITICAL)
def test_granting_a_permission_the_role_lacks_succeeds(admin_client):
    role = role_named(admin_client, "SUPPORT")

    granted = grant(admin_client, role["id"], "settings:manage")

    admin_client.revoke_permission(role["id"], granted["id"])


@allure.title("Granting a permission the role already has returns 409")
@allure.tag("ROLE-006")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_a_permission_the_role_already_has_returns_409(admin_client):
    role = role_named(admin_client, "SUPPORT")

    response = admin_client.grant_permission(role["id"], "notes:manage")

    assert_error(response, 409, "PERMISSION_ALREADY_GRANTED")


@allure.title("Granting an unrecognised permission name returns 422")
@allure.tag("ROLE-007")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_an_unrecognised_permission_name_returns_422(admin_client):
    role = role_named(admin_client, "SUPPORT")

    response = admin_client.grant_permission(role["id"], "not-a-real-permission")

    error = assert_error(response, 422, "UNKNOWN_PERMISSION")
    assert "products:manage" in error["details"]["allowed"]


@allure.title("Granting a permission to an unknown role returns 404")
@allure.tag("ROLE-008")
@allure.severity(allure.severity_level.MINOR)
def test_granting_a_permission_to_an_unknown_role_returns_404(admin_client):
    response = admin_client.grant_permission(uuid.uuid4(), "settings:manage")

    assert_error(response, 404, "ROLE_NOT_FOUND")


@allure.title("Revoking a permission a role holds succeeds")
@allure.tag("ROLE-009")
@allure.severity(allure.severity_level.CRITICAL)
def test_revoking_a_permission_the_role_holds_succeeds(admin_client):
    role = role_named(admin_client, "SUPPORT")
    granted = grant(admin_client, role["id"], "analytics:view")

    response = admin_client.revoke_permission(role["id"], granted["id"])

    assert_status_code(response, 200)
    names = [p["name"] for p in response.json()["permissions"]]
    assert "analytics:view" not in names


@allure.title("roles:manage cannot be revoked from ADMIN")
@allure.tag("ROLE-010")
@allure.severity(allure.severity_level.CRITICAL)
def test_roles_manage_cannot_be_revoked_from_admin(admin_client):
    role = role_named(admin_client, "ADMIN")
    permission = next(p for p in role["permissions"] if p["name"] == "roles:manage")

    response = admin_client.revoke_permission(role["id"], permission["id"])

    assert_error(response, 409, "PERMISSION_PROTECTED")


@allure.title("Revoking a permission a role does not hold returns 404")
@allure.tag("ROLE-011")
@allure.severity(allure.severity_level.NORMAL)
def test_revoking_a_permission_the_role_does_not_hold_returns_404(admin_client):
    support = role_named(admin_client, "SUPPORT")
    admin_role = role_named(admin_client, "ADMIN")
    permission = next(
        p for p in admin_role["permissions"] if p["name"] == "audit_logs:view"
    )

    response = admin_client.revoke_permission(support["id"], permission["id"])

    assert_error(response, 404, "PERMISSION_NOT_FOUND")


@allure.title("Revoking a permission from an unknown role returns 404")
@allure.tag("ROLE-012")
@allure.severity(allure.severity_level.MINOR)
def test_revoking_a_permission_from_an_unknown_role_returns_404(admin_client):
    role = role_named(admin_client, "ADMIN")
    permission = next(p for p in role["permissions"] if p["name"] == "roles:manage")

    response = admin_client.revoke_permission(uuid.uuid4(), permission["id"])

    assert_error(response, 404, "ROLE_NOT_FOUND")


@allure.title("A malformed role_id (not a UUID) returns 422, not 404")
@allure.tag("ROLE-013")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_role_id_returns_422(admin_client):
    grant_response = admin_client.grant_permission("not-a-uuid", "settings:manage")
    assert_error(grant_response, 422, "VALIDATION_ERROR")

    revoke_response = admin_client.revoke_permission("not-a-uuid", uuid.uuid4())
    assert_error(revoke_response, 422, "VALIDATION_ERROR")


@allure.title("A malformed permission_id (not a UUID) returns 422, not 404")
@allure.tag("ROLE-014")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_permission_id_returns_422(admin_client):
    role = role_named(admin_client, "SUPPORT")

    response = admin_client.revoke_permission(role["id"], "not-a-uuid")

    assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("An empty permission name is rejected at the schema level")
@allure.tag("ROLE-015")
@allure.severity(allure.severity_level.MINOR)
def test_granting_an_empty_permission_name_is_rejected(admin_client):
    role = role_named(admin_client, "SUPPORT")

    response = admin_client.grant_permission(role["id"], "")

    assert_error(response, 422, "VALIDATION_ERROR")
