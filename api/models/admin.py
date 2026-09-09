"""Pydantic models for admin-only responses.

Mirrors ``app.schemas.audit.AuditLogResponse`` in the SUT. GET /admin/users
reuses UserResponse from api/models/auth.py rather than its own model - it's
the same shape.
"""

import uuid
from datetime import datetime

from api.models.common import StrictModel


class AuditLogResponse(StrictModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    old_value: dict | None
    new_value: dict | None
    created_at: datetime
