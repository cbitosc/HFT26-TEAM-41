"""Bearer-token authentication against the fixed user table."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import repo
from app.models import User

# auto_error=False: a missing or non-Bearer header reaches get_current_user as None.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(repo.get_session)],
) -> User:
    """FastAPI dependency: the user owning the bearer token, or 401."""
    user = repo.find_user_by_token(session, credentials.credentials) if credentials else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
