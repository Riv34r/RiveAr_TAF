"""
Domain client for admin endpoints (/admin/users/*, /admin/audit-logs,
/admin/roles/*).

    admin = AdminClient(api)
    admin.update_user(user_id, is_active=False)
    admin.list_audit_logs(action="USER_STATUS_CHANGED")
"""

import requests

from core.api_client import ApiClient


class AdminClient:
    """Wraps an ApiClient to expose /admin/* operations without inline payloads."""

    def __init__(self, api: ApiClient):
        self.api = api

    def list_users(self, **params) -> requests.Response:
        return self.api.get("/admin/users", params=params)

    def get_user(self, user_id) -> requests.Response:
        return self.api.get(f"/admin/users/{user_id}")

    def update_user(
        self, user_id, is_active: bool = None, roles: list = None
    ) -> requests.Response:
        payload = {}
        if is_active is not None:
            payload["is_active"] = is_active
        if roles is not None:
            payload["roles"] = roles
        return self.api.patch(f"/admin/users/{user_id}", json=payload)

    def list_audit_logs(self, **params) -> requests.Response:
        return self.api.get("/admin/audit-logs", params=params)

    def list_roles(self) -> requests.Response:
        return self.api.get("/admin/roles")

    def permission_catalogue(self) -> requests.Response:
        return self.api.get("/admin/roles/permission-catalogue")

    def grant_permission(self, role_id, name: str) -> requests.Response:
        return self.api.post(f"/admin/roles/{role_id}/permissions", json={"name": name})

    def revoke_permission(self, role_id, permission_id) -> requests.Response:
        return self.api.delete(f"/admin/roles/{role_id}/permissions/{permission_id}")
