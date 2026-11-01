"""Recruiter routes are guarded by RECRUITER_API_KEY, sent as the X-Recruiter-Key header.

Fails closed: without a configured key every recruiter route returns 503.
"""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_recruiter(
    x_recruiter_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().recruiter_api_key
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "RECRUITER_API_KEY is not set")
    if not x_recruiter_key or not hmac.compare_digest(x_recruiter_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "a valid X-Recruiter-Key is required")
