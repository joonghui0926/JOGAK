from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from jogak_api.core.security import decode_access_token
from jogak_api.db.models import User
from jogak_api.db.session import get_db


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except Exception:
        return None

    return db.get(User, payload["sub"])


CurrentUser = Annotated[User | None, Depends(get_current_user)]
DBSession = Annotated[Session, Depends(get_db)]
