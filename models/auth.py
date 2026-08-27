"""Pydantic models for authentication responses.

Mirrors ``app.schemas.auth.TokenResponse`` in the SUT: every successful
register/login/refresh call returns this exact shape.
"""

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
