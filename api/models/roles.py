"""Pydantic models for the roles/permissions responses.

Mirrors ``app.schemas.user.RoleResponse``/``PermissionResponse`` in the SUT.
"""

import uuid

from api.models.common import StrictModel


class PermissionResponse(StrictModel):
    id: uuid.UUID
    name: str
    description: str | None


class RoleResponse(StrictModel):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[PermissionResponse]
