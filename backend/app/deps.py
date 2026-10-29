"""Request dependencies: current user and role checks."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from .content import Curriculum, get_curriculum
from .db import get_db
from .models import User
from .security import read_token

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in first", headers={"WWW-Authenticate": "Bearer"})
    try:
        data = read_token(cred.credentials)
        uid = int(data["sub"])
    except (PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, uid)
    if user is None or user.role != data.get("role"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This is for {' or '.join(roles)} accounts")
        return user

    return dep


def curriculum() -> Curriculum:
    return get_curriculum()
