"""Pydantic models for authentication responses.

Mirrors ``app.schemas.auth.TokenResponse`` in the SUT: every successful
register/login/refresh call returns this exact shape.
"""

import uuid
from datetime import datetime

from api.models.common import StrictModel


class TokenResponse(StrictModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(StrictModel):
    """Mirrors ``app.schemas.user.UserResponse`` - not auth-specific despite
    living here, but GET /auth/me is where it's first returned; the same
    shape comes back from every admin user endpoint (see api/models/admin.py's
    usage)."""

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    permissions: list[str]
    last_login_at: datetime | None
    created_at: datetime
