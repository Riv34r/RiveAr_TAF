"""Test cases for /admin/roles/*.

Implements ROLE-001 through ROLE-017 from tests/api/scenarios/admin-roles.md.
"""

import uuid

import allure
import pytest
from pydantic import TypeAdapter

from api.clients.admin_client import AdminClient
from api.models.roles import RoleResponse
from utils.helpers import assert_error, assert_status_code, step

pytestmark = allure.feature("Admin roles")


def role_named(admin_client, name):
    roles = admin_client.list_roles().json()
    role = next((r for r in roles if r["name"] == name), None)
    assert role is not None, f"No role named {name!r} - check seed data"
    return role


def grant(admin_client, role_id, permission_name):
    response = admin_client.grant_permission(role_id, permission_name)
    assert_status_code(response, 201)
    permission = next(
        (p for p in response.json()["permissions"] if p["name"] == permission_name),
        None,
    )
    assert permission is not None, f"{permission_name!r} missing from grant response"
    return permission


# ---------------------------------------------------------------------------
# Permission boundary
# ---------------------------------------------------------------------------

ROLE_ENDPOINTS = [
    ("list_roles", lambda c: c.list_roles()),
    ("permission_catalogue", lambda c: c.permission_catalogue()),
    ("grant_permission", lambda c: c.grant_permission(uuid.uuid4(), "products:manage")),
    ("revoke_permission", lambda c: c.revoke_permission(uuid.uuid4(), uuid.uuid4())),
]


@allure.title("Every admin-roles endpoint requires authentication - {name}")
@allure.tag("ROLE-001")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.parametrize(
    "name,call", ROLE_ENDPOINTS, ids=[e[0] for e in ROLE_ENDPOINTS]
)
def test_role_endpoints_require_authentication(api, name, call):
    with step(f"Call {name} without a token"):
        response = call(AdminClient(api))

    with step("The request is turned away"):
        assert_error(response, 401, "TOKEN_MISSING")


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


@allure.title("Listing roles response matches the RoleResponse schema")
@allure.tag("ROLE-002")
@allure.severity(allure.severity_level.NORMAL)
def test_list_roles_response_matches_schema(admin_client):
    with step("List the roles"):
        response = admin_client.list_roles()

    with step("Every role validates against RoleResponse"):
        assert_status_code(response, 200)
        roles = TypeAdapter(list[RoleResponse]).validate_python(response.json())
        assert roles


@allure.title("Listing roles returns each with its permissions")
@allure.tag("ROLE-003")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_roles_returns_each_with_its_permissions(admin_client):
    with step("List the roles"):
        response = admin_client.list_roles()

    with step("Each one carries its permissions, not just a name"):
        assert_status_code(response, 200)
        roles = response.json()
        assert roles
        for role in roles:
            assert set(role) >= {"id", "name", "permissions"}


@allure.title("Listing roles without roles:manage returns 403")
@allure.tag("ROLE-004")
@allure.severity(allure.severity_level.NORMAL)
def test_listing_roles_without_permission_returns_403(customer_client):
    with step("A customer lists the roles"):
        response = customer_client.list_roles()

    with step("They are refused, and told which permission was needed"):
        error = assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")
        assert "roles:manage" in error["details"]["required_any_of"]


@allure.title("The permission catalogue lists every grantable permission")
@allure.tag("ROLE-005")
@allure.severity(allure.severity_level.NORMAL)
def test_permission_catalogue_lists_every_grantable_permission(admin_client):
    with step("Read the permission catalogue"):
        response = admin_client.permission_catalogue()

    with step("It is a non-empty map of permission to description"):
        assert_status_code(response, 200)
        catalogue = response.json()
        assert catalogue
        assert all(isinstance(v, str) for v in catalogue.values())


@allure.title("The permission catalogue requires roles:manage")
@allure.tag("ROLE-006")
@allure.severity(allure.severity_level.MINOR)
def test_permission_catalogue_requires_permission(customer_client):
    with step("A customer reads the permission catalogue"):
        response = customer_client.permission_catalogue()

    with step("They are refused"):
        assert_error(response, 403, "INSUFFICIENT_PERMISSIONS")


@allure.title("Granting a permission a role does not yet have succeeds")
@allure.tag("ROLE-007")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_granting_a_permission_the_role_lacks_succeeds(admin_client):
    with step("Given the SUPPORT role"):
        role = role_named(admin_client, "SUPPORT")

    granted = None
    try:
        with step("Granting it settings:manage returns the permission"):
            granted = grant(admin_client, role["id"], "settings:manage")
    finally:
        if granted is not None:
            admin_client.revoke_permission(role["id"], granted["id"])


@allure.title("Granting a permission the role already has returns 409")
@allure.tag("ROLE-008")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_a_permission_the_role_already_has_returns_409(admin_client):
    with step("Given the SUPPORT role, which already holds notes:manage"):
        role = role_named(admin_client, "SUPPORT")

    with step("Grant it again"):
        response = admin_client.grant_permission(role["id"], "notes:manage")

    with step("The duplicate grant is refused"):
        assert_error(response, 409, "PERMISSION_ALREADY_GRANTED")


@allure.title("Granting an unrecognised permission name returns 422")
@allure.tag("ROLE-009")
@allure.severity(allure.severity_level.NORMAL)
def test_granting_an_unrecognised_permission_name_returns_422(admin_client):
    with step("Given the SUPPORT role"):
        role = role_named(admin_client, "SUPPORT")

    with step("Grant it a permission that does not exist"):
        response = admin_client.grant_permission(role["id"], "not-a-real-permission")

    with step("The error lists the permissions that do"):
        error = assert_error(response, 422, "UNKNOWN_PERMISSION")
        assert "products:manage" in error["details"]["allowed"]


@allure.title("Granting a permission to an unknown role returns 404")
@allure.tag("ROLE-010")
@allure.severity(allure.severity_level.MINOR)
def test_granting_a_permission_to_an_unknown_role_returns_404(admin_client):
    with step("Grant a permission to a role ID that does not exist"):
        response = admin_client.grant_permission(uuid.uuid4(), "settings:manage")

    with step("The role is not found"):
        assert_error(response, 404, "ROLE_NOT_FOUND")


@allure.title("Revoking a permission a role holds succeeds")
@allure.tag("ROLE-011")
@allure.severity(allure.severity_level.CRITICAL)
def test_revoking_a_permission_the_role_holds_succeeds(admin_client):
    with step("Given the SUPPORT role"):
        role = role_named(admin_client, "SUPPORT")

    granted = None
    try:
        with step("Grant it analytics:view"):
            granted = grant(admin_client, role["id"], "analytics:view")

        with step("Revoke it again"):
            response = admin_client.revoke_permission(role["id"], granted["id"])

        with step("The role no longer holds it"):
            assert_status_code(response, 200)
            names = [p["name"] for p in response.json()["permissions"]]
            assert "analytics:view" not in names
            granted = None  # already revoked above - nothing left for finally to do
    finally:
        if granted is not None:
            admin_client.revoke_permission(role["id"], granted["id"])


@allure.title("Roles:manage cannot be revoked from ADMIN")
@allure.tag("ROLE-012")
@allure.severity(allure.severity_level.CRITICAL)
def test_roles_manage_cannot_be_revoked_from_admin(admin_client):
    with step("Given ADMIN's own roles:manage permission"):
        role = role_named(admin_client, "ADMIN")
        permission = next(
            (p for p in role["permissions"] if p["name"] == "roles:manage"), None
        )
        assert permission is not None, "ADMIN is missing roles:manage - check seed data"

    with step("Try to revoke it"):
        response = admin_client.revoke_permission(role["id"], permission["id"])

    with step("The permission is protected"):
        assert_error(response, 409, "PERMISSION_PROTECTED")


@allure.title("Revoking a permission a role does not hold returns 404")
@allure.tag("ROLE-013")
@allure.severity(allure.severity_level.NORMAL)
def test_revoking_a_permission_the_role_does_not_hold_returns_404(admin_client):
    with step("Given a permission ADMIN holds and SUPPORT does not"):
        support = role_named(admin_client, "SUPPORT")
        admin_role = role_named(admin_client, "ADMIN")
        permission = next(
            (p for p in admin_role["permissions"] if p["name"] == "audit_logs:view"),
            None,
        )
        assert (
            permission is not None
        ), "ADMIN is missing audit_logs:view - check seed data"

    with step("Revoke it from SUPPORT"):
        response = admin_client.revoke_permission(support["id"], permission["id"])

    with step("The permission is not found on that role"):
        assert_error(response, 404, "PERMISSION_NOT_FOUND")


@allure.title("Revoking a permission from an unknown role returns 404")
@allure.tag("ROLE-014")
@allure.severity(allure.severity_level.MINOR)
def test_revoking_a_permission_from_an_unknown_role_returns_404(admin_client):
    with step("Given a real permission ID"):
        role = role_named(admin_client, "ADMIN")
        permission = next(
            (p for p in role["permissions"] if p["name"] == "roles:manage"), None
        )
        assert permission is not None, "ADMIN is missing roles:manage - check seed data"

    with step("Revoke it from a role ID that does not exist"):
        response = admin_client.revoke_permission(uuid.uuid4(), permission["id"])

    with step("The role is reported missing before the permission"):
        assert_error(response, 404, "ROLE_NOT_FOUND")


@allure.title("A malformed role_id (not a UUID) returns 422, not 404")
@allure.tag("ROLE-015")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_role_id_returns_422(admin_client):
    with step("Grant against a role_id that is not a UUID"):
        grant_response = admin_client.grant_permission("not-a-uuid", "settings:manage")
        assert_error(grant_response, 422, "VALIDATION_ERROR")

    with step("Revoke against the same malformed role_id"):
        revoke_response = admin_client.revoke_permission("not-a-uuid", uuid.uuid4())
        assert_error(revoke_response, 422, "VALIDATION_ERROR")


@allure.title("A malformed permission_id (not a UUID) returns 422, not 404")
@allure.tag("ROLE-016")
@allure.severity(allure.severity_level.MINOR)
def test_malformed_permission_id_returns_422(admin_client):
    with step("Given the SUPPORT role"):
        role = role_named(admin_client, "SUPPORT")

    with step("Revoke a permission_id that is not a UUID"):
        response = admin_client.revoke_permission(role["id"], "not-a-uuid")

    with step("It is rejected as malformed, not as missing"):
        assert_error(response, 422, "VALIDATION_ERROR")


@allure.title("An empty permission name is rejected at the schema level")
@allure.tag("ROLE-017")
@allure.severity(allure.severity_level.MINOR)
def test_granting_an_empty_permission_name_is_rejected(admin_client):
    with step("Given the SUPPORT role"):
        role = role_named(admin_client, "SUPPORT")

    with step("Grant it a permission with an empty name"):
        response = admin_client.grant_permission(role["id"], "")

    with step("The schema rejects it"):
        assert_error(response, 422, "VALIDATION_ERROR")
